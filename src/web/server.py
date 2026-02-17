# -*- coding: utf-8 -*-
import asyncio
import os
import sys
import time
import json
import logging
import secrets
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Depends, status, Query, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator, constr

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger

security = HTTPBearer(auto_error=False)

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_TIME = 300
TOKEN_EXPIRE_HOURS = 24
MAX_MESSAGE_LENGTH = 5000
MAX_WS_CONNECTIONS = 10
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60


class WebConfig:
    def __init__(self):
        self.enabled: bool = True
        self.host: str = "127.0.0.1"
        self.port: int = 8080
        self.secret: str = ""
        self.username: str = "admin"
        self.password_hash: str = ""
        self._raw_password: str = "admin123"


web_config = WebConfig()
bot_instance = None
web_app = None
web_server = None
ws_clients: Dict[str, WebSocket] = {}
log_buffer: List[str] = []
log_buffer_max = 500

login_attempts: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "lock_until": 0})
active_tokens: Dict[str, Dict] = {}
rate_limits: Dict[str, List[float]] = defaultdict(list)


class LogHandler(logging.Handler):
    def emit(self, record):
        global log_buffer
        log_line = self.format(record)
        log_buffer.append(log_line)
        if len(log_buffer) > log_buffer_max:
            log_buffer = log_buffer[-log_buffer_max:]


def hash_password(password: str, salt: str = None) -> tuple:
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return salt, hashed.hex()


def verify_password(password: str, salt: str, stored_hash: str) -> bool:
    _, computed_hash = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, stored_hash)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def is_valid_token(token: str) -> bool:
    if token not in active_tokens:
        return False
    token_info = active_tokens[token]
    if datetime.now() > token_info["expires"]:
        del active_tokens[token]
        return False
    return True


def check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    requests = rate_limits[client_ip]
    rate_limits[client_ip] = [t for t in requests if now - t < RATE_LIMIT_WINDOW]
    if len(rate_limits[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False
    rate_limits[client_ip].append(now)
    return True


def check_login_attempts(ip: str) -> bool:
    now = time.time()
    attempt = login_attempts[ip]
    if attempt["lock_until"] > now:
        return False
    return True


def record_login_failure(ip: str):
    now = time.time()
    attempt = login_attempts[ip]
    attempt["count"] += 1
    if attempt["count"] >= MAX_LOGIN_ATTEMPTS:
        attempt["lock_until"] = now + LOGIN_LOCKOUT_TIME
        attempt["count"] = 0


def reset_login_attempts(ip: str):
    if ip in login_attempts:
        del login_attempts[ip]


def init_web(bot, config: dict):
    global bot_instance, web_config, web_app
    bot_instance = bot
    
    web_cfg = config.get('web', {})
    web_config.enabled = web_cfg.get('enabled', True)
    web_config.host = web_cfg.get('host', '127.0.0.1')
    web_config.port = web_cfg.get('port', 8080)
    web_config.secret = web_cfg.get('secret', '')
    web_config.username = web_cfg.get('username', 'admin')
    
    password = web_cfg.get('password', 'admin123')
    web_config._raw_password = password
    salt, hashed = hash_password(password)
    web_config.password_hash = f"{salt}:{hashed}"
    
    log_handler = LogHandler()
    log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logging.getLogger().addHandler(log_handler)
    
    web_app = create_app()
    return web_app


def get_bot():
    if bot_instance is None:
        raise HTTPException(status_code=503, detail="Service unavailable")
    return bot_instance


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def verify_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    client_ip = get_client_ip(request)
    
    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    
    if credentials is None:
        raise HTTPException(status_code=401, detail="未授权访问")
    
    token = credentials.credentials
    
    if not is_valid_token(token):
        raise HTTPException(status_code=401, detail="Token无效或已过期")
    
    return True


async def verify_ws_token(token: str) -> bool:
    if not token:
        return False
    return is_valid_token(token)


class LoginRequest(BaseModel):
    username: constr(min_length=1, max_length=50)
    password: constr(min_length=1, max_length=100)


class PluginAction(BaseModel):
    plugin_name: constr(min_length=1, max_length=100)
    
    @validator('plugin_name')
    def validate_plugin_name(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('插件名称格式无效')
        return v


class PermissionUser(BaseModel):
    qq: int
    
    @validator('qq')
    def validate_qq(cls, v):
        if v <= 0 or v > 10**12:
            raise ValueError('无效的QQ号')
        return v


class GroupBlacklist(BaseModel):
    group_id: int
    
    @validator('group_id')
    def validate_group_id(cls, v):
        if v <= 0 or v > 10**12:
            raise ValueError('无效的群号')
        return v


class RestartRequest(BaseModel):
    confirm: bool


class SendMessageRequest(BaseModel):
    message_type: str
    user_id: Optional[int] = None
    group_id: Optional[int] = None
    message: constr(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    
    @validator('message_type')
    def validate_message_type(cls, v):
        if v not in ['private', 'group']:
            raise ValueError('消息类型必须是 private 或 group')
        return v


async def broadcast_to_ws(data: dict):
    global ws_clients
    message = json.dumps(data, ensure_ascii=False)
    disconnected = []
    for token, client in ws_clients.items():
        try:
            await client.send_text(message)
        except:
            disconnected.append(token)
    for token in disconnected:
        if token in ws_clients:
            del ws_clients[token]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Starrain-BOT 管理后台",
        description="QQ机器人Web管理系统",
        version="2.0.0",
        docs_url=None,
        redoc_url=None
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if web_config.host == "0.0.0.0" else [f"http://localhost:{web_config.port}"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
    
    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_file = static_dir / "index.html"
        if html_file.exists():
            return FileResponse(html_file, media_type="text/html")
        return HTMLResponse(content=get_fallback_html(), status_code=200)
    
    @app.post("/api/login")
    async def login(request: Request, req: LoginRequest):
        client_ip = get_client_ip(request)
        
        if not check_login_attempts(client_ip):
            lock_remaining = int(login_attempts[client_ip]["lock_until"] - time.time())
            raise HTTPException(
                status_code=429, 
                detail=f"登录失败次数过多，请{lock_remaining}秒后再试"
            )
        
        if not check_rate_limit(client_ip):
            raise HTTPException(status_code=429, detail="请求过于频繁")
        
        try:
            parts = web_config.password_hash.split(":")
            if len(parts) != 2:
                is_valid = secrets.compare_digest(req.password, web_config._raw_password)
            else:
                salt, stored_hash = parts
                is_valid = verify_password(req.password, salt, stored_hash)
        except Exception:
            is_valid = False
        
        if req.username != web_config.username or not is_valid:
            record_login_failure(client_ip)
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        reset_login_attempts(client_ip)
        
        token = generate_token()
        active_tokens[token] = {
            "expires": datetime.now() + timedelta(hours=TOKEN_EXPIRE_HOURS),
            "ip": client_ip,
            "created": datetime.now()
        }
        
        return {"success": True, "token": token, "expires_in": TOKEN_EXPIRE_HOURS * 3600}
    
    @app.post("/api/logout")
    async def logout(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ):
        if credentials:
            token = credentials.credentials
            if token in active_tokens:
                del active_tokens[token]
        return {"success": True, "message": "已退出登录"}
    
    @app.get("/api/status")
    async def get_status(auth: bool = Depends(verify_auth)):
        bot = get_bot()
        uptime = bot.uptime_seconds
        adapters_info = []
        for a in bot.adapters:
            name = a.__class__.__name__
            connected = getattr(a, "connected", False) or (getattr(a, "is_connected", lambda: False)())
            adapters_info.append({"name": name, "connected": connected})
        
        import platform
        try:
            import psutil
            mem = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=0.1)
            mem_info = {"percent": mem.percent, "available": mem.available // (1024*1024)}
        except ImportError:
            cpu_percent = 0
            mem_info = {"percent": 0, "available": 0}
        
        return {
            "qq": bot.qq,
            "uptime": uptime,
            "uptime_formatted": format_uptime(uptime),
            "running": bot._running,
            "adapters": adapters_info,
            "plugins_count": len(bot.plugin_manager.plugins),
            "enabled_plugins_count": len(bot.plugin_manager.enabled_plugins),
            "system": {
                "python": sys.version.split()[0],
                "platform": f"{platform.system()} {platform.release()}",
                "cpu_cores": os.cpu_count() or 0,
                "cpu_percent": cpu_percent,
                "memory": mem_info
            }
        }
    
    @app.get("/api/plugins")
    async def list_plugins(auth: bool = Depends(verify_auth)):
        bot = get_bot()
        plugins = []
        for name, plugin in bot.plugin_manager.plugins.items():
            enabled = name in bot.plugin_manager.enabled_plugins
            meta = plugin.metadata
            if isinstance(meta, dict):
                version = meta.get("version", "?")
                author = meta.get("author", "Unknown")
                description = meta.get("description", "")
            else:
                version = getattr(meta, "version", "?")
                author = getattr(meta, "author", "Unknown")
                description = getattr(meta, "description", "")
            plugins.append({
                "name": name,
                "enabled": enabled,
                "version": version,
                "author": author,
                "description": description
            })
        return {"plugins": plugins}
    
    @app.post("/api/plugins/enable")
    async def enable_plugin(req: PluginAction, auth: bool = Depends(verify_auth)):
        bot = get_bot()
        ok = bot.plugin_manager.enable_plugin(req.plugin_name)
        if ok:
            await broadcast_to_ws({"type": "plugin_update", "action": "enable", "plugin": req.plugin_name})
            return {"success": True, "message": f"插件 {req.plugin_name} 已启用"}
        raise HTTPException(status_code=400, detail="启用插件失败")
    
    @app.post("/api/plugins/disable")
    async def disable_plugin(req: PluginAction, auth: bool = Depends(verify_auth)):
        bot = get_bot()
        ok = bot.plugin_manager.disable_plugin(req.plugin_name)
        if ok:
            await broadcast_to_ws({"type": "plugin_update", "action": "disable", "plugin": req.plugin_name})
            return {"success": True, "message": f"插件 {req.plugin_name} 已禁用"}
        raise HTTPException(status_code=400, detail="禁用插件失败")
    
    @app.post("/api/plugins/reload")
    async def reload_plugin(req: PluginAction, auth: bool = Depends(verify_auth)):
        bot = get_bot()
        ok = bot.plugin_manager.reload_plugin(req.plugin_name)
        if ok:
            await broadcast_to_ws({"type": "plugin_update", "action": "reload", "plugin": req.plugin_name})
            return {"success": True, "message": f"插件 {req.plugin_name} 已重载"}
        raise HTTPException(status_code=400, detail="重载插件失败")
    
    @app.get("/api/permissions/admins")
    async def list_admins(auth: bool = Depends(verify_auth)):
        bot = get_bot()
        return {
            "admins": bot.permission_manager.list_admins(),
            "owners": bot.permission_manager.list_owners(),
            "developers": bot.permission_manager.list_developers()
        }
    
    @app.post("/api/permissions/admins/add")
    async def add_admin(req: PermissionUser, auth: bool = Depends(verify_auth)):
        bot = get_bot()
        bot.permission_manager.add_admin(req.qq)
        await broadcast_to_ws({"type": "permission_update", "level": "admin"})
        return {"success": True, "message": f"已添加管理员: {req.qq}"}
    
    @app.post("/api/permissions/admins/remove")
    async def remove_admin(req: PermissionUser, auth: bool = Depends(verify_auth)):
        bot = get_bot()
        bot.permission_manager.remove_admin(req.qq)
        await broadcast_to_ws({"type": "permission_update", "level": "admin"})
        return {"success": True, "message": f"已移除管理员: {req.qq}"}
    
    @app.post("/api/permissions/owners/add")
    async def add_owner(req: PermissionUser, auth: bool = Depends(verify_auth)):
        bot = get_bot()
        bot.permission_manager.add_owner(req.qq)
        await broadcast_to_ws({"type": "permission_update", "level": "owner"})
        return {"success": True, "message": f"已添加所有者: {req.qq}"}
    
    @app.post("/api/permissions/owners/remove")
    async def remove_owner(req: PermissionUser, auth: bool = Depends(verify_auth)):
        bot = get_bot()
        bot.permission_manager.remove_owner(req.qq)
        await broadcast_to_ws({"type": "permission_update", "level": "owner"})
        return {"success": True, "message": f"已移除所有者: {req.qq}"}
    
    @app.post("/api/permissions/developers/add")
    async def add_developer(req: PermissionUser, auth: bool = Depends(verify_auth)):
        bot = get_bot()
        bot.permission_manager.add_developer(req.qq)
        await broadcast_to_ws({"type": "permission_update", "level": "developer"})
        return {"success": True, "message": f"已添加开发者: {req.qq}"}
    
    @app.post("/api/permissions/developers/remove")
    async def remove_developer(req: PermissionUser, auth: bool = Depends(verify_auth)):
        bot = get_bot()
        bot.permission_manager.remove_developer(req.qq)
        await broadcast_to_ws({"type": "permission_update", "level": "developer"})
        return {"success": True, "message": f"已移除开发者: {req.qq}"}
    
    @app.get("/api/blacklist")
    async def list_blacklist(auth: bool = Depends(verify_auth)):
        bot = get_bot()
        return {"groups": bot.permission_manager.list_blacklisted_groups()}
    
    @app.post("/api/blacklist/add")
    async def add_blacklist(req: GroupBlacklist, auth: bool = Depends(verify_auth)):
        bot = get_bot()
        bot.permission_manager.add_group_blacklist(req.group_id)
        await broadcast_to_ws({"type": "blacklist_update"})
        return {"success": True, "message": f"已拉黑群: {req.group_id}"}
    
    @app.post("/api/blacklist/remove")
    async def remove_blacklist(req: GroupBlacklist, auth: bool = Depends(verify_auth)):
        bot = get_bot()
        bot.permission_manager.remove_group_blacklist(req.group_id)
        await broadcast_to_ws({"type": "blacklist_update"})
        return {"success": True, "message": f"已移除黑名单群: {req.group_id}"}
    
    @app.get("/api/logs")
    async def get_logs(lines: int = Query(default=100, le=500), auth: bool = Depends(verify_auth)):
        global log_buffer
        if not log_buffer:
            log_file = project_root / "logs" / "bot.log"
            if log_file.exists():
                try:
                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        all_lines = f.readlines()
                        log_buffer = [line.strip() for line in all_lines[-log_buffer_max:]]
                except Exception:
                    return {"logs": [], "error": "无法读取日志"}
        
        return {"logs": log_buffer[-lines:] if len(log_buffer) > lines else log_buffer}
    
    @app.post("/api/message/send")
    async def send_message(req: SendMessageRequest, auth: bool = Depends(verify_auth)):
        bot = get_bot()
        
        if req.message_type == "group" and not req.group_id:
            raise HTTPException(status_code=400, detail="群消息需要group_id")
        if req.message_type == "private" and not req.user_id:
            raise HTTPException(status_code=400, detail="私聊消息需要user_id")
        
        adapter = None
        for a in bot.adapters:
            if getattr(a, "connected", False):
                adapter = a
                break
        
        if not adapter:
            raise HTTPException(status_code=503, detail="没有可用的连接")
        
        try:
            result = await adapter.send_message(
                message_type=req.message_type,
                user_id=req.user_id or 0,
                group_id=req.group_id,
                message=req.message
            )
            if result:
                await broadcast_to_ws({
                    "type": "message_sent",
                    "message_type": req.message_type,
                    "target": req.group_id or req.user_id
                })
                return {"success": True, "message": "消息发送成功"}
            raise HTTPException(status_code=500, detail="消息发送失败")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=500, detail="发送消息异常")
    
    @app.get("/api/friends")
    async def get_friends(auth: bool = Depends(verify_auth)):
        bot = get_bot()
        adapter = None
        for a in bot.adapters:
            if getattr(a, "connected", False):
                adapter = a
                break
        
        if not adapter:
            return {"friends": [], "error": "没有可用的连接"}
        
        try:
            result = await adapter.call_api("get_friend_list", {})
            if result and result.get("status") == "ok":
                return {"friends": result.get("data", [])}
            return {"friends": [], "error": "获取好友列表失败"}
        except Exception:
            return {"friends": [], "error": "获取好友列表失败"}
    
    @app.get("/api/groups")
    async def get_groups(auth: bool = Depends(verify_auth)):
        bot = get_bot()
        adapter = None
        for a in bot.adapters:
            if getattr(a, "connected", False):
                adapter = a
                break
        
        if not adapter:
            return {"groups": [], "error": "没有可用的连接"}
        
        try:
            result = await adapter.call_api("get_group_list", {})
            if result and result.get("status") == "ok":
                return {"groups": result.get("data", [])}
            return {"groups": [], "error": "获取群列表失败"}
        except Exception:
            return {"groups": [], "error": "获取群列表失败"}
    
    @app.post("/api/system/restart")
    async def restart_bot(req: RestartRequest, auth: bool = Depends(verify_auth)):
        if not req.confirm:
            raise HTTPException(status_code=400, detail="需要确认重启")
        bot = get_bot()
        bot._restart_requested = True
        await broadcast_to_ws({"type": "system", "action": "restart"})
        asyncio.create_task(delayed_restart())
        return {"success": True, "message": "机器人将在1秒后重启"}
    
    @app.post("/api/system/shutdown")
    async def shutdown_bot(req: RestartRequest, auth: bool = Depends(verify_auth)):
        if not req.confirm:
            raise HTTPException(status_code=400, detail="需要确认关闭")
        bot = get_bot()
        bot._shutdown_requested = True
        await broadcast_to_ws({"type": "system", "action": "shutdown"})
        asyncio.create_task(delayed_shutdown())
        return {"success": True, "message": "机器人将在1秒后关闭"}
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        token = websocket.query_params.get("token")
        
        if not token or not await verify_ws_token(token):
            await websocket.close(code=4001, reason="Unauthorized")
            return
        
        if len(ws_clients) >= MAX_WS_CONNECTIONS:
            await websocket.close(code=4003, reason="Too many connections")
            return
        
        await websocket.accept()
        ws_clients[token] = websocket
        
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except json.JSONDecodeError:
                    pass
        except WebSocketDisconnect:
            pass
        finally:
            if token in ws_clients:
                del ws_clients[token]
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": exc.detail, "code": exc.status_code}
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "服务器内部错误", "code": 500}
        )
    
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    return app


def format_uptime(seconds: float) -> str:
    if seconds <= 0:
        return "未启动"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d > 0:
        return f"{d}天{h}时{m}分"
    if h > 0:
        return f"{h}时{m}分{s}秒"
    if m > 0:
        return f"{m}分{s}秒"
    return f"{s}秒"


async def delayed_restart():
    global web_server
    await asyncio.sleep(1)
    if web_server:
        web_server.should_exit = True
        await asyncio.sleep(0.5)
    if bot_instance:
        await bot_instance.stop()
    os.execv(sys.executable, [sys.executable] + sys.argv)


async def delayed_shutdown():
    await asyncio.sleep(1)
    if bot_instance:
        await bot_instance.stop()
    sys.exit(0)


def get_fallback_html() -> str:
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Starrain-BOT</title></head>
<body style="background:#0f172a;color:#fff;font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;margin:0">
<div style="text-align:center">
<h1>Starrain-BOT</h1><p>Web管理界面加载中...</p>
</div></body></html>"""


async def run_web_server():
    global web_server
    import uvicorn
    logger = get_logger()
    if not web_config.enabled:
        logger.info("Web管理后台已禁用")
        return
    if web_app is None:
        logger.error("Web应用未初始化")
        return
    app = web_app  # type: ignore
    logger.info(f"启动Web管理后台: http://{web_config.host}:{web_config.port}")
    config = uvicorn.Config(
        app,
        host=web_config.host,
        port=web_config.port,
        log_level="warning"
    )
    web_server = uvicorn.Server(config)
    await web_server.serve()

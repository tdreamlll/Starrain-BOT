import asyncio
import aiohttp
from aiohttp import web
import hmac
import hashlib
import json
from typing import Dict, Any, Optional
from .base import BaseAdapter
from src.utils.logger import get_logger


def _get_logger():
    return get_logger()


class HTTPAdapter(BaseAdapter):
    """
    HTTP适配器 (OneBot v11 HTTP通信)
    
    OneBot v11 HTTP通信分为两部分:
    1. HTTP API: 调用NapCat的API接口 (NapCat作为HTTP服务端)
    2. HTTP POST上报: NapCat主动推送事件到本服务 (NapCat作为HTTP客户端)
    
    NapCat配置示例 (onebot11_xxx.json):
    {
        "network": {
            "httpServers": [{
                "enable": true,
                "host": "127.0.0.1",
                "port": 3000,
                "token": ""
            }],
            "httpClients": [{
                "enable": true,
                "url": "http://127.0.0.1:5700",
                "timeout": 5000
            }]
        }
    }
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get('http_url', 'http://localhost:3000')
        self.access_token = config.get('access_token', '')
        self.timeout = config.get('timeout', 30)
        
        self.post_port = config.get('http_post_port', 5700)
        self.post_host = config.get('http_post_host', '0.0.0.0')
        self.post_secret = config.get('http_post_secret', '')
        
        self.session: Optional[aiohttp.ClientSession] = None
        self._heartbeat_task = None
        self._runner: Optional[web.AppRunner] = None
        self._server_started = False
        self._self_id: Optional[str] = None
    
    async def connect(self) -> bool:
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(
                    headers=self._get_headers(),
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                )
            
            if not self._server_started:
                _get_logger().success(f"[HTTP] API服务已启动: {self.api_url}")
                if not await self._start_post_server():
                    return False
            
            napcat_ok = await self._check_napcat_connection()
            if napcat_ok:
                self.connected = True
                _get_logger().success(f"[HTTP] 已连接到NapCat API: {self.api_url}")
                
                login_info = await self.get_login_info()
                if login_info:
                    self._self_id = str(login_info.get('user_id', ''))
                    _get_logger().info(f"[HTTP] 机器人账号: {login_info.get('nickname', '')}({self._self_id})")
            else:
                self.connected = False
                _get_logger().warning(f"[HTTP] NapCat API未响应: {self.api_url}")
            
            if not self._heartbeat_task or self._heartbeat_task.done():
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            if not self.connected and self.auto_reconnect:
                asyncio.create_task(self._reconnect_loop())
            
            return self.connected

        except Exception as e:
            _get_logger().error(f"[HTTP] 初始化失败: {e}")
            self.connected = False
            return False
    
    async def _start_post_server(self) -> bool:
        try:
            app = self._create_app()
            self._runner = web.AppRunner(app)
            await self._runner.setup()
            site = web.TCPSite(self._runner, self.post_host, self.post_port)
            await site.start()
            self._server_started = True
            _get_logger().success(f"[HTTP] 事件上报服务已启动: http://{self.post_host}:{self.post_port}")
            _get_logger().info(f"[HTTP] 请在NapCat中配置httpClients指向此地址")
            return True
        except OSError as e:
            if 'Address already in use' in str(e) or '10048' in str(e):
                _get_logger().error(f"[HTTP] 端口 {self.post_port} 已被占用，请修改配置中的http_post_port")
            else:
                _get_logger().error(f"[HTTP] 启动事件上报服务失败: {e}")
            return False
        except Exception as e:
            _get_logger().error(f"[HTTP] 启动事件上报服务失败: {e}")
            return False
    
    def _create_app(self) -> web.Application:
        app = web.Application()
        app.router.add_post('/', self._handle_event)
        app.router.add_route('*', '/{path:.*}', self._handle_options)
        return app
    
    async def _handle_options(self, request: web.Request) -> web.Response:
        if request.method == 'OPTIONS':
            return web.Response(
                status=200,
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type, X-Signature, X-Self-ID, Authorization'
                }
            )
        return web.Response(status=405)
    
    async def _handle_event(self, request: web.Request) -> web.Response:
        try:
            body = await request.read()
            
            if not body:
                _get_logger().warning("[HTTP] 收到空请求")
                return web.Response(status=400, text="Empty body")
            
            if self.post_secret:
                sig = request.headers.get('X-Signature', '')
                if not sig.startswith('sha1='):
                    _get_logger().warning("[HTTP] 签名格式错误")
                    return web.Response(status=401, text="Invalid signature format")
                
                computed_sig = 'sha1=' + hmac.new(
                    self.post_secret.encode(),
                    body,
                    hashlib.sha1
                ).hexdigest()
                
                if not hmac.compare_digest(sig, computed_sig):
                    _get_logger().warning("[HTTP] 签名验证失败")
                    return web.Response(status=401, text="Invalid signature")
            
            try:
                event_data = json.loads(body)
            except json.JSONDecodeError as e:
                _get_logger().error(f"[HTTP] JSON解析失败: {e}")
                return web.Response(status=400, text="Invalid JSON")
            
            self_id = request.headers.get('X-Self-ID', '')
            if self_id and self._self_id and self_id != self._self_id:
                _get_logger().warning(f"[HTTP] Self-ID不匹配: {self_id} != {self._self_id}")
                return web.Response(status=403, text="Wrong self_id")
            
            asyncio.create_task(self._process_event(event_data))
            
            return web.json_response(
                {},
                status=200,
                headers={'Access-Control-Allow-Origin': '*'}
            )
            
        except Exception as e:
            _get_logger().error(f"[HTTP] 事件处理错误: {e}")
            return web.Response(status=500, text="Internal Server Error")
    
    async def _process_event(self, event_data: Dict[str, Any]):
        try:
            self._log_event(event_data)
            await self.emit_event(event_data)
        except Exception as e:
            _get_logger().error(f"[HTTP] 事件处理异常: {e}")
    
    def _log_event(self, data: Dict[str, Any]):
        post_type = data.get('post_type', 'unknown')
        
        if post_type == 'message':
            self._log_message_event(data)
        elif post_type == 'message_sent':
            self._log_message_sent_event(data)
        elif post_type == 'notice':
            self._log_notice_event(data)
        elif post_type == 'request':
            self._log_request_event(data)
        elif post_type == 'meta_event':
            self._log_meta_event(data)
        else:
            _get_logger().debug(f"[HTTP] 收到事件: {data}")
    
    def _log_message_event(self, data: Dict[str, Any]):
        message_type = data.get('message_type', '')
        user_id = data.get('user_id', 0)
        group_id = data.get('group_id', 0)
        raw_message = data.get('raw_message', '')
        sender = data.get('sender', {})
        nickname = sender.get('nickname', str(user_id))
        
        if message_type == 'group':
            _get_logger().info(f"[HTTP] [群:{group_id}] {nickname}({user_id}): {raw_message}")
        elif message_type == 'private':
            _get_logger().info(f"[HTTP] [私聊] {nickname}({user_id}): {raw_message}")
        else:
            _get_logger().info(f"[HTTP] [消息] {nickname}({user_id}): {raw_message}")
    
    def _log_message_sent_event(self, data: Dict[str, Any]):
        message_type = data.get('message_type', '')
        group_id = data.get('group_id', 0)
        user_id = data.get('user_id', 0)
        raw_message = data.get('raw_message', '')
        
        if message_type == 'group':
            _get_logger().info(f"[HTTP] [已发送-群:{group_id}]: {raw_message}")
        elif message_type == 'private':
            _get_logger().info(f"[HTTP] [已发送-私聊:{user_id}]: {raw_message}")
        else:
            _get_logger().info(f"[HTTP] [已发送]: {raw_message}")
    
    def _log_notice_event(self, data: Dict[str, Any]):
        notice_type = data.get('notice_type', '')
        sub_type = data.get('sub_type', '')
        group_id = data.get('group_id', 0)
        user_id = data.get('user_id', 0)
        operator_id = data.get('operator_id', 0)
        
        notice_msgs = {
            'group_upload': lambda: f"[群:{group_id}] 文件上传: {data.get('file', {}).get('name', '未知')} (QQ:{user_id})",
            'group_admin': lambda: f"[群:{group_id}] {'设为' if sub_type == 'set' else '取消'}管理员: QQ:{user_id}",
            'group_decrease': lambda: {
                'leave': f"[群:{group_id}] 成员退群: QQ:{user_id}",
                'kick': f"[群:{group_id}] 成员被踢: QQ:{user_id} (操作者:{operator_id})",
                'kick_me': f"[群:{group_id}] 机器人被踢出"
            }.get(sub_type, f"[群:{group_id}] 成员减少: QQ:{user_id}"),
            'group_increase': lambda: f"[群:{group_id}] {'同意入群' if sub_type == 'approve' else '邀请入群'}: QQ:{user_id}",
            'group_ban': lambda: {
                'ban': f"[群:{group_id}] 禁言: QQ:{user_id} {data.get('duration', 0)}秒",
                'lift_ban': f"[群:{group_id}] 解除禁言: QQ:{user_id}"
            }.get(sub_type, f"[群:{group_id}] 禁言变更: QQ:{user_id}"),
            'friend_add': lambda: f"[HTTP] 新增好友: QQ:{user_id}",
            'group_recall': lambda: f"[群:{group_id}] 消息撤回: QQ:{user_id} (操作者:{operator_id})",
            'friend_recall': lambda: f"[HTTP] 好友消息撤回: QQ:{user_id}",
            'notify': lambda: self._format_notify_log(data, group_id, user_id, sub_type),
        }
        
        msg_func = notice_msgs.get(notice_type)
        if msg_func:
            _get_logger().info(f"[HTTP] {msg_func()}")
        else:
            _get_logger().info(f"[HTTP] [通知] {notice_type}: {data}")
    
    def _format_notify_log(self, data: Dict[str, Any], group_id: int, user_id: int, sub_type: str) -> str:
        target_id = data.get('target_id', 0)
        
        if sub_type == 'poke':
            return f"[群:{group_id}] 戳一戳: QQ:{user_id} -> QQ:{target_id}"
        elif sub_type == 'lucky_king':
            return f"[群:{group_id}] 红包运气王: QQ:{target_id}"
        elif sub_type == 'honor':
            honor_names = {'talkative': '龙王', 'performer': '群聊之火', 'emotion': '快乐源泉'}
            honor_name = honor_names.get(data.get('honor_type', ''), data.get('honor_type', '未知荣誉'))
            return f"[群:{group_id}] 荣誉: QQ:{user_id} 获得{honor_name}"
        return f"[群:{group_id}] 通知: {sub_type}"
    
    def _log_request_event(self, data: Dict[str, Any]):
        request_type = data.get('request_type', '')
        sub_type = data.get('sub_type', '')
        user_id = data.get('user_id', 0)
        group_id = data.get('group_id', 0)
        comment = data.get('comment', '')
        
        if request_type == 'friend':
            _get_logger().info(f"[HTTP] [好友请求] QQ:{user_id}: {comment}")
        elif request_type == 'group':
            if sub_type == 'add':
                _get_logger().info(f"[HTTP] [加群请求] QQ:{user_id} -> 群:{group_id}: {comment}")
            elif sub_type == 'invite':
                _get_logger().info(f"[HTTP] [群邀请] QQ:{user_id} 邀请加入群:{group_id}")
        else:
            _get_logger().info(f"[HTTP] [请求] {request_type}: {data}")
    
    def _log_meta_event(self, data: Dict[str, Any]):
        meta_event_type = data.get('meta_event_type', '')
        
        if meta_event_type == 'lifecycle':
            sub_type = data.get('sub_type', '')
            _get_logger().info(f"[HTTP] [生命周期] {sub_type}")
        elif meta_event_type == 'heartbeat':
            status = data.get('status', {})
            interval = data.get('interval', 0)
            online = status.get('online', False) if isinstance(status, dict) else False
            _get_logger().debug(f"[HTTP] [心跳] 间隔:{interval}ms 在线:{online}")
        else:
            _get_logger().debug(f"[HTTP] [元事件] {meta_event_type}: {data}")
    
    async def _check_napcat_connection(self) -> bool:
        try:
            result = await self.get_status()
            if result is None:
                return False
            online = result.get('online', False)
            good = result.get('good', False)
            return online and good
        except Exception:
            return False
    
    async def disconnect(self):
        self.connected = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        _get_logger().info("[HTTP] 已断开连接")
    
    async def stop(self):
        await self.disconnect()
        
        if self._runner:
            await self._runner.cleanup()
            self._server_started = False
        
        if self.session:
            await self.session.close()
            self.session = None
    
    async def send(self, data: Any) -> bool:
        if not self.connected or not self.session:
            _get_logger().warning("[HTTP] 未连接或会话未初始化")
            return False
        
        try:
            if isinstance(data, dict):
                action = data.get('action')
                params = data.get('params', {})
                
                if action:
                    result = await self.call_api(action, params)
                    return result is not None and result.get('status') == 'ok'
            
            return False
        except Exception as e:
            _get_logger().error(f"[HTTP] 发送数据失败: {e}")
            return False
    
    async def receive(self) -> Optional[Dict[str, Any]]:
        return None
    
    async def call_api(self, action: str, params: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        if not self.session:
            _get_logger().warning("[HTTP] 会话未初始化")
            return None
        
        params = params or {}
        try:
            url = f"{self.api_url}/{action}"
            async with self.session.post(
                url, 
                json=params, 
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    _get_logger().warning(f"[HTTP] API调用失败: {action} HTTP {response.status}")
                    return None
                
                result = await response.json()
                retcode = result.get('retcode', 0)
                status = result.get('status', 'ok' if retcode == 0 else 'failed')
                
                if status == 'failed':
                    error_msg = result.get('wording', '') or result.get('message', '未知错误')
                    _get_logger().warning(f"[HTTP] API调用失败: {action} retcode={retcode} {error_msg}")
                
                return {
                    'status': status, 
                    'retcode': retcode, 
                    'data': result.get('data'), 
                    'echo': None
                }
                
        except aiohttp.ClientConnectorError as e:
            _get_logger().error(f"[HTTP] 连接NapCat失败: {e}")
            return None
        except aiohttp.ClientError as e:
            _get_logger().error(f"[HTTP] API调用异常: {e}")
            return None
        except asyncio.TimeoutError:
            _get_logger().warning(f"[HTTP] API调用超时: {action}")
            return None
        except Exception as e:
            _get_logger().error(f"[HTTP] API调用未知错误: {e}")
            return None
    
    async def send_message(self, message_type: str, user_id: int, group_id: Optional[int] = None, message: Any = '') -> bool:
        params = {
            'message_type': message_type,
            'message': self._format_message_content(message)
        }
        if message_type == 'group' and group_id:
            params['group_id'] = group_id
        elif message_type == 'private':
            params['user_id'] = user_id
        
        result = await self.call_api('send_msg', params)
        
        if result and result.get('status') == 'ok':
            data = result.get('data', {})
            msg_id = data.get('message_id', '')
            if message_type == 'group':
                _get_logger().info(f"[HTTP] -> [群:{group_id}]: {message} (msg_id:{msg_id})")
            else:
                _get_logger().info(f"[HTTP] -> [私聊:{user_id}]: {message} (msg_id:{msg_id})")
            return True
        return False
    
    async def bot_exit(self) -> bool:
        result = await self.call_api('bot_exit', {})
        return result is not None and result.get('status') == 'ok'
    
    async def get_login_info(self) -> Optional[Dict[str, Any]]:
        result = await self.call_api('get_login_info', {})
        return result.get('data') if result and result.get('status') == 'ok' else None
    
    async def get_status(self) -> Optional[Dict[str, Any]]:
        result = await self.call_api('get_status', {})
        return result.get('data') if result and result.get('status') == 'ok' else None
    
    async def get_version_info(self) -> Optional[Dict[str, Any]]:
        result = await self.call_api('get_version_info', {})
        return result.get('data') if result and result.get('status') == 'ok' else None
    
    def _format_message_content(self, message: Any) -> Any:
        if isinstance(message, str) and message.startswith(('base64://', 'data:', 'file://')):
            return message
        return message
    
    async def _heartbeat_loop(self):
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(30)
                if self._stop_event.is_set():
                    break
                
                napcat_ok = await self._check_napcat_connection()
                if napcat_ok:
                    if not self.connected:
                        self.connected = True
                        _get_logger().success(f"[HTTP] NapCat API连接恢复: {self.api_url}")
                else:
                    if self.connected:
                        _get_logger().warning("[HTTP] NapCat心跳失败，API未响应")
                        self.connected = False
                    
                    if self.auto_reconnect:
                        asyncio.create_task(self._reconnect_loop())
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                _get_logger().error(f"[HTTP] 心跳错误: {e}")
    
    def _get_headers(self) -> Dict[str, str]:
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Starrain-BOT/1.0'
        }
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        return headers
    
    async def _reconnect_loop(self):
        while not self.connected and not self._stop_event.is_set():
            if self.reconnect_count >= self.max_reconnect_attempts and self.max_reconnect_attempts != -1:
                _get_logger().warning(f"[HTTP] 已达最大重连次数: {self.max_reconnect_attempts}")
                break
            
            self.reconnect_count += 1
            _get_logger().info(f"[HTTP] 重连中... ({self.reconnect_count}/{self.max_reconnect_attempts})")
            
            await asyncio.sleep(self.reconnect_interval / 1000)
            
            try:
                napcat_ok = await self._check_napcat_connection()
                if napcat_ok:
                    self.connected = True
                    self.reconnect_count = 0
                    _get_logger().success(f"[HTTP] 重连成功: {self.api_url}")
                    break
            except Exception as e:
                _get_logger().error(f"[HTTP] 重连失败: {e}")

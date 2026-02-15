import asyncio
import aiohttp
from aiohttp import web
from typing import Dict, Any, Optional
from .base import BaseAdapter
from src.utils.logger import get_logger

def _get_logger():
    return get_logger()


class HTTPAdapter(BaseAdapter):
    """HTTP适配器 (支持HTTP POST上报)"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = config.get('http_url', 'http://localhost:3000')
        self.access_token = config.get('access_token', '')
        
        # HTTP POST上报服务器配置
        self.post_port = config.get('http_post_port', 5700)
        self.post_host = config.get('http_post_host', '0.0.0.0')
        self.post_secret = config.get('http_post_secret', '')
        
        self.session: Optional[aiohttp.ClientSession] = None
        self._heartbeat_task = None
        self._server: Optional[web.AppRunner] = None
    
    async def connect(self) -> bool:
        try:
            # 初始化HTTP客户端（用于调用API）
            self.session = aiohttp.ClientSession(
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=30)
            )
            
            # 启动HTTP POST上报服务器
            self._runner = web.AppRunner(self._create_app())
            await self._runner.setup()
            site = web.TCPSite(self._runner, self.post_host, self.post_port)
            
            try:
                await site.start()
                self.connected = True
                _get_logger().success(f"HTTP API初始化成功: {self.api_url}")
                _get_logger().success(f"HTTP POST上报服务器启动成功: http://{self.post_host}:{self.post_port}")
                
                # 启动心跳检查
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                
                return True
            except Exception as e:
                _get_logger().error(f"HTTP POST服务器启动失败: {e}")
                await self._runner.cleanup()
                return False
                
        except Exception as e:
            _get_logger().error(f"HTTP初始化失败: {e}")
            self.connected = False
            
            if self.auto_reconnect:
                asyncio.create_task(self._reconnect_loop())
            
            return False
    
    async def disconnect(self):
        self.connected = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if hasattr(self, '_runner') and self._runner:
            await self._runner.cleanup()
        
        if self.session:
            await self.session.close()
            self.session = None
        
        _get_logger().info("HTTP已断开连接")
    
    async def send(self, data: Any) -> bool:
        if not self.connected or not self.session:
            _get_logger().warning("HTTP未初始化")
            return False
        
        try:
            if isinstance(data, dict):
                action = data.get('action')
                params = data.get('params', {})
                
                if action and params:
                    msg_detail = self._format_message(action, params)
                    _get_logger().info(f"HTTP发送{action}: {msg_detail}")
                    result = await self.call_api(action, params)
                    return result is not None
            
            return False
        except Exception as e:
            _get_logger().error(f"HTTP发送数据失败: {e}")
            return False
    
    async def receive(self) -> Optional[Dict[str, Any]]:
        return None
    
    def _create_app(self):
        app = web.Application()
        app.router.add_post('/', self._handle_event)
        return app
    
    async def _handle_event(self, request):
        try:
            # 验证X-Self-ID（可选）
            self_id = request.headers.get('X-Self-ID')
            if self_id and int(self_id) != self.config.get('qq', 0):
                return web.Response(status=403, text="Wrong self_id")
            
            # 验证签名
            sig = request.headers.get('X-Signature', '')
            if self.post_secret:
                body = await request.read()
                import hmac
                import hashlib
                computed_sig = 'sha1=' + hmac.new(
                    self.post_secret.encode(),
                    body,
                    hashlib.sha1
                ).hexdigest()
                if sig != computed_sig:
                    return web.Response(status=401, text="Invalid signature")
                event_data = await request.json()
            else:
                event_data = await request.json()
            
            # 异步处理事件
            asyncio.create_task(self._process_event(event_data))
            
            return web.Response(text="OK", status=200)
        except Exception as e:
            _get_logger().error(f"HTTP POST事件处理错误: {e}")
            return web.Response(text="Internal Server Error", status=500)
    
    async def _process_event(self, event_data: Dict[str, Any]):
        try:
            await self.emit_event(event_data)
        except Exception as e:
            _get_logger().error(f"事件处理错误: {e}")
    
    async def call_api(self, action: str, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        if not self.session:
            _get_logger().error("HTTP会话未初始化")
            return None
        
        params = params or {}
        try:
            url = f"{self.api_url}/{action}"
            async with self.session.post(url, json=params) as response:
                result = await response.json()
                retcode = result.get('retcode', 0)
                status = result.get('status', 'ok' if retcode == 0 else 'failed')
                
                if status == 'failed':
                    error_msg = result.get('wording', '') or result.get('data', '未知错误')
                    _get_logger().warning(f"HTTP API 调用失败: {action}, retcode={retcode}, {error_msg}")
                
                return {'status': status, 'retcode': retcode, 'data': result.get('data'), 'echo': None}
        except Exception as e:
            _get_logger().error(f"API调用错误 {action}: {e}")
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
        return result is not None and result.get('status') == 'ok'
    
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
        while self.connected and not self._stop_event.is_set():
            try:
                await asyncio.sleep(30)
                status = await self.get_status()
                if not status:
                    _get_logger().warning("HTTP心跳失败，尝试重连...")
                    if self.auto_reconnect:
                        await self._reconnect()
            except Exception as e:
                _get_logger().error(f"HTTP心跳错误: {e}")
    
    async def _reconnect(self):
        await self.disconnect()
        await asyncio.sleep(1)
        return await self.connect()
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {}
        if self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        return headers
    
    def _format_message(self, action: str, params: Dict[str, Any]) -> str:
        """格式化消息内容用于日志显示"""
        if action == 'send_msg':
            message_type = params.get('message_type', '')
            user_id = params.get('user_id', 0)
            group_id = params.get('group_id', 0)
            message = params.get('message', '')
            
            if isinstance(message, list):
                msg_text = '[消息段]'
            else:
                msg_text = str(message)
            
            if message_type == 'group':
                return f"[群:{group_id}] - {msg_text}"
            elif message_type == 'private':
                return f"[私聊] QQ:{user_id} - {msg_text}"
            else:
                return f"{msg_text}"
        
        elif action == 'send_group_msg':
            group_id = params.get('group_id', 0)
            message = params.get('message', '')
            
            if isinstance(message, list):
                msg_text = '[消息段]'
            else:
                msg_text = str(message)
            
            return f"[群:{group_id}] - {msg_text}"
        
        elif action == 'send_private_msg':
            user_id = params.get('user_id', 0)
            message = params.get('message', '')
            
            if isinstance(message, list):
                msg_text = '[消息段]'
            else:
                msg_text = str(message)
            
            return f"[私聊] QQ:{user_id} - {msg_text}"
        
        return str(params)
    
    async def _reconnect_loop(self):
        while not self.connected and not self._stop_event.is_set():
            if self.reconnect_count >= self.max_reconnect_attempts and self.max_reconnect_attempts != -1:
                _get_logger().warning("HTTP已达到最大重连次数")
                break
            
            self.reconnect_count += 1
            _get_logger().info(f"HTTP正在重连... ({self.reconnect_count}/{self.max_reconnect_attempts})")
            
            await asyncio.sleep(self.reconnect_interval / 1000)
            await self._reconnect()

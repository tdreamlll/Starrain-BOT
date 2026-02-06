import asyncio
import aiohttp
from typing import Dict, Any, Optional
from .base import BaseAdapter


class HTTPAdapter(BaseAdapter):
    """HTTP适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = config.get('http_url', 'http://localhost:3000')
        self.access_token = config.get('access_token', '')
        self.session: Optional[aiohttp.ClientSession] = None
        self._poll_task = None
        self.last_event_id = None
    
    async def connect(self) -> bool:
        """连接（HTTP不需要连接）"""
        try:
            self.session = aiohttp.ClientSession(
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=30)
            )
            self.connected = True
            print(f"✓ HTTP初始化成功: {self.url}")
            
            # 启动轮询
            self._poll_task = asyncio.create_task(self._poll_loop())
            
            return True
        except Exception as e:
            print(f"[HTTP] ✗ 连接失败: {e}")
            self.connected = False
            
            # 如果启用了自动重连，启动重连任务
            if self.auto_reconnect:
                asyncio.create_task(self._reconnect_loop())
            
            return False
    
    async def disconnect(self):
        """断开连接"""
        self.connected = False
        
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        
        if self.session:
            await self.session.close()
            self.session = None
        
        print(f"[HTTP] 会话已关闭")
    
    async def send(self, data: Any) -> bool:
        """发送数据"""
        if not self.connected or not self.session:
            print(f"[HTTP] 未初始化")
            return False
        
        try:
            if isinstance(data, dict):
                action = data.get('action')
                params = data.get('params', {})
                
                if action and params:
                    msg_detail = self._format_message(action, params)
                    print(f"[HTTP] 发送{action}: {msg_detail}")
                    result = await self.call_api(action, params)
                    return result is not None
            
            return False
        except Exception as e:
            print(f"[HTTP] 发送数据失败: {e}")
            return False
    
    async def receive(self) -> Optional[Dict[str, Any]]:
        """接收数据（通过轮询）"""
        return None
    
    async def call_api(self, action: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """调用API"""
        try:
            async with self.session.post(
                f"{self.url}/{action}",
                json=params
            ) as response:
                result = await response.json()
                if result.get('retcode') == 0:
                    return result.get('data')
                else:
                    print(f"API调用失败: {result}")
                    return None
        except Exception as e:
            print(f"API调用错误: {e}")
            return None
    
    async def _poll_loop(self):
        """轮询事件"""
        while self.connected and not self._stop_event.is_set():
            try:
                await asyncio.sleep(1)
            except Exception as e:
                print(f"[HTTP] 轮询错误: {e}")
                await asyncio.sleep(1)
    
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
        """重连循环（用于初始连接失败后）"""
        while not self.connected and not self._stop_event.is_set():
            try:
                if self.reconnect_count >= self.max_reconnect_attempts and self.max_reconnect_attempts != -1:
                    print(f"[HTTP] 已达到最大重连次数，停止重连")
                    break
                
                self.reconnect_count += 1
                print(f"[HTTP] 正在重连... ({self.reconnect_count}/{self.max_reconnect_attempts})")
                
                await asyncio.sleep(self.reconnect_interval / 1000)
                
                # 尝试重新连接
                try:
                    self.session = aiohttp.ClientSession(
                        headers=self._get_headers(),
                        timeout=aiohttp.ClientTimeout(total=30)
                    )
                    self.connected = True
                    print(f"[HTTP] ✓ 重连成功")
                    
                    # 启动轮询
                    self._poll_task = asyncio.create_task(self._poll_loop())
                    
                    self.reconnect_count = 0
                    break
                except Exception as e:
                    print(f"[HTTP] 重连失败: {e}")
                    
            except Exception as e:
                print(f"[HTTP] 重连循环错误: {e}")
                await asyncio.sleep(1)

import asyncio
import websockets
import json
from typing import Dict, Any, Optional
from .base import BaseAdapter
from src.utils.logger import get_logger

def _get_logger():
    return get_logger()


class WebSocketAdapter(BaseAdapter):
    """正向WS适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = config.get('url', 'ws://localhost:3001')
        self.access_token = config.get('access_token', '')
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._receive_task = None
    
    async def connect(self) -> bool:
        """连接"""
        try:
            headers = {}
            if self.access_token:
                headers['Authorization'] = f'Bearer {self.access_token}'
            
            _get_logger().info(f"WS正在连接 {self.url}...")
            self.websocket = await websockets.connect(
                self.url,
                additional_headers=headers,
                ping_interval=None,
                close_timeout=10
            )
            
            self.connected = True
            _get_logger().success("WS已连接")
            
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            return True
            
        except Exception as e:
            _get_logger().error(f"WS连接失败: {e}")
            self.connected = False
            
            # 如果启用了自动重连，启动重连任务
            if self.auto_reconnect:
                asyncio.create_task(self._reconnect_loop())
            
            return False
    
    async def disconnect(self):
        """断开连接"""
        self.connected = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        _get_logger().info("WS连接已断开")
    
    async def send(self, data: Any) -> bool:
        """发送数据"""
        if not self.connected or not self.websocket:
            _get_logger().warning("WS未连接")
            return False
        
        try:
            if isinstance(data, dict):
                data = json.dumps(data)
            
            await self.websocket.send(data)
            return True
        except Exception as e:
            _get_logger().error(f"WS发送数据失败: {e}")
            return False
    
    async def receive(self) -> Optional[Dict[str, Any]]:
        """接收数据"""
        if not self.connected or not self.websocket:
            return None
        
        try:
            message = await self.websocket.recv()
            return json.loads(message)
        except Exception as e:
            return None
    
    async def _receive_loop(self):
        """接收循环"""
        while self.connected and not self._stop_event.is_set():
            try:
                data = await self.receive()
                if data:
                    post_type = data.get('post_type', 'unknown')
                    msg_detail = self._format_message(data)
                    print(f"[WS] 收到{post_type}: {msg_detail}")
                    await self.emit_event(data)
            except websockets.exceptions.ConnectionClosed:
                print(f"[WS] 连接已关闭")
                self.connected = False
                if self.auto_reconnect:
                    print(f"[WS] 自动重连...")
                    # 使用自定义重连循环，避免递归深度过大
                    asyncio.create_task(self._reconnect_loop_from_disconnect())
                break
            except Exception as e:
                print(f"[WS] 接收循环错误: {e}")
                await asyncio.sleep(1)
    
    def _format_message(self, data: Dict[str, Any]) -> str:
        """格式化消息内容用于日志显示"""
        post_type = data.get('post_type', 'unknown')
        
        if post_type == 'message':
            message_type = data.get('message_type', '')
            user_id = data.get('user_id', 0)
            group_id = data.get('group_id', 0)
            raw_message = data.get('raw_message', '')
            
            if message_type == 'group':
                return f"[群:{group_id}] QQ:{user_id} - {raw_message}"
            elif message_type == 'private':
                return f"[私聊] QQ:{user_id} - {raw_message}"
            else:
                return f"{raw_message}"
        
        elif post_type == 'notice':
            notice_type = data.get('notice_type', '')
            return f"通知:{notice_type}"
        
        elif post_type == 'request':
            request_type = data.get('request_type', '')
            return f"请求:{request_type}"
        
        elif post_type == 'meta_event':
            meta_event_type = data.get('meta_event_type', '')
            return f"元事件:{meta_event_type}"
        
        return str(data)
    
    async def _reconnect_loop(self):
        """重连循环（用于初始连接失败后）"""
        while not self.connected and not self._stop_event.is_set():
            try:
                if self.reconnect_count >= self.max_reconnect_attempts and self.max_reconnect_attempts != -1:
                    print(f"[WebsocketAdapter] 已达到最大重连次数，停止重连")
                    break
                
                self.reconnect_count += 1
                print(f"[WebsocketAdapter] 正在重连... ({self.reconnect_count}/{self.max_reconnect_attempts})")
                
                await asyncio.sleep(self.reconnect_interval / 1000)
                
                # 尝试重新连接
                try:
                    headers = {}
                    if self.access_token:
                        headers['Authorization'] = f'Bearer {self.access_token}'
                    
                    print(f"[WS] 正在连接 {self.url}...")
                    self.websocket = await websockets.connect(
                        self.url,
                        additional_headers=headers,
                        ping_interval=None,
                        close_timeout=10
                    )
                    
                    self.connected = True
                    print(f"[WS] ✓ 连接成功")
                    
                    # 启动接收循环
                    self._receive_task = asyncio.create_task(self._receive_loop())
                    
                    self.reconnect_count = 0
                    break
                except Exception as e:
                    print(f"[WS] 重连失败: {e}")
                    
            except Exception as e:
                print(f"[WebsocketAdapter] 重连循环错误: {e}")
                await asyncio.sleep(1)
    
    async def _reconnect_loop_from_disconnect(self):
        """重连循环（用于连接断开后）"""
        while not self.connected and not self._stop_event.is_set():
            if self.reconnect_count >= self.max_reconnect_attempts and self.max_reconnect_attempts != -1:
                print(f"[WebsocketAdapter] 已达到最大重连次数，停止重连")
                break
            
            self.reconnect_count += 1
            print(f"[WebsocketAdapter] 正在重连... ({self.reconnect_count}/{self.max_reconnect_attempts})")
            
            try:
                await asyncio.sleep(self.reconnect_interval / 1000)
                
                # 尝试重新连接
                headers = {}
                if self.access_token:
                    headers['Authorization'] = f'Bearer {self.access_token}'
                
                print(f"[WS] 正在连接 {self.url}...")
                self.websocket = await websockets.connect(
                    self.url,
                    additional_headers=headers,
                    ping_interval=None,
                    close_timeout=10
                )
                
                self.connected = True
                print(f"[WS] ✓ 连接成功")
                
                # 启动接收循环
                self._receive_task = asyncio.create_task(self._receive_loop())
                
                self.reconnect_count = 0
                print(f"[WebsocketAdapter] 重连成功")
                break
            except Exception as e:
                print(f"[WS] 重连失败: {e}")
                continue

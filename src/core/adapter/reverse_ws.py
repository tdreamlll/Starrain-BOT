import asyncio
import websockets
import json
from typing import Dict, Any, Optional
from .base import BaseAdapter
from src.utils.logger import get_logger

def _get_logger():
    return get_logger()


class ReverseWebSocketAdapter(BaseAdapter):
    """反向WS适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = config.get('reverse_ws_url', 'ws://localhost:3002')
        self.urls = [u.strip() for u in self.url.split(',') if u.strip()]
        self.access_token = config.get('access_token', '')
        self.server = None
        self.clients = set()
    
    async def connect(self) -> bool:
        """启动反向WS服务器"""
        try:
            async for client in websockets.serve(
                self._handle_client,
                port=3002,
                ping_interval=None
            ):
                pass
            return True
        except Exception as e:
            _get_logger().error(f"反向WS启动失败: {e}")
            return False
    
    async def disconnect(self):
        """断开所有客户端连接"""
        self.connected = False
        for client in self.clients:
            await client.close()
        self.clients.clear()
        _get_logger().info("反向WS已停止")
    
    async def send(self, data: Any) -> bool:
        """发送数据到所有客户端"""
        if not self.clients:
            _get_logger().warning("反向WS没有连接的客户端")
            return False
        
        try:
            if isinstance(data, dict):
                data = json.dumps(data)
            
            # 发送到所有连接的客户端
            disconnected = set()
            for client in self.clients:
                try:
                    await client.send(data)
                except Exception:
                    disconnected.add(client)
            
            # 移除断开的客户端
            self.clients -= disconnected
            
            return True
        except Exception as e:
            _get_logger().error(f"反向WS发送数据失败: {e}")
            return False
    
    async def receive(self) -> Optional[Dict[str, Any]]:
        """接收数据 (不适用，通过回调处理)"""
        return None
    
    async def _handle_client(self, websocket, path):
        """处理客户端连接"""
        client_addr = websocket.remote_address
        _get_logger().info(f"反向WS新客户端连接: {client_addr}")
        self.clients.add(websocket)
        self.connected = True
        _get_logger().success("反向WS已连接")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    post_type = data.get('post_type', 'unknown')
                    msg_detail = self._format_message(data)
                    _get_logger().info(f"反向WS收到{post_type}: {msg_detail}")
                    await self.emit_event(data)
                except json.JSONDecodeError as e:
                    _get_logger().error(f"反向WS JSON解析错误: {e}")
        except websockets.exceptions.ConnectionClosed:
            _get_logger().info(f"反向WS客户端断开连接: {client_addr}")
        except Exception as e:
            _get_logger().error(f"反向WS客户端处理错误: {e}")
        finally:
            self.clients.discard(websocket)
            if not self.clients:
                self.connected = False
                _get_logger().info("反向WS所有客户端已断开")
    
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
    
    async def start_server(self):
        """启动服务器"""
        _get_logger().info("反向WS正在启动服务器，监听端口: 3002...")
        _get_logger().info("反向WS等待客户端连接...")
        await self.connect()

import asyncio
import websockets
from websockets.client import connect as ws_connect, WebSocketClientProtocol
from websockets.exceptions import ConnectionClosed
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
        self.websocket: Optional[WebSocketClientProtocol] = None
        self._receive_task = None
    
    async def connect(self) -> bool:
        """连接"""
        try:
            headers = {}
            if self.access_token:
                headers['Authorization'] = f'Bearer {self.access_token}'
            
            _get_logger().info(f"WS正在连接 {self.url}...")
            self.websocket = await ws_connect(
                self.url,
                extra_headers=headers,
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
                    if 'echo' in data:
                        self.handle_api_response(data)
                        continue
                    
                    post_type = data.get('post_type')
                    if post_type:
                        msg_detail = self._format_message(data)
                        print(f"[WS] 收到{post_type}: {msg_detail}")
                        await self.emit_event(data)
            except ConnectionClosed:
                print(f"[WS] 连接已关闭")
                self.connected = False
                if self.auto_reconnect:
                    print(f"[WS] 自动重连...")
                    asyncio.create_task(self._reconnect_loop_from_disconnect())
                break
            except Exception as e:
                print(f"[WS] 接收循环错误: {e}")
                await asyncio.sleep(1)
    
    def _format_message(self, data: Dict[str, Any]) -> str:
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
        
        elif post_type == 'message_sent':
            message_type = data.get('message_type', '')
            user_id = data.get('user_id', 0)
            group_id = data.get('group_id', 0)
            raw_message = data.get('raw_message', '')
            
            if message_type == 'group':
                return f"[已发送群:{group_id}] QQ:{user_id} - {raw_message}"
            elif message_type == 'private':
                return f"[已发送私聊] QQ:{user_id} - {raw_message}"
            else:
                return f"[已发送]{raw_message}"
        
        elif post_type == 'notice':
            return self._format_notice(data)
        
        elif post_type == 'request':
            request_type = data.get('request_type', '')
            return f"请求:{request_type}"
        
        elif post_type == 'meta_event':
            meta_event_type = data.get('meta_event_type', '')
            return f"元事件:{meta_event_type}"
        
        return str(data)
    
    def _format_notice(self, data: Dict[str, Any]) -> str:
        notice_type = data.get('notice_type', '')
        group_id = data.get('group_id', 0)
        user_id = data.get('user_id', 0)
        sub_type = data.get('sub_type', '')
        
        if notice_type == 'group_upload':
            file_info = data.get('file', {})
            file_name = file_info.get('name', '未知文件')
            return f"[群:{group_id}] 文件上传: {file_name} (QQ:{user_id})"
        
        elif notice_type == 'group_admin':
            action = "设为管理员" if sub_type == 'set' else "取消管理员"
            return f"[群:{group_id}] {action}: QQ:{user_id}"
        
        elif notice_type == 'group_decrease':
            if sub_type == 'leave':
                return f"[群:{group_id}] 成员退群: QQ:{user_id}"
            elif sub_type == 'kick':
                operator_id = data.get('operator_id', 0)
                return f"[群:{group_id}] 成员被踢: QQ:{user_id} (操作者:{operator_id})"
            elif sub_type == 'kick_me':
                return f"[群:{group_id}] 机器人被踢出"
            return f"[群:{group_id}] 成员减少: QQ:{user_id}"
        
        elif notice_type == 'group_increase':
            operator_id = data.get('operator_id', 0)
            way = "同意入群" if sub_type == 'approve' else "邀请入群"
            return f"[群:{group_id}] 新成员{way}: QQ:{user_id} (操作者:{operator_id})"
        
        elif notice_type == 'group_ban':
            duration = data.get('duration', 0)
            operator_id = data.get('operator_id', 0)
            if sub_type == 'ban':
                return f"[群:{group_id}] 禁言: QQ:{user_id} {duration}秒 (操作者:{operator_id})"
            else:
                return f"[群:{group_id}] 解除禁言: QQ:{user_id} (操作者:{operator_id})"
        
        elif notice_type == 'friend_add':
            return f"新增好友: QQ:{user_id}"
        
        elif notice_type == 'group_recall':
            operator_id = data.get('operator_id', 0)
            message_id = data.get('message_id', 0)
            return f"[群:{group_id}] 消息撤回: QQ:{user_id} (操作者:{operator_id}) msg_id:{message_id}"
        
        elif notice_type == 'friend_recall':
            message_id = data.get('message_id', 0)
            return f"好友消息撤回: QQ:{user_id} msg_id:{message_id}"
        
        elif notice_type == 'notify':
            target_id = data.get('target_id', 0)
            if sub_type == 'poke':
                return f"[群:{group_id}] 戳一戳: QQ:{user_id} -> QQ:{target_id}"
            elif sub_type == 'lucky_king':
                return f"[群:{group_id}] 红包运气王: QQ:{target_id}"
            elif sub_type == 'honor':
                honor_type = data.get('honor_type', '')
                honor_names = {'talkative': '龙王', 'performer': '群聊之火', 'emotion': '快乐源泉'}
                honor_name = honor_names.get(honor_type, honor_type)
                return f"[群:{group_id}] 荣誉变更: QQ:{user_id} 获得{honor_name}"
            return f"[群:{group_id}] 通知: {sub_type}"
        
        return f"通知:{notice_type}"
    
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
                    self.websocket = await ws_connect(
                        self.url,
                        extra_headers=headers,
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
                self.websocket = await ws_connect(
                    self.url,
                    extra_headers=headers,
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

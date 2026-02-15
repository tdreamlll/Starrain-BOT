import asyncio
import websockets
from websockets.server import serve
from websockets.exceptions import ConnectionClosed
import json
from typing import Dict, Any, Optional, Set
from urllib.parse import urlparse
from .base import BaseAdapter
from src.utils.logger import get_logger

def _get_logger():
    return get_logger()


class ReverseWebSocketAdapter(BaseAdapter):
    """反向WS适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.url = config.get('reverse_ws_url', 'ws://0.0.0.0:3002')
        self.access_token = config.get('access_token', '')
        self.server = None
        self.clients: Dict[str, Set] = {
            'api': set(),
            'event': set(),
            'universal': set()
        }
        self._self_id_map: Dict = {}
    
    def _parse_url(self) -> tuple:
        parsed = urlparse(self.url)
        host = parsed.hostname or '0.0.0.0'
        port = parsed.port or 3002
        return host, port
    
    async def connect(self) -> bool:
        """启动反向WS服务器"""
        try:
            host, port = self._parse_url()
            self.server = await serve(
                self._handle_client,
                host=host,
                port=port,
                ping_interval=None
            )
            _get_logger().info(f"反向WS服务器已启动: {host}:{port}")
            return True
        except Exception as e:
            _get_logger().error(f"反向WS启动失败: {e}")
            return False
    
    async def disconnect(self):
        """断开所有客户端连接"""
        self.connected = False
        for client_type in self.clients:
            for client in self.clients[client_type]:
                await client.close()
            self.clients[client_type].clear()
        self._self_id_map.clear()
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        _get_logger().info("反向WS已停止")
    
    async def send(self, data: Any) -> bool:
        """发送数据到所有Universal和API客户端"""
        targets = self.clients['universal'] | self.clients['api']
        if not targets:
            _get_logger().warning("反向WS没有可用的API客户端")
            return False
        
        try:
            if isinstance(data, dict):
                data = json.dumps(data)
            
            disconnected = set()
            for client in targets:
                try:
                    await client.send(data)
                except Exception:
                    disconnected.add(client)
            
            for client in disconnected:
                self._remove_client(client)
            
            return True
        except Exception as e:
            _get_logger().error(f"反向WS发送数据失败: {e}")
            return False
    
    async def receive(self) -> Optional[Dict[str, Any]]:
        """接收数据 (不适用，通过回调处理)"""
        return None
    
    def _validate_client(self, websocket, path: str) -> tuple:
        headers = dict(websocket.request_headers)
        
        self_id = headers.get('X-Self-ID', '')
        client_role = headers.get('X-Client-Role', 'Universal').lower()
        auth_header = headers.get('Authorization', '')
        
        if self.access_token:
            if not auth_header:
                _get_logger().warning(f"反向WS客户端缺少Authorization头")
                return None, None, None
            
            token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else auth_header
            if token != self.access_token:
                _get_logger().warning(f"反向WS客户端access_token验证失败")
                return None, None, None
        
        if client_role not in ('api', 'event', 'universal'):
            client_role = 'universal'
        
        if path.rstrip('/') == '/api':
            client_role = 'api'
        elif path.rstrip('/') == '/event':
            client_role = 'event'
        
        return self_id, client_role, path
    
    def _remove_client(self, websocket):
        for client_type in self.clients:
            self.clients[client_type].discard(websocket)
        for self_id in list(self._self_id_map.keys()):
            if self._self_id_map[self_id] == websocket:
                del self._self_id_map[self_id]
    
    async def _handle_client(self, websocket, path: str):
        """处理客户端连接"""
        self_id, client_role, client_path = self._validate_client(websocket, path)
        
        if client_role is None:
            await websocket.close(code=1008, reason="Unauthorized")
            return
        
        client_addr = websocket.remote_address
        _get_logger().info(f"反向WS新客户端连接: {client_addr}, Self-ID: {self_id}, Role: {client_role}, Path: {path}")
        
        self.clients[client_role].add(websocket)
        if self_id:
            self._self_id_map[self_id] = websocket
        
        if self.clients['universal'] or self.clients['api']:
            self.connected = True
        _get_logger().success(f"反向WS已连接 ({client_role})")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if 'echo' in data:
                        self.handle_api_response(data)
                        continue
                    
                    post_type = data.get('post_type')
                    if post_type:
                        msg_detail = self._format_message(data)
                        _get_logger().info(f"反向WS收到{post_type}: {msg_detail}")
                        await self.emit_event(data)
                except json.JSONDecodeError as e:
                    _get_logger().error(f"反向WS JSON解析错误: {e}")
        except ConnectionClosed:
            _get_logger().info(f"反向WS客户端断开连接: {client_addr}")
        except Exception as e:
            _get_logger().error(f"反向WS客户端处理错误: {e}")
        finally:
            self._remove_client(websocket)
            if not (self.clients['universal'] or self.clients['api']):
                self.connected = False
                _get_logger().info("反向WS所有API客户端已断开")
    
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
    
    async def start_server(self):
        """启动服务器"""
        host, port = self._parse_url()
        _get_logger().info(f"反向WS正在启动服务器，监听: {host}:{port}...")
        _get_logger().info("反向WS等待客户端连接...")
        await self.connect()

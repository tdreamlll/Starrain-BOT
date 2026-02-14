import asyncio
import time
from typing import Dict, Any, Optional, Callable
from .adapter import WebSocketAdapter, ReverseWebSocketAdapter, HTTPAdapter
from .permission import PermissionManager
from .plugin_manager import PluginManager
from ..utils.logger import get_logger
from ..utils.renderer import ImageRenderer
from ..utils.db import Database
from ..event import parse_event, Event


class Bot:
    """机器人核心类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._qq = config['bot']['qq']
        
        # 初始化各个组件
        self.logger = get_logger(config['log'])
        # 数据库：默认使用 save/bot.db
        self.db = Database()
        self.permission_manager = PermissionManager(config['permission'])
        self.plugin_manager = PluginManager(config['plugin'])
        self.renderer = ImageRenderer(config['renderer'])
        
        # 适配器
        self.adapters = []
        self._setup_adapters()
        
        # 事件处理器
        self._event_handlers = {
            'message': [],
            'message_sent': [],
            'group_message': [],
            'private_message': [],
            'notice': [],
            'request': [],
            'meta_event': [],
        }
        
        self._running = False
        self._start_time: Optional[float] = None
        self._restart_requested = False
        self._shutdown_requested = False

    @property
    def qq(self) -> int:
        return self._qq

    @property
    def uptime_seconds(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    def _setup_adapters(self):
        """设置适配器（只能启用一种连接方式）"""
        onebot_config = self.config['onebot']
        bot_config = self.config['bot']
        connection_type = onebot_config.get('connection_type', 'ws')
        
        self.logger.info(f"连接类型: {connection_type}")
        
        # 根据配置选择一种连接方式
        if connection_type == 'ws':
            # 正向WS
            self.logger.info("使用正向WebSocket连接")
            ws_adapter = WebSocketAdapter({
                **onebot_config,
                **bot_config
            })
            ws_adapter.on_event(self._handle_adapter_event)
            self.adapters.append(ws_adapter)
            
        elif connection_type == 'reverse_ws':
            # 反向WS
            self.logger.info("使用反向WebSocket连接")
            reverse_ws_adapter = ReverseWebSocketAdapter({
                **onebot_config,
                **bot_config
            })
            reverse_ws_adapter.on_event(self._handle_adapter_event)
            self.adapters.append(reverse_ws_adapter)
            
        elif connection_type == 'http':
            # HTTP
            self.logger.info("使用HTTP连接")
            http_adapter = HTTPAdapter({
                **onebot_config,
                **bot_config
            })
            http_adapter.on_event(self._handle_adapter_event)
            self.adapters.append(http_adapter)
            
        else:
            self.logger.warning(f"未知的连接类型: {connection_type}，默认使用WS")
            # 默认使用正向WS
            ws_adapter = WebSocketAdapter({
                **onebot_config,
                **bot_config
            })
            ws_adapter.on_event(self._handle_adapter_event)
            self.adapters.append(ws_adapter)
        
        self.logger.success(f"已启用的适配器数量: {len(self.adapters)}")
    
    async def _handle_adapter_event(self, event_data: Dict[str, Any]):
        """处理适配器事件"""
        try:
            event = parse_event(event_data)
            setattr(event, 'bot', self)

            if hasattr(event, 'group_id') and event.group_id:
                if self.permission_manager.is_group_blacklisted(event.group_id):
                    return

            group_role = None
            if hasattr(event, 'sender_role'):
                group_role = event.sender_role

            permission_level = self.permission_manager.check_permission(
                event.user_id,
                event.group_id if hasattr(event, 'group_id') else None,
                group_role
            )

            await self._dispatch_event(event, permission_level)
        except Exception as e:
            self.logger.error(f"事件处理错误: {e}")
    
    async def _dispatch_event(self, event: Event, permission_level):
        post_type = event.data.get('post_type', '')
        
        if post_type == 'message':
            if event.message_type == 'group':
                await self._emit('message', event, permission_level)
                await self._emit('group_message', event, permission_level)
            elif event.message_type == 'private':
                await self._emit('message', event, permission_level)
                await self._emit('private_message', event, permission_level)
        elif post_type == 'message_sent':
            if event.message_type == 'group':
                await self._emit('message', event, permission_level)
                await self._emit('group_message', event, permission_level)
            elif event.message_type == 'private':
                await self._emit('message', event, permission_level)
                await self._emit('private_message', event, permission_level)
        elif post_type == 'notice':
            await self._emit('notice', event, permission_level)
        elif post_type == 'request':
            await self._emit('request', event, permission_level)
        elif post_type == 'meta_event':
            await self._emit('meta_event', event, permission_level)
        
        await self.plugin_manager.dispatch_event(event.event_type, event, permission_level)
    
    async def _emit(self, event_type: str, *args, **kwargs):
        """触发事件"""
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    result = handler(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    self.logger.error(f"事件处理器错误: {e}")
    
    def on_message(self, handler: Callable):
        """注册消息事件处理器"""
        self._event_handlers['message'].append(handler)
    
    def on_group_message(self, handler: Callable):
        """注册群消息事件处理器"""
        self._event_handlers['group_message'].append(handler)
    
    def on_private_message(self, handler: Callable):
        """注册私聊消息事件处理器"""
        self._event_handlers['private_message'].append(handler)
    
    def on_notice(self, handler: Callable):
        """注册通知事件处理器"""
        self._event_handlers['notice'].append(handler)
    
    def on_request(self, handler: Callable):
        """注册请求事件处理器"""
        self._event_handlers['request'].append(handler)
    
    def on_meta_event(self, handler: Callable):
        """注册元事件处理器"""
        self._event_handlers['meta_event'].append(handler)
    
    def on_message_sent(self, handler: Callable):
        """注册消息发送事件处理器"""
        self._event_handlers['message_sent'].append(handler)
    
    async def send_message(self, message_type: str, user_id: int, 
                          group_id: Optional[int] = None, message: Any = '') -> bool:
        for adapter in self.adapters:
            if adapter.is_connected():
                return await adapter.send_message(message_type, user_id, group_id, message)
        return False
    
    async def send_group_message(self, group_id: int, message: Any) -> bool:
        """发送群消息"""
        return await self.send_message('group', 0, group_id, message)
    
    async def send_private_message(self, user_id: int, message: Any) -> bool:
        """发送私聊消息"""
        return await self.send_message('private', user_id, None, message)

    async def set_group_ban(self, group_id: int, user_id: int, duration: int = 60) -> bool:
        for adapter in self.adapters:
            if adapter.is_connected():
                if isinstance(adapter, HTTPAdapter):
                    result = await adapter.call_api('set_group_ban', {
                        'group_id': group_id,
                        'user_id': user_id,
                        'duration': duration,
                    })
                    if result is not None:
                        return True
                else:
                    return await adapter.send({
                        'action': 'set_group_ban',
                        'params': {'group_id': group_id, 'user_id': user_id, 'duration': duration},
                    })
        return False
    
    async def bot_exit(self) -> bool:
        for adapter in self.adapters:
            if adapter.is_connected():
                if isinstance(adapter, HTTPAdapter):
                    result = await adapter.call_api('bot_exit', {})
                    if result is not None:
                        return True
                else:
                    return await adapter.bot_exit()
        return False

    async def start(self):
        """启动机器人"""
        self._running = True
        self._start_time = time.time()
        self.logger.info(f"机器人启动中... QQ: {self.qq}")
        await asyncio.sleep(0.3)
        
        # 连接所有适配器
        for adapter in self.adapters:
            try:
                if isinstance(adapter, ReverseWebSocketAdapter):
                    # 反向WS需要单独启动服务器
                    asyncio.create_task(adapter.start_server())
                else:
                    success = await adapter.connect()
                    await asyncio.sleep(0.5)
                    if success:
                        self.logger.success(f"{adapter.__class__.__name__} 初始化完成")
                    else:
                        self.logger.error(f"{adapter.__class__.__name__} 连接失败")
            except Exception as e:
                self.logger.error(f"{adapter.__class__.__name__} 启动错误: {e}")
        
        self.logger.success("机器人启动完成")
    
    async def stop(self):
        """停止机器人"""
        self._running = False
        
        self.logger.info("正在停止机器人...")
        
        # 断开所有适配器
        for adapter in self.adapters:
            await adapter.stop()
        
        # 停止插件管理器
        self.plugin_manager.stop()
        
        # 关闭图片渲染器浏览器
        if hasattr(self.renderer, 'close_browser'):
            await self.renderer.close_browser()
        
        self.logger.success("机器人已停止")
    
    async def run(self):
        """运行机器人"""
        await self.start()
        
        try:
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.stop()
    
    def check_permission(self, qq: int, group_id: Optional[int] = None, 
                        group_role: Optional[str] = None):
        """检查权限"""
        return self.permission_manager.check_permission(qq, group_id, group_role)
    
    def is_admin(self, qq: int) -> bool:
        return self.permission_manager.is_admin(qq)

    def can_modify_user(
        self,
        modifier_qq: int,
        target_qq: int,
        modifier_group_id: Optional[int] = None,
        modifier_role: Optional[str] = None,
    ) -> bool:
        return self.permission_manager.can_modify_user(
            modifier_qq, target_qq, modifier_group_id, modifier_role
        )

    def get_user_level_without_group(self, qq: int):
        return self.permission_manager.get_level_without_group(qq)

    def is_group_admin(self, group_role: Optional[str] = None) -> bool:
        return self.permission_manager.is_group_staff(group_role)

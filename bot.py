import asyncio
from typing import Dict, Any, Optional, Callable
from ..core.adapter import WebSocketAdapter, ReverseWebSocketAdapter, HTTPAdapter
from ..core.permission import PermissionManager
from ..core.plugin_manager import PluginManager
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
        self.permission_manager = PermissionManager(config['permission'], self.db)
        self.plugin_manager = PluginManager(config['plugin'])
        self.renderer = ImageRenderer(config['renderer'])
        
        # 适配器
        self.adapters = []
        self._setup_adapters()
        
        # 事件处理器
        self._event_handlers = {
            'message': [],
            'group_message': [],
            'private_message': [],
            'notice': [],
            'request': [],
            'meta_event': [],
        }
        
        self._running = False
    
    @property
    def qq(self) -> int:
        return self._qq
    
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
            
            # 获取发送者信息（群角色）
            group_role = None
            if hasattr(event, 'sender_role'):
                group_role = event.sender_role
            
            # 检查权限
            permission_level = self.permission_manager.check_permission(
                event.user_id,
                event.group_id if hasattr(event, 'group_id') else None,
                group_role
            )
            
            # 分发事件
            await self._dispatch_event(event, permission_level)
        except Exception as e:
            self.logger.error(f"事件处理错误: {e}")
    
    async def _dispatch_event(self, event: Event, permission_level):
        """分发事件（优化版，减少asyncio调用）"""
        # 通用消息事件
        if event.event_type == 'message':
            if event.message_type == 'group':
                await self._emit('message', event, permission_level)
                await self._emit('group_message', event, permission_level)
            elif event.message_type == 'private':
                await self._emit('message', event, permission_level)
                await self._emit('private_message', event, permission_level)
        
        # 通知事件
        elif event.event_type == 'notice':
            await self._emit('notice', event, permission_level)
        
        # 请求事件
        elif event.event_type == 'request':
            await self._emit('request', event, permission_level)
        
        # 元事件
        elif event.event_type == 'meta_event':
            await self._emit('meta_event', event, permission_level)
        
        # 分发到插件（只分发给已启用的插件）
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
    
    async def send_message(self, message_type: str, user_id: int, 
                          group_id: Optional[int] = None, message: Any = '') -> bool:
        """发送消息"""
        params = {
            'message_type': message_type,
            'user_id': user_id,
            'message': message
        }
        
        if group_id and message_type == 'group':
            params['group_id'] = group_id
        
        # 尝试通过HTTP适配器发送
        for adapter in self.adapters:
            if isinstance(adapter, HTTPAdapter) and adapter.is_connected():
                result = await adapter.call_api('send_msg', params)
                return result is not None
        
        # 尝试通过WS适配器发送
        for adapter in self.adapters:
            if adapter.is_connected() and not isinstance(adapter, HTTPAdapter):
                return await adapter.send({
                    'action': 'send_msg',
                    'params': params
                })
        
        self.logger.warning("没有可用的适配器发送消息")
        return False
    
    async def send_group_message(self, group_id: int, message: Any) -> bool:
        """发送群消息"""
        return await self.send_message('group', 0, group_id, message)
    
    async def send_private_message(self, user_id: int, message: Any) -> bool:
        """发送私聊消息"""
        return await self.send_message('private', user_id, None, message)
    
    async def start(self):
        """启动机器人"""
        self._running = True
        self.logger.success(f"机器人启动中... QQ: {self.qq}")
        
        # 连接所有适配器
        for adapter in self.adapters:
            try:
                if isinstance(adapter, ReverseWebSocketAdapter):
                    # 反向WS需要单独启动服务器
                    asyncio.create_task(adapter.start_server())
                else:
                    success = await adapter.connect()
                    if success:
                        if isinstance(adapter, HTTPAdapter):
                            self.logger.success(f"✓ {adapter.__class__.__name__} 初始化完成")
                        else:
                            self.logger.success(f"✓ {adapter.__class__.__name__} 连接成功")
                    else:
                        self.logger.error(f"✗ {adapter.__class__.__name__} 连接失败")
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
        """是否是BOT管理员"""
        return self.permission_manager.is_admin(qq)
    
    def is_group_admin(self, group_role: Optional[str] = None) -> bool:
        """是否是群管理员"""
        return self.permission_manager.is_group_admin(group_role)

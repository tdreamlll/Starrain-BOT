import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Optional, Any, Dict
from src.utils.logger import get_logger

def _get_logger():
    return get_logger()


class BaseAdapter(ABC):
    """基础适配器抽象类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connected = False
        self.reconnect_count = 0
        self.max_reconnect_attempts = config.get('max_reconnect_attempts', 10)
        self.reconnect_interval = config.get('reconnect_interval', 5000)
        self.auto_reconnect = config.get('auto_reconnect', True)
        self._event_handlers = []
        self._stop_event = asyncio.Event()
        self.adapter_name = self.__class__.__name__
        self._echo_counter = 0
        self._pending_requests: Dict[Any, asyncio.Future] = {}
    
    @abstractmethod
    async def connect(self) -> bool:
        """连接"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        pass
    
    @abstractmethod
    async def send(self, data: Any) -> bool:
        pass
    
    async def send_message(self, message_type: str, user_id: int, group_id: Optional[int] = None, message: Any = '') -> bool:
        echo = self._get_next_echo()
        params = {'message_type': message_type, 'message': message}
        
        if message_type == 'group':
            if group_id:
                params['group_id'] = group_id
        elif message_type == 'private':
            params['user_id'] = user_id
        
        request = {'action': 'send_msg', 'params': params, 'echo': echo}
        return await self.send(request)
    
    async def call_api(self, action: str, params: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        echo = self._get_next_echo()
        request = {'action': action, 'params': params or {}, 'echo': echo}
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[echo] = future
        try:
            success = await self.send(request)
            if not success:
                _get_logger().warning(f"{self.adapter_name} API 请求发送失败: {action}")
                return None
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            _get_logger().warning(f"{self.adapter_name} API 调用超时: {action}")
            return None
        except Exception as e:
            _get_logger().error(f"{self.adapter_name} API 调用失败: {e}")
            return None
        finally:
            self._pending_requests.pop(echo, None)
    
    def _get_next_echo(self) -> int:
        self._echo_counter += 1
        return self._echo_counter
    
    def handle_api_response(self, response: Dict[str, Any]):
        echo = response.get('echo')
        if echo is not None and echo in self._pending_requests:
            future = self._pending_requests[echo]
            if not future.done():
                status = response.get('status', '')
                if status == 'failed':
                    retcode = response.get('retcode', 0)
                    data = response.get('data')
                    error_msg = data if isinstance(data, str) else response.get('wording', '未知错误')
                    _get_logger().warning(f"{self.adapter_name} API 调用失败: retcode={retcode}, {error_msg}")
                future.set_result(response)
    
    async def bot_exit(self) -> bool:
        echo = self._get_next_echo()
        return await self.send({'action': 'bot_exit', 'params': {}, 'echo': echo})
    
    @abstractmethod
    async def receive(self) -> Optional[Dict[str, Any]]:
        """接收数据"""
        pass
    
    def on_event(self, handler: Callable[[Dict[str, Any]], Any]):
        """注册事件处理器"""
        self._event_handlers.append(handler)
    
    async def emit_event(self, event_data: Dict[str, Any]):
        """触发事件"""
        for handler in self._event_handlers:
            try:
                result = handler(event_data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                _get_logger().error(f"事件处理错误: {e}")
    
    async def reconnect(self):
        """重连"""
        if self.reconnect_count >= self.max_reconnect_attempts and self.max_reconnect_attempts != -1:
            _get_logger().warning(f"{self.adapter_name}已达到最大重连次数: {self.max_reconnect_attempts}")
            return False
        
        self.reconnect_count += 1
        _get_logger().info(f"{self.adapter_name}正在重连... ({self.reconnect_count}/{self.max_reconnect_attempts})")
        
        try:
            await asyncio.sleep(self.reconnect_interval / 1000)
            success = await self.connect()
            if success:
                self.reconnect_count = 0
                _get_logger().success(f"{self.adapter_name}重连成功")
                return True
            else:
                return await self.reconnect()
        except Exception as e:
            _get_logger().error(f"{self.adapter_name}重连失败: {e}")
            return await self.reconnect()
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connected
    
    async def stop(self):
        """停止适配器"""
        self._stop_event.set()
        await self.disconnect()

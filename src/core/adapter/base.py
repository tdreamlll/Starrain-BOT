import asyncio
from abc import ABC, abstractmethod
from typing import Callable, Optional, Any, Dict


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
        """发送数据"""
        pass
    
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
                print(f"事件处理错误: {e}")
    
    async def reconnect(self):
        """重连"""
        if self.reconnect_count >= self.max_reconnect_attempts and self.max_reconnect_attempts != -1:
            print(f"[{self.adapter_name}] 已达到最大重连次数: {self.max_reconnect_attempts}")
            return False
        
        self.reconnect_count += 1
        print(f"[{self.adapter_name}] 正在重连... ({self.reconnect_count}/{self.max_reconnect_attempts})")
        
        try:
            await asyncio.sleep(self.reconnect_interval / 1000)
            success = await self.connect()
            if success:
                self.reconnect_count = 0
                print(f"[{self.adapter_name}] 重连成功")
                return True
            else:
                return await self.reconnect()
        except Exception as e:
            print(f"[{self.adapter_name}] 重连失败: {e}")
            return await self.reconnect()
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connected
    
    async def stop(self):
        """停止适配器"""
        self._stop_event.set()
        await self.disconnect()

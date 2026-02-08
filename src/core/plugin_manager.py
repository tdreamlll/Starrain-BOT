import os
import sys
import json
import importlib
import importlib.util
import asyncio
from pathlib import Path
from typing import Dict, Set, Optional, Callable, Any, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from src.utils.logger import get_logger

def _get_logger():
    return get_logger()


class PluginMetadata:
    """插件元数据"""
    
    def __init__(self, name: str, version: str, author: str, description: str = ""):
        self.name = name
        self.version = version
        self.author = author
        self.description = description


class Plugin:
    """插件封装类"""
    
    def __init__(self, module_path: Path):
        self.path = module_path
        self.name = module_path.stem
        self.module = None
        self.enabled = True
        self.metadata = None
        self._event_handlers = {}
    
    def load(self):
        """加载插件"""
        try:
            spec = importlib.util.spec_from_file_location(self.name, self.path)
            if spec and spec.loader:
                self.module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(self.module)
                
                # 读取元数据
                if hasattr(self.module, '__plugin_metadata__'):
                    self.metadata = self.module.__plugin_metadata__
                else:
                    self.metadata = PluginMetadata(
                        self.name,
                        "1.0.0",
                        "Unknown",
                        ""
                    )
                
                return True
        except Exception as e:
            _get_logger().error(f"插件加载失败 {self.name}: {e}")
            return False
    
    def unload(self):
        """卸载插件"""
        if self.module:
            del self.module
            self.module = None
    
    def reload(self):
        """重载插件"""
        self.unload()
        return self.load()
    
    def on_event(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    async def handle_event(self, event_type: str, *args, **kwargs):
        """处理事件"""
        if event_type not in self._event_handlers:
            return
        
        for handler in self._event_handlers[event_type]:
            try:
                result = handler(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                _get_logger().error(f"插件事件处理错误 {self.name}: {e}")


class PluginEventHandler(FileSystemEventHandler):
    """插件文件监控处理器"""
    
    def __init__(self, plugin_manager: 'PluginManager'):
        self.plugin_manager = plugin_manager
    
    def on_modified(self, event: FileModifiedEvent):
        if not event.is_directory and event.src_path.endswith('.py'):
            plugin_path = Path(event.src_path)
            self.plugin_manager._on_plugin_modified(plugin_path)


class PluginManager:
    """插件管理器；插件相关数据统一存放在 data 目录。"""

    def __init__(self, config: dict):
        self.config = config
        self.plugin_dir = Path(config.get('dir', './plugins'))
        self.data_dir = Path(config.get('data_dir', 'data')).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.plugins: Dict[str, Plugin] = {}
        self.enabled_plugins: Set[str] = set()
        self.auto_load = config.get('auto_load', True)
        self.hot_reload = config.get('hot_reload', True)
        self.metadata_file = self.data_dir / config.get('metadata_file', 'plugin_metadata.json')
        self._group_plugins_file = self.data_dir / "group_plugins.json"
        self._group_plugins: Dict[str, Dict[str, bool]] = {}
        self._load_group_plugins()

        # 文件监控
        self.observer = None
        if self.hot_reload:
            self.observer = Observer()
            self.observer.schedule(
                PluginEventHandler(self),
                str(self.plugin_dir),
                recursive=False
            )
            self.observer.start()
        
        self._load_metadata()
        
        if self.auto_load:
            self.load_all_plugins()
    
    def _load_metadata(self):
        """加载插件元数据"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.enabled_plugins = set(data.get('enabled_plugins', []))
        except Exception as e:
            _get_logger().error(f"加载插件元数据失败: {e}")
    
    def _save_metadata(self):
        """保存插件元数据（存于 data 目录）"""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'enabled_plugins': list(self.enabled_plugins)
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            _get_logger().error(f"保存插件元数据失败: {e}")

    def _load_group_plugins(self):
        try:
            if self._group_plugins_file.exists():
                with open(self._group_plugins_file, 'r', encoding='utf-8') as f:
                    self._group_plugins = json.load(f)
            else:
                self._group_plugins = {}
        except Exception:
            self._group_plugins = {}

    def _save_group_plugins(self):
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self._group_plugins_file, 'w', encoding='utf-8') as f:
                json.dump(self._group_plugins, f, ensure_ascii=False, indent=2)
        except Exception as e:
            _get_logger().error(f"保存群插件配置失败: {e}")

    def set_group_plugin_enabled(self, group_id: int, plugin_name: str, enabled: bool) -> None:
        gk = str(group_id)
        if gk not in self._group_plugins:
            self._group_plugins[gk] = {}
        self._group_plugins[gk][plugin_name] = enabled
        self._save_group_plugins()

    def get_group_plugin_enabled(self, group_id: int, plugin_name: str) -> Optional[bool]:
        return self._group_plugins.get(str(group_id), {}).get(plugin_name)

    def is_plugin_enabled_for_context(self, plugin_name: str, group_id: Optional[int]) -> bool:
        if plugin_name not in self.enabled_plugins:
            return False
        if group_id is None:
            return True
        override = self.get_group_plugin_enabled(group_id, plugin_name)
        return override is None or override is True

    def discover_plugins(self) -> list:
        """发现插件"""
        plugins = []
        if self.plugin_dir.exists():
            for file_path in self.plugin_dir.glob('*.py'):
                if file_path.name != '__init__.py':
                    plugins.append(file_path)
        return plugins
    
    def load_all_plugins(self):
        """加载所有插件"""
        plugins = self.discover_plugins()
        for plugin_path in plugins:
            plugin_name = plugin_path.stem
            if plugin_name not in self.plugins:
                self.load_plugin(plugin_name, file_path=plugin_path)
    
    def load_plugin(self, plugin_name: str, file_path: Optional[Path] = None) -> bool:
        """加载插件"""
        if plugin_name in self.plugins:
            return False
        
        if not file_path:
            file_path = self.plugin_dir / f"{plugin_name}.py"
        
        if not file_path.exists():
            _get_logger().error(f"插件文件不存在: {file_path}")
            return False
        
        plugin = Plugin(file_path)
        if plugin.load():
            self.plugins[plugin_name] = plugin
            
            if plugin_name in self.enabled_plugins:
                self.enable_plugin(plugin_name)
            
            _get_logger().success(f"插件加载成功: {plugin_name}")
            
            # 调用插件的on_load
            if hasattr(plugin.module, 'on_load'):
                try:
                    result = plugin.module.on_load()
                    if asyncio.iscoroutine(result):
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(result)
                        except RuntimeError:
                            asyncio.run(result)
                except Exception as e:
                    _get_logger().error(f"插件on_load错误 {plugin_name}: {e}")
            
            return True
        return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """卸载插件"""
        if plugin_name not in self.plugins:
            return False
        
        plugin = self.plugins[plugin_name]
        
        # 调用插件的on_unload
        if plugin.module and hasattr(plugin.module, 'on_unload'):
            try:
                result = plugin.module.on_unload()
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        asyncio.run(result)
            except Exception as e:
                _get_logger().warning(f"插件on_unload错误 {plugin_name}: {e}")
        
        plugin.unload()
        del self.plugins[plugin_name]
        _get_logger().success(f"插件卸载成功: {plugin_name}")
        return True
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """重载插件"""
        if plugin_name not in self.plugins:
            return self.load_plugin(plugin_name)
        
        plugin = self.plugins[plugin_name]
        
        # 调用插件的on_reload
        if plugin.module and hasattr(plugin.module, 'on_reload'):
            try:
                result = plugin.module.on_reload()
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        asyncio.run(result)
            except Exception as e:
                _get_logger().warning(f"插件on_reload错误 {plugin_name}: {e}")
        
        if plugin.reload():
            _get_logger().success(f"插件重载成功: {plugin_name}")
            return True
        return False
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """启用插件"""
        if plugin_name not in self.plugins:
            return False
        
        self.plugins[plugin_name].enabled = True
        self.enabled_plugins.add(plugin_name)
        self._save_metadata()
        _get_logger().success(f"插件已启用: {plugin_name}")
        return True
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """禁用插件"""
        if plugin_name not in self.plugins:
            return False
        
        self.plugins[plugin_name].enabled = False
        self.enabled_plugins.discard(plugin_name)
        self._save_metadata()
        _get_logger().success(f"插件已禁用: {plugin_name}")
        return True
    
    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        return self.plugins.get(plugin_name)

    def get_plugin_data_dir(self, plugin_name: str) -> Path:
        path = self.data_dir / plugin_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def dispatch_event(self, event_type: str, *args, **kwargs):
        group_id = getattr(args[0], 'group_id', None) if args else None
        for plugin_name, plugin in self.plugins.items():
            if not self.is_plugin_enabled_for_context(plugin_name, group_id):
                continue
            await plugin.handle_event(event_type, *args, **kwargs)
    
    def _on_plugin_modified(self, plugin_path: Path):
        """插件文件修改回调"""
        if self.hot_reload:
            plugin_name = plugin_path.stem
            _get_logger().info(f"检测到插件修改: {plugin_name}")
            self.reload_plugin(plugin_name)
    
    def stop(self):
        """停止插件管理器"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
        
        for plugin_name in list(self.plugins.keys()):
            self.unload_plugin(plugin_name)

import logging
from rich.console import Console
from rich.logging import RichHandler
from rich.text import Text
from pathlib import Path


class ColorLogger:
    """彩色日志记录器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.level = config.get('level', 'INFO').upper()
        self.log_file = config.get('file', 'logs/bot.log')
        self.console_enabled = config.get('console', True)
        self.color_enabled = config.get('color', True)
        
        self.console = Console(theme=None if self.color_enabled else "no_color")
        self.logger = self._setup_logger()
        
        self._setup_log_file()
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('StarrainBOT')
        logger.setLevel(getattr(logging, self.level))
        
        if self.console_enabled:
            console_handler = RichHandler(
                console=self.console,
                rich_tracebacks=True,
                show_time=True,
                show_path=False
            )
            console_handler.setLevel(getattr(logging, self.level))
            logger.addHandler(console_handler)
        
        return logger
    
    def _setup_log_file(self):
        """设置日志文件"""
        log_path = Path(self.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, self.level))
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
    
    def debug(self, message: str):
        """调试日志"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """信息日志"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """警告日志"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """错误日志"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """严重错误日志"""
        self.logger.critical(message)
    
    def success(self, message: str):
        """成功信息"""
        if self.console_enabled:
            success_text = Text.from_markup(f"[bold green]✓[/bold green] {message}")
            self.console.print(success_text)
        else:
            self.info(f"✓ {message}")
    
    def print(self, message: str, color: str = "white"):
        """直接打印消息"""
        if self.console_enabled and self.color_enabled:
            colored_text = Text.from_markup(f"[{color}]{message}[/{color}]")
            self.console.print(colored_text)
        else:
            self.console.print(message)
    
    def print_info(self, message: str):
        """打印信息（青色）"""
        self.print(f"ℹ {message}", "cyan")
    
    def print_warning(self, message: str):
        """打印警告（黄色）"""
        self.print(f"⚠ {message}", "yellow")
    
    def print_error(self, message: str):
        """打印错误（红色）"""
        self.print(f"✗ {message}", "red")


_logger_instance = None


def get_logger(config: dict = None) -> ColorLogger:
    """获取日志记录器实例"""
    global _logger_instance
    if _logger_instance is None and config:
        _logger_instance = ColorLogger(config)
    return _logger_instance

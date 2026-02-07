import logging
from pathlib import Path


class ColorLogger:
    """彩色日志记录器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.level = config.get('level', 'INFO').upper()
        self.log_file = config.get('file', 'logs/bot.log')
        self.console_enabled = config.get('console', True)
        
        self.logger = self._setup_logger()
        
        self._setup_log_file()
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('StarrainBOT')
        logger.setLevel(getattr(logging, self.level))
        
        if self.console_enabled:
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(getattr(logging, self.level))
            stream_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)-8s %(message)s', datefmt='%m/%d/%y %H:%M:%S'))
            stream_handler.flush = lambda: None
            logger.addHandler(stream_handler)
        
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
        self.logger.handlers[0].flush() if self.logger.handlers else None
    
    def warning(self, message: str):
        """警告日志"""
        self.logger.warning(message)
        self.logger.handlers[0].flush() if self.logger.handlers else None
    
    def error(self, message: str):
        """错误日志"""
        self.logger.error(message)
        self.logger.handlers[0].flush() if self.logger.handlers else None
    
    def critical(self, message: str):
        """严重错误日志"""
        self.logger.critical(message)
        self.logger.handlers[0].flush() if self.logger.handlers else None
    
    def success(self, message: str):
        self.info(f"✓ {message}")
    
    def print(self, message: str, color: str = "white"):
        pass
    
    def print_info(self, message: str):
        pass
    
    def print_warning(self, message: str):
        pass
    
    def print_error(self, message: str):
        pass


_logger_instance = None


def get_logger(config: dict = None) -> ColorLogger:
    """获取日志记录器实例"""
    global _logger_instance
    if _logger_instance is None and config:
        _logger_instance = ColorLogger(config)
    return _logger_instance

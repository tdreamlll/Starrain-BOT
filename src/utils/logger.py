import logging
import sys
from pathlib import Path

class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器（使用 ANSI 颜色码）"""
    
    # ANSI 颜色码
    COLORS = {
        logging.DEBUG: '\033[36m',      # 青色
        logging.INFO: '\033[32m',       # 绿色
        logging.WARNING: '\033[33m',    # 黄色
        logging.ERROR: '\033[31m',      # 红色
        logging.CRITICAL: '\033[41m',   # 红色背景
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    def __init__(self, fmt=None, datefmt=None, use_color=True):
        super().__init__(fmt, datefmt)
        self.use_color = use_color
    
    def format(self, record):
        levelname = record.levelname
        levelno = record.levelno
        
        if self.use_color:
            # 获取颜色
            color_start = self.COLORS.get(levelno, '')
            # 应用颜色到 levelname
            colored_levelname = f"{color_start}{self.BOLD}{levelname}{self.RESET}"
            # 设置 levelname（保持固定宽度）
            record.levelname = colored_levelname.ljust(8)
        else:
            record.levelname = levelname.ljust(8)
        
        return super().format(record)


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
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setLevel(getattr(logging, self.level))
            stream_handler.flush = lambda: sys.stdout.flush()
            
            # 使用彩色格式化器
            use_color = self.config.get('color', True)
            stream_handler.setFormatter(ColoredFormatter(
                '[%(asctime)s] %(levelname)-8s %(message)s',
                datefmt='%m/%d/%y %H:%M:%S',
                use_color=use_color
            ))
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
        self.info(f"✓ {message}")
    
    def print_info(self, message: str):
        """打印信息"""
        self.info(f"ℹ {message}")
    
    def print_warning(self, message: str):
        """打印警告"""
        self.warning(f"⚠ {message}")
    
    def print_error(self, message: str):
        """打印错误"""
        self.error(f"✗ {message}")


_logger_instance = None


def get_logger(config: dict = None) -> ColorLogger:
    """获取日志记录器实例"""
    global _logger_instance
    if _logger_instance is None and config:
        _logger_instance = ColorLogger(config)
    return _logger_instance

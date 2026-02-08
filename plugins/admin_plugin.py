"""
管理命令插件
"""
from src.core.permission import PermissionLevel
from src.utils.logger import get_logger

logger = get_logger()

# 插件元数据
__plugin_metadata__ = {
    'name': 'admin',
    'version': '1.0.0',
    'author': 'Starrain',
    'description': '管理员命令插件'
}


async def on_load():
    """插件加载时调用"""
    logger.info(f"插件加载: {__plugin_metadata__['name']} v{__plugin_metadata__['version']}")


def on_group_message(event, permission_level):
    """处理群消息"""
    # 只允许BOT管理员
    if permission_level != PermissionLevel.BOT_ADMIN:
        return
    
    message = event.raw_message
    args = message.split()
    
    if len(args) < 2:
        return
    
    command = args[0]
    
    # 添加管理员
    if command == '/add_admin':
        try:
            qq = int(args[1])
            return {
                'action': 'add_admin',
                'qq': qq
            }
        except ValueError:
            return {
                'action': 'help',
                'message': '请输入有效的QQ号'
            }
    
    # 移除管理员
    elif command == '/remove_admin':
        try:
            qq = int(args[1])
            return {
                'action': 'remove_admin',
                'qq': qq
            }
        except ValueError:
            return {
                'action': 'help',
                'message': '请输入有效的QQ号'
            }

"""
示例插件 - 回声机器人
"""
from src.core.permission import PermissionLevel


# 插件元数据
__plugin_metadata__ = {
    'name': 'echo',
    'version': '1.0.0',
    'author': 'Starrain',
    'description': '简单的回声插件，重复收到的消息'
}


async def on_load():
    """插件加载时调用"""
    print(f"[插件] {__plugin_metadata__['name']} v{__plugin_metadata__['version']} 加载成功")


async def on_unload():
    """插件卸载时调用"""
    print(f"[插件] {__plugin_metadata__['name']} 已卸载")


def on_message(event, permission_level):
    """处理消息事件"""
    # 只处理普通成员
    if permission_level != PermissionLevel.MEMBER:
        return
    
    # 检查是否包含"回声"关键字
    if '回声' in event.raw_message:
        return {
            'action': 'echo',
            'message': event.raw_message.replace('回声', '').strip()
        }


def on_group_message(event, permission_level):
    """处理群消息"""
    result = on_message(event, permission_level)
    if result:
        return result

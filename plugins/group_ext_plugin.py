"""
群扩展和小程序卡片插件
演示群扩展API和Ark消息的使用
"""
from src.utils.logger import get_logger

logger = get_logger()

__plugin_metadata__ = {
    'name': 'group_extension',
    'version': '1.0.0',
    'author': 'Starrain',
    'description': '群扩展和小程序卡片功能'
}


async def on_load():
    logger.info(f"插件加载: {__plugin_metadata__['name']}")


async def on_reload():
    logger.info(f"插件重载: {__plugin_metadata__['name']}")


def on_group_message(event, permission_level, client):
    """
    处理群消息
    可用命令:
    /groupinfo - 获取群详细信息
    /sign - 群打卡
    /album - 获取群相册列表
    /ark_bili <标题>|<描述>|<图片URL>|<跳转URL> - 生成B站风格小程序卡片
    /ark_share_group <群号> - 分享群卡片
    """
    message = event.raw_message
    group_id = event.group_id
    
    if message == '/groupinfo':
        return {
            'action': 'api_call',
            'api': 'group_ext.get_group_detail_info',
            'params': {'group_id': group_id},
            'callback': _handle_group_info
        }
    
    elif message == '/sign':
        return {
            'action': 'api_call',
            'api': 'group_ext.send_group_sign',
            'params': {'group_id': group_id},
            'callback': _handle_sign_result
        }
    
    elif message == '/album':
        return {
            'action': 'api_call',
            'api': 'group_ext.get_qun_album_list',
            'params': {'group_id': group_id},
            'callback': _handle_album_list
        }
    
    elif message.startswith('/ark_bili '):
        parts = message[10:].strip().split('|')
        if len(parts) < 4:
            return {
                'action': 'send_message',
                'message': '格式: /ark_bili 标题|描述|图片URL|跳转URL'
            }
        title, desc, pic_url, jump_url = parts[0], parts[1], parts[2], parts[3]
        return {
            'action': 'api_call',
            'api': 'ark.get_mini_app_ark_bili',
            'params': {
                'title': title.strip(),
                'desc': desc.strip(),
                'pic_url': pic_url.strip(),
                'jump_url': jump_url.strip()
            },
            'callback': _handle_ark_result,
            'group_id': group_id
        }
    
    elif message.startswith('/ark_share_group '):
        target_group_id = message[17:].strip()
        if not target_group_id.isdigit():
            return {
                'action': 'send_message',
                'message': '请输入有效的群号'
            }
        return {
            'action': 'api_call',
            'api': 'ark.ark_share_group',
            'params': {'group_id': int(target_group_id)},
            'callback': _handle_share_group_result,
            'target_group': group_id
        }
    
    elif message == '/group_ex':
        return {
            'action': 'api_call',
            'api': 'group_ext.get_group_info_ex',
            'params': {'group_id': group_id},
            'callback': _handle_group_info_ex
        }
    
    elif message.startswith('/todo '):
        msg_id = message[6:].strip()
        if not msg_id:
            return {
                'action': 'send_message',
                'message': '格式: /todo 消息ID'
            }
        return {
            'action': 'api_call',
            'api': 'group_ext.set_group_todo',
            'params': {
                'group_id': group_id,
                'message_id': msg_id
            },
            'callback': _handle_todo_result
        }


def _handle_group_info(result, context):
    if result:
        info_text = f"""群详细信息:
群号: {result.get('group_id', '未知')}
群名: {result.get('group_name', '未知')}
成员数: {result.get('member_count', 0)}/{result.get('max_member_count', 0)}
全员禁言: {'是' if result.get('group_all_shut') else '否'}
群备注: {result.get('group_remark', '无')}"""
        return {
            'action': 'send_message',
            'message': info_text
        }
    return {
        'action': 'send_message',
        'message': '获取群信息失败'
    }


def _handle_group_info_ex(result, context):
    if result:
        return {
            'action': 'send_message',
            'message': f'群扩展信息: {result}'
        }
    return {
        'action': 'send_message',
        'message': '获取群扩展信息失败'
    }


def _handle_sign_result(result, context):
    if result:
        return {
            'action': 'send_message',
            'message': '打卡成功！'
        }
    return {
        'action': 'send_message',
        'message': '打卡失败，请稍后重试'
    }


def _handle_album_list(result, context):
    if result and isinstance(result, list):
        if not result:
            return {
                'action': 'send_message',
                'message': '该群暂无相册'
            }
        album_text = '群相册列表:\n'
        for album in result:
            album_text += f"- {album.get('album_name', '未知')} (ID: {album.get('album_id', '未知')})\n"
        return {
            'action': 'send_message',
            'message': album_text.strip()
        }
    return {
        'action': 'send_message',
        'message': '获取相册列表失败'
    }


def _handle_ark_result(result, context):
    if result and result.get('data'):
        ark_data = result['data'].get('data', result['data'])
        return {
            'action': 'send_ark',
            'ark_data': ark_data,
            'group_id': context.get('group_id')
        }
    return {
        'action': 'send_message',
        'message': '生成小程序卡片失败'
    }


def _handle_share_group_result(result, context):
    if result:
        return {
            'action': 'send_ark',
            'ark_data': result,
            'group_id': context.get('target_group')
        }
    return {
        'action': 'send_message',
        'message': '获取群分享卡片失败'
    }


def _handle_todo_result(result, context):
    if result:
        return {
            'action': 'send_message',
            'message': '已设置群待办'
        }
    return {
        'action': 'send_message',
        'message': '设置群待办失败'
    }

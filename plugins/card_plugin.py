"""
卡片生成插件
展示卡片、列表和表格的用法
"""
import asyncio
from src.utils.renderer import render_card, render_list, render_table
from src.utils.logger import get_logger

logger = get_logger()

# 插件元数据
__plugin_metadata__ = {
    'name': 'card_generator',
    'version': '1.0.0',
    'author': 'Starrain',
    'description': '卡片生成插件示例'
}


async def on_load():
    logger.info(f"插件加载: {__plugin_metadata__['name']}")


async def on_reload():
    logger.info(f"插件重载: {__plugin_metadata__['name']}")


def on_group_message(event, permission_level):
    """
    处理群消息
    可用命令:
    /card <标题>|<内容> - 生成卡片
    /help_card - 显示帮助
    /rank <玩家1> <玩家2> <玩家3> - 生成排行榜
    """
    message = event.raw_message
    
    # 生成卡片
    if message.startswith('/card '):
        parts = message[6:].strip().split('|', 1)
        if len(parts) != 2:
            return {
                'action': 'send_message',
                'message': '使用格式: /card 标题|内容'
            }
        
        title, content = parts
        image_path = asyncio.run(render_card(
            title.strip(),
            content.strip(),
            width=800,
            height=400,
            theme='default'
        ))
        
        return {
            'action': 'send_image',
            'image_path': image_path
        }
    
    # 帮助卡片
    elif message == '/help_card':
        help_text = '''可用命令:

1. /card 标题|内容
   生成信息卡片

2. /rank 玩家1 玩家2 玩家3
   生成排行榜

示例:
/card 公告|今日维护时间为10:00
/rank 小明 小红 小华'''
        
        image_path = asyncio.run(render_card(
            '卡片插件帮助',
            help_text,
            width=700,
            height=500,
            theme='default'
        ))
        
        return {
            'action': 'send_image',
            'image_path': image_path
        }
    
    # 排行榜
    elif message.startswith('/rank '):
        players = message[6:].strip().split()
        if len(players) < 3:
            return {
                'action': 'send_message',
                'message': '请至少提供3个玩家，格式: /rank 玩家1 玩家2 玩家3'
            }
        
        # 为每个玩家生成排名列表
        ranked_list = []
        for i, player in enumerate(players, 1):
            ranked_list.append(f'第{i}名: {player}')
        
        image_path = asyncio.run(render_list(
            items=ranked_list,
            title='排行榜',
            width=700,
            height=400,
            theme='default'
        ))
        
        return {
            'action': 'send_image',
            'image_path': image_path
        }
    
    # 用户信息表格
    elif message.startswith('/users '):
        # 解析用户信息
        # 格式: /users 用户1:角色1 用户2:角色2
        parts = message[7:].strip().split()
        if len(parts) < 1:
            return
        
        headers = ['用户', '角色', '等级']
        rows = []
        
        for part in parts:
            if ':' in part:
                user, role = part.split(':', 1)
                rows.append([user, role, str(len(user) * 10)])  # 模拟等级
            else:
                rows.append([part, '普通', '1'])
        
        image_path = asyncio.run(render_table(
            headers=headers,
            rows=rows,
            title='用户信息表',
            width=700,
            height=400
        ))
        
        return {
            'action': 'send_image',
            'image_path': image_path
        }

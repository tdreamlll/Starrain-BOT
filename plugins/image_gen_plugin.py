"""
图片生成插件示例
展示如何使用封装的图片渲染功能
"""
import asyncio
from src.core.permission import PermissionLevel
from src.utils.renderer import render_text, render_card, render_list, render_table


# 插件元数据
__plugin_metadata__ = {
    'name': 'image_gen',
    'version': '2.0.0',
    'author': 'Starrain',
    'description': '图片生成插件示例 - 使用封装的渲染API'
}


async def on_load():
    """插件加载时调用"""
    print(f"[插件] {__plugin_metadata__['name']} v{__plugin_metadata__['version']} 加载成功")


async def on_reload():
    """插件重载时调用"""
    print(f"[插件] {__plugin_metadata__['name']} 已重载")


def on_group_message(event, permission_level):
    """处理群消息"""
    message = event.raw_message
    
    # 渲染文字: /img <文字>
    if message.startswith('/img '):
        text = message[5:].strip()
        if text:
            image_path = asyncio.run(render_text(
                text,
                width=800,
                height=200,
                font_size=32,
                font_color='#000000',
                bg_color='#FFFFFF'
            ))
            
            return {
                'action': 'send_image',
                'image_path': image_path
            }
    
    # 渲染卡片: /card <标题>|<内容>
    elif message.startswith('/card '):
        parts = message[6:].strip().split('|', 1)
        if len(parts) == 2:
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
    
    # 渲染列表: /list <标题> <项目1> <项目2> ...
    elif message.startswith('/list '):
        parts = message[6:].strip().split()
        if parts:
            title = parts[0]
            items = parts[1:]
            image_path = asyncio.run(render_list(
                items,
                title=title,
                width=800,
                height=400
            ))
            
            return {
                'action': 'send_image',
                'image_path': image_path
            }
    
    # 渲染表格: /table <标题> <列1,列2> <行1列1,行1列2> <行2列1,行2列2> ...
    elif message.startswith('/table '):
        parts = message[7:].strip().split('|')
        if len(parts) >= 2:
            title = parts[0].strip()
            headers = [h.strip() for h in parts[1].split(',')]
            rows = []
            for row_part in parts[2:]:
                rows.append([cell.strip() for cell in row_part.split(',')])
            
            image_path = asyncio.run(render_table(
                headers=headers,
                rows=rows,
                title=title,
                width=800,
                height=500
            ))
            
            return {
                'action': 'send_image',
                'image_path': image_path
            }

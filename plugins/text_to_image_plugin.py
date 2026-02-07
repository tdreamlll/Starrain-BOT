"""
简单的文字转图片插件
展示最简单的图片渲染用法
"""
import asyncio
from src.utils.renderer import render_text

# 插件元数据
__plugin_metadata__ = {
    'name': 'text_to_image',
    'version': '1.0.0',
    'author': 'Starrain',
    'description': '简单的文字转图片插件'
}


async def on_load():
    print(f"[插件] {__plugin_metadata__['name']} 加载成功")


async def on_reload():
    print(f"[插件] {__plugin_metadata__['name']} 已重载")


def on_group_message(event, permission_level):
    """
    处理群消息
    命令格式: /text <文字>
    示例: /text 你好世界
    """
    message = event.raw_message
    
    if message.startswith('/text '):
        text = message[6:].strip()
        if not text:
            return
        
        # 使用封装的渲染函数
        image_path = asyncio.run(render_text(
            text=text,
            width=800,
            height=300,
            font_size=36,
            font_color='#333333',
            bg_color='#f0f0f0'
        ))
        
        return {
            'action': 'send_image',
            'image_path': image_path
        }
    
    # 彩色文字: /ctext <颜色> <文字>
    elif message.startswith('/ctext '):
        parts = message[7:].strip().split(' ', 1)
        if len(parts) != 2:
            return
        
        color = parts[0]
        text = parts[1]
        
        image_path = asyncio.run(render_text(
            text=text,
            width=800,
            height=300,
            font_size=36,
            font_color=color,
            bg_color='#ffffff'
        ))
        
        return {
            'action': 'send_image',
            'image_path': image_path
        }

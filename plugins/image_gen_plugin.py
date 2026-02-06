"""
图片生成插件示例
"""
from src.core.permission import PermissionLevel


# 插件元数据
__plugin_metadata__ = {
    'name': 'image_gen',
    'version': '1.0.0',
    'author': 'Starrain',
    'description': '图片生成插件示例'
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
    
    # 截图命令: /img <文字>
    if message.startswith('/img '):
        import sys
        from pathlib import Path
        
        # 添加项目根路径
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        
        from src.utils.renderer import ImageRenderer
        
        text = message[5:].strip()
        if text:
            renderer = ImageRenderer({
                'cache_dir': './cache',
                'max_cache_size': 100,
                'default_width': 800,
                'default_height': 600,
                'cache_expire': 3600
            })
            
            # 渲染文字图片
            import asyncio
            image_path = asyncio.run(renderer.render_text(
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

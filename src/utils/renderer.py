import hashlib
import base64
from pathlib import Path
from typing import Optional
import io
import json
from datetime import datetime, timedelta
import asyncio

_renderer_instance = None

try:
    from pyppeteer import launch
    PUPPETEER_AVAILABLE = True
except ImportError:
    PUPPETEER_AVAILABLE = False


class ImageRenderer:
    """基于 Puppeteer 的图片渲染器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.cache_dir = Path(config.get('cache_dir', './cache'))
        self.max_cache_size = config.get('max_cache_size', 100)
        self.default_width = config.get('default_width', 800)
        self.default_height = config.get('default_height', 600)
        self.cache_expire = config.get('cache_expire', 3600)
        
        self.cache: dict = {}
        self.cache_metadata: dict = {}
        
        self.browser = None
        self.browser_launched = False
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_cache_metadata()
    
    async def _ensure_browser(self):
        """确保浏览器已启动"""
        if not PUPPETEER_AVAILABLE:
            raise ImportError("pyppeteer 未安装，请运行: pip install pyppeteer")
            
        if self.browser is None or not self.browser_launched:
            self.browser = await launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-setuid-sandbox'
                ]
            )
            self.browser_launched = True
    
    async def close_browser(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.browser_launched = False
    
    def _load_cache_metadata(self):
        """加载缓存元数据"""
        metadata_file = self.cache_dir / 'metadata.json'
        try:
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    self.cache_metadata = json.load(f)
        except Exception:
            self.cache_metadata = {}
    
    def _save_cache_metadata(self):
        """保存缓存元数据"""
        metadata_file = self.cache_dir / 'metadata.json'
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存缓存元数据失败: {e}")
    
    def _cleanup_cache(self):
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = []
        
        for key, data in self.cache_metadata.items():
            expire_time = datetime.fromisoformat(data.get('expire_time', ''))
            if now > expire_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            self.delete_cache(key)
        
        if len(self.cache) > self.max_cache_size:
            sorted_keys = sorted(
                self.cache_metadata.keys(),
                key=lambda k: datetime.fromisoformat(self.cache_metadata[k].get('created_at'))
            )
            for key in sorted_keys[:len(self.cache) - self.max_cache_size]:
                self.delete_cache(key)
    
    def _get_cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.png"
    
    def generate_cache_key(self, *args) -> str:
        """生成缓存键"""
        data = str(args)
        return hashlib.md5(data.encode()).hexdigest()
    
    def get_cache(self, cache_key: str) -> Optional[bytes]:
        """获取缓存"""
        cache_path = self._get_cache_path(cache_key)
        
        if cache_path not in self.cache and cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    self.cache[cache_key] = f.read()
            except Exception as e:
                print(f"读取缓存失败: {e}")
                return None
        
        return self.cache.get(cache_key)
    
    def set_cache(self, cache_key: str, data: bytes):
        """设置缓存"""
        self.cache[cache_key] = data
        cache_path = self._get_cache_path(cache_key)
        
        try:
            with open(cache_path, 'wb') as f:
                f.write(data)
            
            now = datetime.now()
            self.cache_metadata[cache_key] = {
                'created_at': now.isoformat(),
                'expire_time': (now + timedelta(seconds=self.cache_expire)).isoformat(),
                'size': len(data)
            }
            self._save_cache_metadata()
            
            self._cleanup_cache()
        except Exception as e:
            print(f"保存缓存失败: {e}")
    
    def delete_cache(self, cache_key: str):
        """删除缓存"""
        cache_path = self._get_cache_path(cache_key)
        
        if cache_key in self.cache:
            del self.cache[cache_key]
        
        if cache_path.exists():
            cache_path.unlink()
        
        if cache_key in self.cache_metadata:
            del self.cache_metadata[cache_key]
    
    def _generate_html(self, text: str, width: int, height: int, 
                      font_size: int = 24, font_color: str = '#000000',
                      bg_color: str = '#FFFFFF', padding: int = 20,
                      font_family: str = '"Microsoft YaHei", Arial, sans-serif') -> str:
        """生成 HTML"""
        return f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    width: {width}px;
                    height: {height}px;
                    background-color: {bg_color};
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-family: {font_family};
                    font-size: {font_size}px;
                    color: {font_color};
                    padding: {padding}px;
                    word-wrap: break-word;
                    overflow: hidden;
                }}
                .content {{
                    text-align: center;
                    max-width: 100%;
                    max-height: 100%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
            </style>
        </head>
        <body>
            <div class="content">{text}</div>
        </body>
        </html>
        '''
    
    async def _screenshot_from_html(self, html: str, width: int, height: int) -> bytes:
        """从 HTML 截图"""
        await self._ensure_browser()
        
        page = await self.browser.newPage()
        
        try:
            await page.setViewport({'width': width, 'height': height})
            await page.setContent(html, {'waitUntil': 'networkidle0'})
            
            screenshot = await page.screenshot({
                'type': 'png',
                'encoding': 'binary'
            })
            
            return screenshot
        finally:
            await page.close()
    
    async def render_text(self, text: str, width: Optional[int] = None, height: Optional[int] = None,
                        font_size: int = 24, font_color: str = '#000000',
                        bg_color: str = '#FFFFFF', padding: int = 20) -> str:
        """渲染文字到图片，返回图片路径"""
        cache_key = self.generate_cache_key('text', text, width, height, font_size, font_color, bg_color, padding)
        
        cached = self.get_cache(cache_key)
        if cached:
            return f"file:///{self._get_cache_path(cache_key).absolute()}"
        
        w = width or self.default_width
        h = height or self.default_height
        
        html = self._generate_html(text, w, h, font_size, font_color, bg_color, padding)
        data = await self._screenshot_from_html(html, w, h)
        
        self.set_cache(cache_key, data)
        
        return f"file:///{self._get_cache_path(cache_key).absolute()}"
    
    async def render_from_template(self, template: str, context: dict, 
                                   width: Optional[int] = None, height: Optional[int] = None,
                                   styles: Optional[str] = None) -> str:
        """从模板渲染图片（完整 HTML 模板）"""
        cache_key = self.generate_cache_key('template', template, json.dumps(context), width, height, styles)
        
        cached = self.get_cache(cache_key)
        if cached:
            return f"file:///{self._get_cache_path(cache_key).absolute()}"
        
        w = width or self.default_width
        h = height or self.default_height
        
        html = template
        for key, value in context.items():
            html = html.replace({{'' + key + ''}}, str(value))
        
        if styles:
            html = f'<style>{styles}</style>' + html
        
        data = await self._screenshot_from_html(html, w, h)
        
        self.set_cache(cache_key, data)
        
        return f"file:///{self._get_cache_path(cache_key).absolute()}"
    
    async def render_html(self, html: str, width: Optional[int] = None, 
                         height: Optional[int] = None) -> str:
        """直接渲染 HTML"""
        cache_key = self.generate_cache_key('html', html, width, height)
        
        cached = self.get_cache(cache_key)
        if cached:
            return f"file:///{self._get_cache_path(cache_key).absolute()}"
        
        w = width or self.default_width
        h = height or self.default_height
        
        data = await self._screenshot_from_html(html, w, h)
        
        self.set_cache(cache_key, data)
        
        return f"file:///{self._get_cache_path(cache_key).absolute()}"
    
    async def render_card(self, title: str, content: str, 
                         width: Optional[int] = None, height: Optional[int] = None,
                         theme: str = 'default') -> str:
        """渲染卡片样式图片
        
        Args:
            title: 卡片标题
            content: 卡片内容
            width: 宽度
            height: 高度
            theme: 主题色
        """
        cache_key = self.generate_cache_key('card', title, content, width, height, theme)
        
        cached = self.get_cache(cache_key)
        if cached:
            return f"file:///{self._get_cache_path(cache_key).absolute()}"
        
        w = width or self.default_width
        h = height or self.default_height
        
        themes = {
            'default': {
                'bg': '#FFFFFF',
                'title_bg': '#4A90E2',
                'title_color': '#FFFFFF',
                'content_color': '#333333'
            },
            'dark': {
                'bg': '#1A1A1A',
                'title_bg': '#5B5B5B',
                'title_color': '#FFFFFF',
                'content_color': '#E0E0E0'
            },
            'green': {
                'bg': '#FFFFFF',
                'title_bg': '#52C41A',
                'title_color': '#FFFFFF',
                'content_color': '#333333'
            }
        }
        
        theme_config = themes.get(theme, themes['default'])
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    width: {w}px;
                    height: {h}px;
                    background-color: {theme_config['bg']};
                    font-family: "Microsoft YaHei", Arial, sans-serif;
                    display: flex;
                    flex-direction: column;
                    overflow: hidden;
                }}
                .header {{
                    background-color: {theme_config['title_bg']};
                    color: {theme_config['title_color']};
                    padding: 20px;
                    font-size: 24px;
                    font-weight: bold;
                    text-align: center;
                    line-height: 1.5;
                }}
                .content {{
                    color: {theme_config['content_color']};
                    padding: 20px;
                    font-size: 16px;
                    line-height: 1.8;
                    flex: 1;
                    overflow: auto;
                    word-wrap: break-word;
                }}
            </style>
        </head>
        <body>
            <div class="header">{title}</div>
            <div class="content">{content}</div>
        </body>
        </html>
        '''
        
        data = await self._screenshot_from_html(html, w, h)
        self.set_cache(cache_key, data)
        
        return f"file:///{self._get_cache_path(cache_key).absolute()}"
    
    def get_image_base64(self, image_path: str) -> str:
        """获取图片的Base64编码"""
        if image_path.startswith('file:///'):
            image_path = image_path[8:]
        
        path = Path(image_path)
        if path.exists():
            try:
                with open(path, 'rb') as f:
                    data = f.read()
                return base64.b64encode(data).decode()
            except Exception as e:
                print(f"读取图片失败: {e}")
        
        return ""
    
    async def create_composite_image(self, images: list, layout: str = 'vertical',
                                   spacing: int = 10, bg_color: str = '#FFFFFF') -> str:
        """创建合成图片"""
        cache_key = self.generate_cache_key('composite', len(images), layout, spacing, bg_color,
                                           *[img for img in images])
        
        cached = self.get_cache(cache_key)
        if cached:
            return f"file:///{self._get_cache_path(cache_key).absolute()}"
        
        img_tags = ''.join(f'<img src="{img}" style="display:block; margin:5px 0;">' for img in images)
        
        if layout == 'vertical':
            styles = f'''
                body {{ display: flex; flex-direction: column; align-items: center; 
                         gap: {spacing}px; background: {bg_color}; }}
                img {{ max-width: {self.default_width}px; }}
            '''
        elif layout == 'horizontal':
            styles = f'''
                body {{ display: flex; flex-direction: row; align-items: center; justify-content: center;
                         gap: {spacing}px; background: {bg_color}; }}
            '''
        else:
            styles = f'''
                body {{ background: {bg_color}; padding: 20px; }}
            '''
        
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ width: {self.default_width}px; height: {self.default_height}px;
                       overflow: auto; display: flex; font-family: sans-serif; }}
                {styles}
            </style>
        </head>
        <body>{img_tags}</body>
        </html>
        '''
        
        data = await self._screenshot_from_html(html, self.default_width, self.default_height)
        self.set_cache(cache_key, data)
        
        return f"file:///{self._get_cache_path(cache_key).absolute()}"


# 全局辅助函数
def get_renderer(config: dict = None) -> ImageRenderer:
    """获取图片渲染器实例（单例模式）
    
    Args:
        config: 渲染器配置，首次调用时需要提供
        
    Returns:
        ImageRenderer: 图片渲染器实例
    """
    global _renderer_instance
    if _renderer_instance is None and config:
        _renderer_instance = ImageRenderer(config)
    return _renderer_instance


async def render_text(text: str, width: int = 800, height: int = 400,
                     font_size: int = 32, font_color: str = '#000000',
                     bg_color: str = '#FFFFFF') -> str:
    """快速渲染文字图片（便捷函数）
    
    Args:
        text: 要渲染的文字
        width: 图片宽度
        height: 图片高度
        font_size: 字体大小
        font_color: 字体颜色
        bg_color: 背景颜色
        
    Returns:
        str: 图片路径（file:///格式）
    """
    if _renderer_instance is None:
        raise RuntimeError("渲染器未初始化，请先调用 get_renderer(config)")
    
    return await _renderer_instance.render_text(
        text, width, height, font_size, font_color, bg_color
    )


async def render_card(title: str, content: str, width: int = 800, height: int = 600,
                      theme: str = 'default') -> str:
    """快速渲染卡片图片（便捷函数）
    
    Args:
        title: 卡片标题
        content: 卡片内容
        width: 图片宽度
        height: 图片高度
        theme: 主题（default/dark/green）
        
    Returns:
        str: 图片路径（file:///格式）
    """
    if _renderer_instance is None:
        raise RuntimeError("渲染器未初始化，请先调用 get_renderer(config)")
    
    return await _renderer_instance.render_card(title, content, width, height, theme)


async def render_list(items: list, title: str = None, width: int = 800, height: int = 600,
                      theme: str = 'default') -> str:
    """快速渲染列表（便捷函数）
    
    Args:
        items: 列表项
        title: 标题
        width: 图片宽度
        height: 图片高度
        theme: 主题
        
    Returns:
        str: 图片路径（file:///格式）
    """
    if _renderer_instance is None:
        raise RuntimeError("渲染器未初始化，请先调用 get_renderer(config)")
    
    content = '<br>'.join(f'• {item}' for item in items)
    return await _renderer_instance.render_card(title or '列表', content, width, height, theme)


async def render_table(headers: list, rows: list, title: str = None,
                      width: int = 800, height: int = 600) -> str:
    """快速渲染表格（便捷函数）
    
    Args:
        headers: 表头
        rows: 数据行
        title: 标题
        width: 图片宽度
        height: 图片高度
        
    Returns:
        str: 图片路径（file:///格式）
    """
    if _renderer_instance is None:
        raise RuntimeError("渲染器未初始化，请先调用 get_renderer(config)")
    
    table_html = '<table style="border-collapse: collapse; width: 100%;">'
    
    if headers:
        table_html += '<tr>'
        for header in headers:
            table_html += f'<th style="border: 1px solid #ddd; padding: 8px; background: #f2f2f2; text-align: left;">{header}</th>'
        table_html += '</tr>'
    
    for row in rows:
        table_html += '<tr>'
        for cell in row:
            table_html += f'<td style="border: 1px solid #ddd; padding: 8px;">{cell}</td>'
        table_html += '</tr>'
    
    table_html += '</table>'
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                width: {width}px;
                height: {height}px;
                background: #FFFFFF;
                font-family: "Microsoft YaHei", Arial, sans-serif;
                padding: 20px;
                display: flex;
                flex-direction: column;
            }}
            .title {{
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 20px;
                text-align: center;
            }}
            .content {{
                flex: 1;
                overflow: auto;
            }}
        </style>
    </head>
    <body>
        {f'<div class="title">{title}</div>' if title else ''}
        <div class="content">{table_html}</div>
    </body>
    </html>
    '''
    
    return await _renderer_instance.render_html(html, width, height)

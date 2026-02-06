import hashlib
import base64
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import io
import json
from datetime import datetime, timedelta


class ImageRenderer:
    """图片渲染器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.cache_dir = Path(config.get('cache_dir', './cache'))
        self.max_cache_size = config.get('max_cache_size', 100)
        self.default_width = config.get('default_width', 800)
        self.default_height = config.get('default_height', 600)
        self.cache_expire = config.get('cache_expire', 3600)
        
        self.cache: dict = {}
        self.cache_metadata: dict = {}
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_cache_metadata()
    
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
        
        # 清理超过大小限制的缓存
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
        
        # 检查缓存是否存在
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
            
            # 更新元数据
            now = datetime.now()
            self.cache_metadata[cache_key] = {
                'created_at': now.isoformat(),
                'expire_time': (now + timedelta(seconds=self.cache_expire)).isoformat(),
                'size': len(data)
            }
            self._save_cache_metadata()
            
            # 清理过期缓存
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
    
    async def render_text(self, text: str, width: Optional[int] = None, height: Optional[int] = None,
                        font_size: int = 24, font_color: str = '#000000',
                        bg_color: str = '#FFFFFF', padding: int = 20) -> str:
        """渲染文字到图片，返回图片路径"""
        cache_key = self.generate_cache('text', text, width, height, font_size, font_color, bg_color, padding)
        
        cached = self.get_cache(cache_key)
        if cached:
            return f"file:///{self._get_cache_path(cache_key).absolute()}"
        
        w = width or self.default_width
        h = height or self.default_height
        
        img = Image.new('RGB', (w, h), bg_color)
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("msyh.ttc", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("Arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()
        
        text_bbox = draw.textbbox((padding, padding), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        x = (w - text_width) // 2
        y = (h - text_height) // 2
        
        draw.text((x, y), text, font=font, fill=font_color)
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        data = buffer.getvalue()
        
        self.set_cache(cache_key, data)
        
        return f"file:///{self._get_cache_path(cache_key).absolute()}"
    
    async def render_from_template(self, template: str, context: dict, 
                                   width: Optional[int] = None, height: Optional[int] = None) -> str:
        """从模板渲染图片（简单实现）"""
        cache_key = self.generate_cache('template', template, json.dumps(context), width, height)
        
        cached = self.get_cache(cache_key)
        if cached:
            return f"file:///{self._get_cache_path(cache_key).absolute()}"
        
        # 简单实现：替换变量并渲染文字
        for key, value in context.items():
            template = template.replace(f'{{{{{key}}}}}', str(value))
        
        result = await self.render_text(template, width, height)
        return result
    
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
    
    def create_composite_image(self, images: list, layout: str = 'vertical', 
                               spacing: int = 10, bg_color: str = '#FFFFFF') -> str:
        """创建合成图片"""
        cache_key = self.generate_cache('composite', len(images), layout, spacing, bg_color, 
                                      *[img for img in images])
        
        cached = self.get_cache(cache_key)
        if cached:
            return f"file:///{self._get_cache_path(cache_key).absolute()}"
        
        loaded_images = []
        for img_path in images:
            if isinstance(img_path, str) and img_path.startswith('file:///'):
                img_path = img_path[8:]
            
            try:
                img = Image.open(img_path)
                loaded_images.append(img)
            except Exception as e:
                print(f"加载图片失败: {e}")
        
        if not loaded_images:
            return ""
        
        if layout == 'vertical':
            total_width = max(img.width for img in loaded_images)
            total_height = sum(img.height for img in loaded_images) + spacing * (len(loaded_images) - 1)
        elif layout == 'horizontal':
            total_width = sum(img.width for img in loaded_images) + spacing * (len(loaded_images) - 1)
            total_height = max(img.height for img in loaded_images)
        else:
            grid_cols = int(len(loaded_images) ** 0.5) + 1
            total_width = 0
            total_height = 0
            for i, img in enumerate(loaded_images):
                if i % grid_cols == 0:
                    total_height += img.height
                    total_width = max(total_width, img.width)
                else:
                    total_width += img.width + spacing
        
        composite = Image.new('RGB', (total_width, total_height), bg_color)
        
        y = 0
        x = 0
        for img in loaded_images:
            composite.paste(img, (x, y))
            if layout == 'vertical':
                y += img.height + spacing
            elif layout == 'horizontal':
                x += img.width + spacing
        
        buffer = io.BytesIO()
        composite.save(buffer, format='PNG')
        data = buffer.getvalue()
        
        self.set_cache(cache_key, data)
        
        return f"file:///{self._get_cache_path(cache_key).absolute()}"

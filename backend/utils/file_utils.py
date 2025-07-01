"""
文件处理工具
"""
import os
import mimetypes
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# 支持的图片格式
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.tiff', '.ico'}

def get_file_info(file_path: Path) -> Optional[Dict]:
    """获取文件信息"""
    try:
        if not file_path.exists() or not file_path.is_file():
            return None
        
        stat = file_path.stat()
        
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(str(file_path))
        
        return {
            'name': file_path.name,
            'path': str(file_path),
            'size': stat.st_size,
            'mime_type': mime_type,
            'extension': file_path.suffix.lower(),
            'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'is_image': is_image_file(file_path),
            'is_svg': file_path.suffix.lower() == '.svg'
        }
        
    except Exception as e:
        logger.error(f"获取文件信息失败 {file_path}: {e}")
        return None

def is_image_file(file_path: Path) -> bool:
    """检查是否为图片文件"""
    return file_path.suffix.lower() in IMAGE_EXTENSIONS

def is_svg_file(file_path: Path) -> bool:
    """检查是否为SVG文件"""
    return file_path.suffix.lower() == '.svg'

def get_image_dimensions(image_path: Path) -> Optional[Tuple[int, int]]:
    """获取图片尺寸"""
    try:
        if not is_image_file(image_path):
            return None
        
        # 对于SVG文件，需要特殊处理
        if is_svg_file(image_path):
            return _get_svg_dimensions(image_path)
        
        # 对于其他图片格式，使用PIL
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                return img.size
        except ImportError:
            logger.warning("PIL库未安装，无法获取图片尺寸")
            return None
        except Exception as e:
            logger.debug(f"获取图片尺寸失败 {image_path}: {e}")
            return None
            
    except Exception as e:
        logger.error(f"获取图片尺寸失败 {image_path}: {e}")
        return None

def _get_svg_dimensions(svg_path: Path) -> Optional[Tuple[int, int]]:
    """获取SVG文件尺寸"""
    try:
        import xml.etree.ElementTree as ET
        
        tree = ET.parse(svg_path)
        root = tree.getroot()
        
        # 尝试从width和height属性获取
        width = root.get('width')
        height = root.get('height')
        
        if width and height:
            # 移除单位（如px, em等）
            width = _parse_dimension(width)
            height = _parse_dimension(height)
            if width and height:
                return (int(width), int(height))
        
        # 尝试从viewBox获取
        viewbox = root.get('viewBox')
        if viewbox:
            parts = viewbox.split()
            if len(parts) >= 4:
                try:
                    return (int(float(parts[2])), int(float(parts[3])))
                except ValueError:
                    pass
        
        return None
        
    except Exception as e:
        logger.debug(f"解析SVG尺寸失败 {svg_path}: {e}")
        return None

def _parse_dimension(dim_str: str) -> Optional[float]:
    """解析尺寸字符串，移除单位"""
    try:
        # 移除常见单位
        dim_str = dim_str.lower()
        for unit in ['px', 'pt', 'em', 'rem', '%', 'cm', 'mm', 'in']:
            if dim_str.endswith(unit):
                dim_str = dim_str[:-len(unit)]
                break
        
        return float(dim_str)
    except ValueError:
        return None

def format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"

def safe_filename(filename: str) -> str:
    """生成安全的文件名"""
    import re
    
    # 移除或替换不安全的字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # 移除控制字符
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # 限制长度
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    
    return filename

def get_relative_path(file_path: Path, base_path: Path) -> str:
    """获取相对路径"""
    try:
        return str(file_path.relative_to(base_path))
    except ValueError:
        return str(file_path)

def ensure_directory(dir_path: Path) -> bool:
    """确保目录存在"""
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"创建目录失败 {dir_path}: {e}")
        return False

def copy_file(src_path: Path, dst_path: Path) -> bool:
    """复制文件"""
    try:
        import shutil
        
        # 确保目标目录存在
        ensure_directory(dst_path.parent)
        
        shutil.copy2(src_path, dst_path)
        return True
        
    except Exception as e:
        logger.error(f"复制文件失败 {src_path} -> {dst_path}: {e}")
        return False

def move_file(src_path: Path, dst_path: Path) -> bool:
    """移动文件"""
    try:
        import shutil
        
        # 确保目标目录存在
        ensure_directory(dst_path.parent)
        
        shutil.move(str(src_path), str(dst_path))
        return True
        
    except Exception as e:
        logger.error(f"移动文件失败 {src_path} -> {dst_path}: {e}")
        return False

def delete_file(file_path: Path) -> bool:
    """删除文件"""
    try:
        if file_path.exists() and file_path.is_file():
            file_path.unlink()
            return True
        return False
        
    except Exception as e:
        logger.error(f"删除文件失败 {file_path}: {e}")
        return False

def get_file_hash(file_path: Path, algorithm: str = 'md5') -> Optional[str]:
    """获取文件哈希值"""
    try:
        import hashlib
        
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
        
    except Exception as e:
        logger.error(f"计算文件哈希失败 {file_path}: {e}")
        return None
"""
Gallery 服务层
处理文件夹和图片相关的业务逻辑
"""
import os
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import mimetypes
import logging

from backend.utils.file_utils import get_file_info, is_image_file, get_image_dimensions
from backend.utils.cache_utils import cached_result, cache_clear

# 临时设置图片根目录
import os
IMAGES_ROOT = os.environ.get('GALLERY_IMAGES_ROOT', os.path.expanduser('~/pythoncode/pngs'))

logger = logging.getLogger(__name__)

class GalleryService:
    """画廊服务类"""
    
    def __init__(self):
        self.images_root = Path(IMAGES_ROOT)
        if not self.images_root.exists():
            logger.warning(f"图片根目录不存在: {self.images_root}")
            
    def get_folder_list(self) -> List[Dict]:
        """获取文件夹列表"""
        try:
            folders = []
            
            if not self.images_root.exists():
                return folders
            
            for item in self.images_root.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    folder_info = self._get_folder_info(item)
                    if folder_info:
                        folders.append(folder_info)
            
            # 按日期降序排序
            folders.sort(key=lambda x: x.get('date', ''), reverse=True)
            return folders
            
        except Exception as e:
            logger.error(f"获取文件夹列表失败: {e}")
            raise
    
    def get_folder_info(self, folder_name: str) -> Optional[Dict]:
        """获取单个文件夹信息"""
        try:
            folder_path = self.images_root / folder_name
            if not folder_path.exists() or not folder_path.is_dir():
                return None
            
            return self._get_folder_info(folder_path)
            
        except Exception as e:
            logger.error(f"获取文件夹信息失败 {folder_name}: {e}")
            return None
    
    def get_subfolder_list(self, folder_name: str) -> List[Dict]:
        """获取子文件夹列表"""
        try:
            folder_path = self.images_root / folder_name
            if not folder_path.exists():
                return []
            
            subfolders = []
            for item in folder_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    subfolder_info = self._get_folder_info(item)
                    if subfolder_info:
                        subfolders.append(subfolder_info)
            
            # 按日期降序排序
            subfolders.sort(key=lambda x: x.get('date', ''), reverse=True)
            return subfolders
            
        except Exception as e:
            logger.error(f"获取子文件夹列表失败 {folder_name}: {e}")
            raise
    
    def get_image_list(self, folder_name: str, page: int = 1, per_page: int = 20, sort_by: str = 'neu_ret') -> Dict:
        """获取图片列表"""
        try:
            folder_path = self.images_root / folder_name
            if not folder_path.exists():
                return {'images': [], 'total': 0, 'page': page, 'per_page': per_page}
            
            # 收集所有图片文件
            all_images = []
            for item in folder_path.rglob('*'):
                if item.is_file() and is_image_file(item):
                    image_info = self._get_image_info(item, folder_path)
                    if image_info:
                        all_images.append(image_info)
            
            # 收益率排序支持
            if sort_by == 'neu_ret':
                all_images = self._sort_by_neu_ret(folder_path, all_images)
            elif sort_by == 'time':
                all_images.sort(key=lambda x: x.get('date', ''), reverse=True)
            else:
                # 默认按文件名排序
                all_images.sort(key=lambda x: x['name'].lower())
            
            # 分页
            total = len(all_images)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            images = all_images[start_idx:end_idx]
            
            return {
                'images': images,
                'total': total,
                'page': page,
                'per_page': per_page,
                'has_next': end_idx < total,
                'has_prev': page > 1
            }
            
        except Exception as e:
            logger.error(f"获取图片列表失败 {folder_name}: {e}")
            raise
    
    def get_file_path(self, relative_path: str) -> Optional[str]:
        """获取文件的完整路径"""
        try:
            full_path = self.images_root / relative_path
            
            # 安全检查：确保路径在images_root内
            if not str(full_path.resolve()).startswith(str(self.images_root.resolve())):
                logger.warning(f"路径访问被拒绝: {relative_path}")
                return None
            
            return str(full_path) if full_path.exists() else None
            
        except Exception as e:
            logger.error(f"获取文件路径失败 {relative_path}: {e}")
            return None
    
    def get_file_info(self, relative_path: str) -> Optional[Dict]:
        """获取文件信息"""
        try:
            full_path = self.get_file_path(relative_path)
            if not full_path:
                return None
            
            # 确保传入Path对象而不是字符串
            return get_file_info(Path(full_path))
            
        except Exception as e:
            logger.error(f"获取文件信息失败 {relative_path}: {e}")
            return None
    
    def search_files(self, query: str, folder: str = '', file_type: str = 'all') -> List[Dict]:
        """搜索文件"""
        try:
            results = []
            search_path = self.images_root / folder if folder else self.images_root
            
            if not search_path.exists():
                return results
            
            query_lower = query.lower()
            
            for item in search_path.rglob('*'):
                if not item.is_file():
                    continue
                
                # 文件类型过滤
                if file_type == 'image' and not is_image_file(item):
                    continue
                elif file_type == 'svg' and item.suffix.lower() != '.svg':
                    continue
                
                # 名称匹配
                if query_lower in item.name.lower():
                    relative_path = item.relative_to(self.images_root)
                    file_info = get_file_info(item)
                    if file_info:
                        file_info['relative_path'] = str(relative_path)
                        results.append(file_info)
            
            # 按相关性排序（名称匹配度）
            results.sort(key=lambda x: x['name'].lower().find(query_lower))
            return results[:100]  # 限制结果数量
            
        except Exception as e:
            logger.error(f"搜索文件失败 {query}: {e}")
            raise
    
    def delete_files(self, folder_name: str, file_paths: List[str]) -> Dict:
        """删除文件"""
        try:
            folder_path = self.images_root / folder_name
            if not folder_path.exists():
                return {'success': False, 'message': '文件夹不存在'}
            
            deleted_files = []
            failed_files = []
            
            for file_path in file_paths:
                try:
                    full_path = folder_path / file_path
                    
                    # 安全检查
                    if not str(full_path.resolve()).startswith(str(folder_path.resolve())):
                        failed_files.append({'file': file_path, 'error': '路径不安全'})
                        continue
                    
                    if full_path.exists() and full_path.is_file():
                        full_path.unlink()
                        deleted_files.append(file_path)
                    else:
                        failed_files.append({'file': file_path, 'error': '文件不存在'})
                        
                except Exception as e:
                    failed_files.append({'file': file_path, 'error': str(e)})
            
            return {
                'success': True,
                'deleted_count': len(deleted_files),
                'failed_count': len(failed_files),
                'deleted_files': deleted_files,
                'failed_files': failed_files
            }
            
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return {'success': False, 'message': str(e)}
    
    def query_backup_files(self, query: str) -> List[Dict]:
        """查询备份文件"""
        try:
            # 这里可以根据实际需求实现备份文件查询逻辑
            # 例如从备份目录或数据库中查询
            results = []
            
            # 示例实现：在特定备份目录中搜索
            backup_paths = [
                Path.home() / 'backup',
                Path.home() / 'backups',
                self.images_root.parent / 'backup'
            ]
            
            query_lower = query.lower()
            
            for backup_path in backup_paths:
                if not backup_path.exists():
                    continue
                
                for item in backup_path.rglob('*'):
                    if not item.is_file():
                        continue
                    
                    if query_lower in item.name.lower():
                        file_info = get_file_info(item)
                        if file_info:
                            file_info['backup_path'] = str(backup_path)
                            file_info['relative_path'] = str(item.relative_to(backup_path))
                            results.append(file_info)
            
            return results[:50]  # 限制结果数量
            
        except Exception as e:
            logger.error(f"查询备份文件失败 {query}: {e}")
            raise
    
    @cached_result(timeout=300)  # 缓存5分钟
    def _get_folder_info(self, folder_path: Path) -> Optional[Dict]:
        """获取文件夹详细信息"""
        try:
            if not folder_path.exists() or not folder_path.is_dir():
                return None
            
            # 统计文件
            image_count = 0
            total_size = 0
            
            for item in folder_path.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
                    if is_image_file(item):
                        image_count += 1
            
            # 获取修改时间
            mtime = folder_path.stat().st_mtime
            
            # 检查是否有描述文件
            description = self._get_folder_description(folder_path)
            
            return {
                'name': folder_path.name,
                'path': str(folder_path.relative_to(self.images_root)),
                'image_count': image_count,
                'size': total_size,
                'date': datetime.fromtimestamp(mtime).isoformat(),
                'description': description,
                'has_images': image_count > 0,
                'has_subfolders': any(item.is_dir() for item in folder_path.iterdir() if not item.name.startswith('.'))
            }
            
        except Exception as e:
            logger.error(f"获取文件夹信息失败 {folder_path}: {e}")
            return None
    
    def _get_folder_description(self, folder_path: Path) -> Optional[str]:
        """获取文件夹描述"""
        try:
            # 查找描述文件（folder_info.md为主，README.md等为备选）
            desc_files = ['folder_info.md', 'README.md', 'readme.md', 'description.txt', 'desc.txt']
            
            for desc_file in desc_files:
                desc_path = folder_path / desc_file
                if desc_path.exists() and desc_path.is_file():
                    with open(desc_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        return content
            
            return None
            
        except Exception as e:
            logger.debug(f"读取文件夹描述失败 {folder_path}: {e}")
            return None
    
    def _get_image_info(self, image_path: Path, base_path: Path) -> Optional[Dict]:
        """获取图片信息"""
        try:
            if not is_image_file(image_path):
                return None
            
            file_info = get_file_info(image_path)
            if not file_info:
                return None
            
            # 添加相对路径（相对于images_root）
            file_info['relative_path'] = str(image_path.relative_to(self.images_root))
            
            # 添加图片尺寸
            try:
                dimensions = get_image_dimensions(image_path)
                if dimensions:
                    file_info['width'], file_info['height'] = dimensions
            except Exception as e:
                logger.debug(f"获取图片尺寸失败 {image_path}: {e}")
            
            # 添加描述信息
            try:
                folder_path = image_path.parent
                relative_folder = str(folder_path.relative_to(self.images_root))
                description = self.get_image_description(relative_folder, image_path.name)
                file_info['description'] = description
                file_info['has_description'] = description is not None and description.strip() != ""
            except Exception as e:
                logger.debug(f"获取图片描述失败 {image_path}: {e}")
                file_info['description'] = None
                file_info['has_description'] = False
            
            return file_info
            
        except Exception as e:
            logger.error(f"获取图片信息失败 {image_path}: {e}")
            return None

    def get_image_description(self, folder_name: str, filename: str) -> Optional[str]:
        """获取图片描述"""
        try:
            folder_path = self.images_root / folder_name
            
            # 主要方案：读取隐藏的.descriptions.json文件
            desc_file = folder_path / ".descriptions.json"
            if desc_file.exists():
                with open(desc_file, 'r', encoding='utf-8') as f:
                    descriptions = json.load(f)
                return descriptions.get(filename)
            
            # 备选方案：读取统一的descriptions.json文件
            desc_file_public = folder_path / "descriptions.json"
            if desc_file_public.exists():
                with open(desc_file_public, 'r', encoding='utf-8') as f:
                    descriptions = json.load(f)
                return descriptions.get(filename)
            
            # 第三备选方案：读取单独的描述文件（图片名.json）
            name_without_ext = filename.rsplit('.', 1)[0]
            individual_desc_file = folder_path / f"{name_without_ext}.json"
            
            if individual_desc_file.exists():
                with open(individual_desc_file, 'r', encoding='utf-8') as f:
                    desc_data = json.load(f)
                    # 支持多种格式：直接字符串、{"description": "..."} 或 {"desc": "..."}
                    if isinstance(desc_data, str):
                        return desc_data
                    elif isinstance(desc_data, dict):
                        return desc_data.get('description') or desc_data.get('desc') or desc_data.get('text')
            
            return None
            
        except Exception as e:
            logger.error(f"获取图片描述失败 {folder_name}/{filename}: {e}")
            return None

    def set_image_description(self, folder_name: str, filename: str, description: str) -> bool:
        """设置图片描述"""
        try:
            folder_path = self.images_root / folder_name
            
            # 使用隐藏的.descriptions.json文件
            desc_file = folder_path / ".descriptions.json"
            
            # 读取现有描述
            descriptions = {}
            if desc_file.exists():
                try:
                    with open(desc_file, 'r', encoding='utf-8') as f:
                        descriptions = json.load(f)
                except (json.JSONDecodeError, OSError):
                    descriptions = {}
            
            # 更新或删除描述
            if description.strip():
                descriptions[filename] = description.strip()
            else:
                descriptions.pop(filename, None)
            
            # 保存更新的描述文件
            if descriptions:
                with open(desc_file, 'w', encoding='utf-8') as f:
                    json.dump(descriptions, f, ensure_ascii=False, indent=2)
            else:
                # 如果没有任何描述，删除描述文件
                if desc_file.exists():
                    desc_file.unlink()
            
            # 清除缓存以确保立即更新
            cache_clear()
            
            return True
            
        except Exception as e:
            logger.error(f"设置图片描述失败 {folder_name}/{filename}: {e}")
            return False

    def get_described_images(self, folder_name: str) -> List[Dict]:
        """获取有描述的图片列表"""
        try:
            folder_path = self.images_root / folder_name
            described_images = []
            
            # 主要方案：读取隐藏的.descriptions.json文件
            desc_file = folder_path / ".descriptions.json"
            if desc_file.exists():
                try:
                    with open(desc_file, 'r', encoding='utf-8') as f:
                        descriptions = json.load(f)
                    
                    for filename, description in descriptions.items():
                        image_path = folder_path / filename
                        if image_path.exists() and is_image_file(image_path):
                            image_info = self._get_image_info(image_path, folder_path)
                            if image_info:
                                image_info['description'] = description
                                described_images.append(image_info)
                except (json.JSONDecodeError, OSError) as e:
                    logger.debug(f"读取隐藏描述文件失败 {desc_file}: {e}")
            
            # 备选方案：读取统一的descriptions.json文件
            if not described_images:
                desc_file_public = folder_path / "descriptions.json"
                if desc_file_public.exists():
                    try:
                        with open(desc_file_public, 'r', encoding='utf-8') as f:
                            descriptions = json.load(f)
                        
                        for filename, description in descriptions.items():
                            image_path = folder_path / filename
                            if image_path.exists() and is_image_file(image_path):
                                image_info = self._get_image_info(image_path, folder_path)
                                if image_info:
                                    image_info['description'] = description
                                    described_images.append(image_info)
                    except (json.JSONDecodeError, OSError) as e:
                        logger.debug(f"读取统一描述文件失败 {desc_file_public}: {e}")
            
            # 按名称排序
            described_images.sort(key=lambda x: x['name'].lower())
            return described_images
            
        except Exception as e:
            logger.error(f"获取有描述图片列表失败 {folder_name}: {e}")
            return []

    def set_folder_description(self, folder_name: str, description: str) -> bool:
        """设置文件夹描述"""
        try:
            folder_path = self.images_root / folder_name
            if not folder_path.exists() or not folder_path.is_dir():
                return False
            
            # 保存到folder_info.md文件（优先使用）
            folder_info_path = folder_path / "folder_info.md"
            
            if description.strip():
                with open(folder_info_path, 'w', encoding='utf-8') as f:
                    f.write(description.strip())
            else:
                # 删除空描述文件
                if folder_info_path.exists():
                    folder_info_path.unlink()
            
            # 清除相关缓存
            cache_clear()
            
            return True
            
        except Exception as e:
            logger.error(f"设置文件夹描述失败 {folder_name}: {e}")
            return False

    def _sort_by_neu_ret(self, folder_path: Path, images: List[Dict]) -> List[Dict]:
        """根据neu_rets.json中的数值排序"""
        try:
            neu_ret_file = folder_path / 'neu_rets.json'
            neu_ret_data = {}
            
            if neu_ret_file.exists():
                try:
                    with open(neu_ret_file, 'r', encoding='utf-8') as f:
                        neu_ret_data = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"无法读取neu_rets.json文件 {neu_ret_file}: {e}")
            
            # 为每个图片添加neu_ret值
            for image_info in images:
                file_name = image_info['name']
                # 去掉扩展名作为key
                file_key = file_name.rsplit('.', 1)[0]
                image_info['neu_ret'] = neu_ret_data.get(file_key, 0)
            
            # 按neu_ret值从大到小排序
            images.sort(key=lambda x: x.get('neu_ret', 0), reverse=True)
            return images
            
        except Exception as e:
            logger.error(f"收益率排序失败: {e}")
            # 如果排序失败，返回原始列表
            return images
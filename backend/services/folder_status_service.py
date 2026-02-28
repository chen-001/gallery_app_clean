"""
文件夹状态服务
管理文件夹的研究状态：研究中、交流过、已收尾
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class FolderStatusService:
    """文件夹状态服务类"""
    
    # 状态定义
    STATUS_RESEARCHING = 'researching'  # 研究中
    STATUS_COMMUNICATED = 'communicated'  # 交流过
    STATUS_COMPLETED = 'completed'  # 已收尾
    
    STATUS_LABELS = {
        STATUS_RESEARCHING: '研究中',
        STATUS_COMMUNICATED: '交流过',
        STATUS_COMPLETED: '已收尾'
    }
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        初始化服务
        
        Args:
            data_dir: 数据存储目录，默认为 config/data
        """
        if data_dir is None:
            # 使用配置目录下的data子目录
            from pathlib import Path
            data_dir = Path(__file__).parent.parent.parent / 'config' / 'data'
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 状态数据文件路径
        self.status_file = self.data_dir / 'folder_status.json'
        
        # 加载状态数据
        self._status_data = self._load_status_data()
    
    def _load_status_data(self) -> Dict:
        """加载状态数据"""
        if self.status_file.exists():
            try:
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载状态数据失败: {e}")
                return {}
        return {}
    
    def _save_status_data(self):
        """保存状态数据"""
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(self._status_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"状态数据已保存到 {self.status_file}")
        except Exception as e:
            logger.error(f"保存状态数据失败: {e}")
    
    def get_folder_status(self, folder_name: str) -> Optional[str]:
        """
        获取文件夹状态
        
        Args:
            folder_name: 文件夹名称
            
        Returns:
            状态值，如果未设置则返回None
        """
        return self._status_data.get(folder_name)
    
    def set_folder_status(self, folder_name: str, status: str) -> bool:
        """
        设置文件夹状态
        
        Args:
            folder_name: 文件夹名称
            status: 状态值（researching, communicated, completed）
            
        Returns:
            是否设置成功
        """
        if status not in self.STATUS_LABELS:
            logger.error(f"无效的状态值: {status}")
            return False
        
        self._status_data[folder_name] = status
        self._save_status_data()
        
        logger.info(f"文件夹 '{folder_name}' 状态已设置为: {self.STATUS_LABELS[status]}")
        return True
    
    def remove_folder_status(self, folder_name: str) -> bool:
        """
        移除文件夹状态
        
        Args:
            folder_name: 文件夹名称
            
        Returns:
            是否移除成功
        """
        if folder_name in self._status_data:
            del self._status_data[folder_name]
            self._save_status_data()
            logger.info(f"文件夹 '{folder_name}' 状态已移除")
            return True
        return False
    
    def get_all_status(self) -> Dict[str, str]:
        """
        获取所有文件夹状态
        
        Returns:
            文件夹状态字典
        """
        return self._status_data.copy()
    
    def get_status_label(self, status: str) -> str:
        """获取状态的中文标签"""
        return self.STATUS_LABELS.get(status, '未知')
    
    def get_status_icon(self, status: str) -> str:
        """获取状态的图标类名"""
        icons = {
            self.STATUS_RESEARCHING: 'fa-flask',  # 烧瓶图标
            self.STATUS_COMMUNICATED: 'fa-comments',  # 对话图标
            self.STATUS_COMPLETED: 'fa-check-circle'  # 勾选图标
        }
        return icons.get(status, 'fa-question')
    
    def get_status_color(self, status: str) -> str:
        """获取状态的颜色"""
        colors = {
            self.STATUS_RESEARCHING: '#3498db',  # 蓝色
            self.STATUS_COMMUNICATED: '#f39c12',  # 橙色
            self.STATUS_COMPLETED: '#27ae60'  # 绿色
        }
        return colors.get(status, '#95a5a6')


# 全局实例
_folder_status_service = None

def get_folder_status_service() -> FolderStatusService:
    """获取全局文件夹状态服务实例"""
    global _folder_status_service
    if _folder_status_service is None:
        _folder_status_service = FolderStatusService()
    return _folder_status_service

"""
Gallery App 配置文件
"""
import os
from pathlib import Path

# 基础配置
BASE_DIR = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
BACKEND_DIR = BASE_DIR / "backend"

# 服务器配置
SERVER_PORT = int(os.environ.get('GALLERY_PORT', 5202))
SERVER_HOST = os.environ.get('GALLERY_HOST', '0.0.0.0')
DEBUG = os.environ.get('GALLERY_DEBUG', 'False').lower() == 'true'

# 图片根目录配置
IMAGES_ROOT = os.environ.get(
    'GALLERY_IMAGES_ROOT', 
    os.path.expanduser('~/pythoncode/pngs')
)

# Flask配置
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
WTF_CSRF_ENABLED = False  # 对于API接口可以禁用CSRF

# 认证配置
AUTH_CONFIG_FILE = BASE_DIR / "config" / "gallery_config.json"

# 日志配置
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FILE = BASE_DIR / "logs" / "gallery.log"

# 上传配置
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp'}

# 缓存配置
CACHE_TIMEOUT = 300  # 5分钟
CACHE_DIR = BASE_DIR / "cache"

# 分页配置
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# WebSocket配置
SOCKETIO_ASYNC_MODE = 'eventlet'
SOCKETIO_CORS_ALLOWED_ORIGINS = "*"

# 安全配置
CORS_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]

# 文件处理配置
THUMBNAIL_SIZE = (200, 200)
PREVIEW_SIZE = (800, 600)

# 数据库配置（如果需要的话）
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///gallery.db')

class Config:
    """基础配置类"""
    SECRET_KEY = SECRET_KEY
    WTF_CSRF_ENABLED = WTF_CSRF_ENABLED
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH
    
class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    TESTING = False
    
class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    TESTING = False
    
class TestingConfig(Config):
    """测试环境配置"""
    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False

# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
"""
Gallery App 主应用入口
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'backend'))

from flask import Flask, render_template, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO

# 创建全局SocketIO实例
socketio = SocketIO(cors_allowed_origins="*")

# 设置路径
FRONTEND_DIR = PROJECT_ROOT / 'frontend'

# 简化配置
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    WTF_CSRF_ENABLED = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

config = {
    'development': Config,
    'production': Config,
    'testing': Config,
    'default': Config
}

def create_app(config_name=None):
    """创建Flask应用实例"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    app = Flask(__name__, 
                template_folder=str(FRONTEND_DIR / 'templates'),
                static_folder=str(FRONTEND_DIR / 'static'))
    
    # 加载配置
    app.config.from_object(config[config_name])

    # 初始化扩展
    CORS(app)
    socketio.init_app(app, async_mode='threading', cors_allowed_origins="*")

    # 注册蓝图
    register_blueprints(app)
    
    # 注册错误处理器
    register_error_handlers(app)
    
    # 注册模板过滤器
    register_template_filters(app)
    
    return app, socketio

def register_blueprints(app):
    """注册蓝图"""
    from backend.api.gallery_routes import gallery_bp
    from backend.api.auth_routes import auth_bp
    from backend.api.progress_routes import progress_bp
    
    app.register_blueprint(gallery_bp, url_prefix='/gallery')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(progress_bp, url_prefix='/progress')
    
    # 根路由重定向到gallery
    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('gallery.folder_list'))

def register_error_handlers(app):
    """注册错误处理器"""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('error.html', 
                             title='页面未找到',
                             message='您访问的页面不存在'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return render_template('error.html',
                             title='服务器错误',
                             message='服务器内部错误，请稍后重试'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('error.html',
                             title='访问被拒绝',
                             message='您没有权限访问此页面'), 403

def register_template_filters(app):
    """注册模板过滤器"""
    
    @app.template_filter('filesizeformat')
    def filesizeformat(num):
        """格式化文件大小"""
        for unit in ['bytes', 'KB', 'MB', 'GB', 'TB']:
            if num < 1024.0:
                return f"{num:3.1f} {unit}"
            num /= 1024.0
        return f"{num:.1f} PB"
    
    @app.template_filter('date')
    def dateformat(date_string):
        """格式化日期"""
        from datetime import datetime
        try:
            if isinstance(date_string, str):
                date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
            else:
                date_obj = date_string
            return date_obj.strftime('%Y-%m-%d %H:%M')
        except:
            return date_string

if __name__ == '__main__':
    app, socketio = create_app()
    
    from config.settings import SERVER_HOST, SERVER_PORT, DEBUG
    
    print(f"启动Gallery App服务器")
    print(f"访问地址: http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"模式: {'开发' if DEBUG else '生产'}")
    
    socketio.run(app, 
                host=SERVER_HOST, 
                port=SERVER_PORT, 
                debug=DEBUG,
                allow_unsafe_werkzeug=True)
#!/usr/bin/env python3
"""
Gallery App 重构版本启动脚本
"""
import os
import sys
import signal
import logging
from pathlib import Path

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def setup_logging():
    """设置日志"""
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'gallery.log'),
            logging.StreamHandler()
        ]
    )

def check_dependencies():
    """检查依赖"""
    required_packages = [
        'flask', 'flask_cors', 'flask_socketio',
        'eventlet', 'pypinyin', 'psutil'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"缺少以下依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        sys.exit(1)

def create_directories():
    """创建必要的目录"""
    directories = [
        PROJECT_ROOT / "logs",
        PROJECT_ROOT / "cache",
        PROJECT_ROOT / "temp"
    ]
    
    for directory in directories:
        directory.mkdir(exist_ok=True)

def signal_handler(sig, frame):
    """信号处理器"""
    print("\n收到退出信号，正在关闭服务器...")
    sys.exit(0)

def main():
    """主函数"""
    print("=== Gallery App 重构版本 ===")
    print(f"项目路径: {PROJECT_ROOT}")
    
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 初始化
    setup_logging()
    check_dependencies()
    create_directories()
    
    logger = logging.getLogger(__name__)
    logger.info("启动 Gallery App 重构版本")
    
    try:
        # 导入并创建应用
        from backend.app import create_app
        app, socketio = create_app()
        
        # 获取配置
        SERVER_HOST = os.environ.get('GALLERY_HOST', '0.0.0.0')
        SERVER_PORT = int(os.environ.get('GALLERY_PORT', 5202))
        DEBUG = os.environ.get('GALLERY_DEBUG', 'False').lower() == 'true'
        
        logger.info(f"服务器配置:")
        logger.info(f"  地址: {SERVER_HOST}:{SERVER_PORT}")
        logger.info(f"  调试模式: {DEBUG}")
        logger.info(f"  静态文件: {app.static_folder}")
        logger.info(f"  模板目录: {app.template_folder}")
        
        print(f"\n🚀 Gallery App 正在启动...")
        print(f"🌐 访问地址: http://{SERVER_HOST}:{SERVER_PORT}")
        print(f"📁 图片根目录: {os.environ.get('GALLERY_IMAGES_ROOT', '~/pythoncode/pngs')}")
        print(f"🔧 模式: {'开发' if DEBUG else '生产'}")
        print(f"\n按 Ctrl+C 停止服务器\n")
        
        # 启动服务器
        socketio.run(
            app,
            host=SERVER_HOST,
            port=SERVER_PORT,
            debug=DEBUG,
            allow_unsafe_werkzeug=True,
            use_reloader=False  # 避免重复启动
        )
        
    except ImportError as e:
        logger.error(f"导入模块失败: {e}")
        print(f"❌ 启动失败: 导入模块失败 - {e}")
        print("请确保所有依赖已正确安装")
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"启动失败: {e}")
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
Gallery App 重构版本快速启动脚本
"""
import os
import sys
import signal
from pathlib import Path

# 设置项目路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'backend'))

def signal_handler(sig, frame):
    """信号处理器"""
    print("\n📴 收到退出信号，正在关闭服务器...")
    sys.exit(0)

def main():
    """主函数"""
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🚀 Gallery App 重构版本")
    print(f"📁 项目路径: {PROJECT_ROOT}")
    
    # 环境配置
    SERVER_HOST = os.environ.get('GALLERY_HOST', '127.0.0.1')
    SERVER_PORT = int(os.environ.get('GALLERY_PORT', 5202))
    DEBUG = os.environ.get('GALLERY_DEBUG', 'True').lower() == 'true'
    
    print(f"🌐 地址: http://{SERVER_HOST}:{SERVER_PORT}")
    print(f"🔧 调试模式: {DEBUG}")
    print(f"📸 图片目录: {os.environ.get('GALLERY_IMAGES_ROOT', '~/pythoncode/pngs')}")
    
    try:
        # 导入并创建应用
        from backend.app import create_app
        app, socketio = create_app()
        
        print("\n✅ 应用创建成功")
        print("🔄 正在启动服务器...")
        print("\n按 Ctrl+C 停止服务器")
        print("-" * 50)
        
        # 启动服务器
        socketio.run(
            app,
            host=SERVER_HOST,
            port=SERVER_PORT,
            debug=DEBUG,
            allow_unsafe_werkzeug=True,
            use_reloader=False,
            log_output=True
        )
        
    except KeyboardInterrupt:
        print("\n📴 服务器已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
测试应用启动
"""
import sys
from pathlib import Path

# 添加路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'backend'))

def test_imports():
    """测试导入"""
    try:
        print("🔍 测试导入...")
        
        # 测试基础导入
        from backend.app import create_app
        print("✅ 基础导入成功")
        
        # 测试应用创建
        app, socketio = create_app()
        print("✅ 应用创建成功")
        
        # 测试蓝图注册
        print(f"📝 注册的蓝图: {list(app.blueprints.keys())}")
        
        # 测试模板和静态文件路径
        print(f"📂 模板目录: {app.template_folder}")
        print(f"📂 静态文件目录: {app.static_folder}")
        
        # 测试配置
        print(f"🔧 密钥设置: {'✅' if app.config['SECRET_KEY'] else '❌'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_functionality():
    """测试基本功能"""
    try:
        print("\n🔍 测试基本功能...")
        
        from backend.services.gallery_service import GalleryService
        gallery_service = GalleryService()
        print("✅ Gallery 服务创建成功")
        
        from backend.services.auth_service import AuthService
        auth_service = AuthService()
        print("✅ Auth 服务创建成功")
        
        from backend.services.progress_service import ProgressService
        progress_service = ProgressService()
        print("✅ Progress 服务创建成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=== Gallery App 重构版本测试 ===")
    
    success = True
    
    success &= test_imports()
    success &= test_basic_functionality()
    
    if success:
        print("\n🎉 所有测试通过！应用可以正常启动")
    else:
        print("\n❌ 测试失败，请检查错误信息")
        sys.exit(1)
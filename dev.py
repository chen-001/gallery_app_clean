#!/usr/bin/env python3
"""
开发环境启动脚本
"""
import os
import sys
from pathlib import Path

# 设置开发环境
os.environ['FLASK_ENV'] = 'development'
os.environ['GALLERY_DEBUG'] = 'true'

# 添加项目根目录到Python路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

if __name__ == '__main__':
    # 导入并运行服务器
    from run_server import main
    main()
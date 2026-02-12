# CLAUDE.md

always respond in Chinese.
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

- Python路径: `/home/chenzongwei/.conda/envs/chenzongwei311/bin/python`
- Pip路径: `/home/chenzongwei/.conda/envs/chenzongwei311/bin/pip`

## GitHub
- 每次git push之前先运行`git remote -v`查看当前仓库地址，然后再git push
- git push时使用 HTTP_PROXY=http://127.0.0.1:10808 HTTPS_PROXY=http://127.0.0.1:10808 git push设置代理
- 有关git或npm的操作，都要设置这个代理 HTTP_PROXY=http://127.0.0.1:10808 HTTPS_PROXY=http://127.0.0.1:10808
- 用户名称是`chen-001`

## Bash命令
- 上传git时,将所有更改都上传
- 写git commit message时,要详细列出更新的版本号和内容信息
- 不要主动上传git,除非我在prompt中明确要求上传git
- 不要生成markdown文件,除非我在提示词中明确要求.如果要生成一些代码说明文件,请不要单独创建一个markdown文件,而是可以在代码文件中多写些注释,或者使用ipynb文件演示.

## Development Commands

### 启动应用
```bash
# 主要启动方式 - 推荐使用
python start.py

# 服务管理脚本启动（带保活机制）
./gallery_service_clean.sh start

# 开发模式启动
python dev.py

# 完整启动脚本
python run_server.py

# 直接运行应用
python backend/app.py
```

### 服务管理
```bash
# 使用服务管理脚本
./gallery_service_clean.sh start     # 启动服务（带保活机制）
./gallery_service_clean.sh stop      # 停止服务
./gallery_service_clean.sh restart   # 重启服务
./gallery_service_clean.sh status    # 查看服务状态
./gallery_service_clean.sh logs      # 查看实时日志
./gallery_service_clean.sh test      # 测试应用
```

### 开发工具
```bash
# 安装依赖
pip install -r requirements.txt

# 测试应用
python test_app.py

# 代码格式化（如果安装了black）
black .

# 代码检查（如果安装了flake8）
flake8 .

# 运行测试（如果安装了pytest）
pytest
```

### 应用访问
- 服务器默认运行在 `http://localhost:5202`
- 主要访问地址：`/gallery`（文件夹列表）
- 登录页面：`/auth/login`
- 进度监控：`/progress`

## 应用架构

这是一个**重构版本的Flask SVG图片画廊应用**，具有以下架构特点：

### 项目结构
```
gallery_app_clean/
├── backend/                    # 后端代码（模块化设计）
│   ├── api/                   # API路由层
│   │   ├── gallery_routes.py  # 图片画廊API
│   │   ├── auth_routes.py     # 认证API
│   │   └── progress_routes.py # 进度监控API
│   ├── services/              # 业务逻辑层
│   │   ├── gallery_service.py # 图片画廊服务
│   │   ├── auth_service.py    # 认证服务
│   │   └── progress_service.py # 进度监控服务
│   ├── utils/                 # 工具函数
│   └── app.py                 # Flask应用入口
├── frontend/                  # 前端代码（已分离）
│   ├── templates/             # Jinja2模板
│   └── static/                # CSS、JS、图片资源
├── config/                    # 配置管理
│   ├── settings.py           # 应用配置
│   └── gallery_config.json   # 认证配置
└── logs/                      # 日志文件
```

### 核心组件

#### 1. 后端架构（分层设计）
- **API层**：处理HTTP请求，参数验证，响应格式化
- **服务层**：业务逻辑处理，数据操作
- **工具层**：文件操作、缓存、装饰器等通用功能

#### 2. 认证系统
支持多种认证方式（在 `gallery_config.json` 中配置）：
- HTTP头认证（`X-Remote-User`，`X-Forwarded-User`）
- IP地址映射认证
- 手动登录认证
- 会话管理

#### 3. 文件系统
- **两层文件夹结构**：父文件夹 → 子文件夹 → 图片文件
- **SVG主要支持**：专门优化SVG文件的浏览和预览
- **描述文件支持**：支持Markdown描述文件

#### 4. 实时功能
- **WebSocket集成**：使用Flask-SocketIO实现实时通信
- **进度监控**：内置任务进度跟踪和内存管理
- **保活机制**：自动监控和重启服务

## 配置文件

### 环境变量配置
```bash
# 服务器配置
export GALLERY_HOST=0.0.0.0        # 服务器地址
export GALLERY_PORT=5202           # 服务器端口
export GALLERY_DEBUG=false         # 调试模式
export GALLERY_IMAGES_ROOT=/path/to/images  # 图片根目录

# 其他配置
export SECRET_KEY=your-secret-key   # Flask密钥
export LOG_LEVEL=INFO              # 日志级别
```

### 主要配置文件
- `config/settings.py`：应用主配置
- `config/gallery_config.json`：认证和用户配置
- `requirements.txt`：Python依赖包

## 关键依赖

### 核心框架
- **Flask + 扩展**：Flask-CORS、Flask-SocketIO
- **WebSocket**：eventlet、python-socketio
- **中文支持**：pypinyin（用于中文字符排序）
- **系统监控**：psutil（进程管理）

### 数据处理
- **图片处理**：Pillow
- **缓存**：cachetools
- **配置管理**：pydantic、pydantic-settings
- **时间处理**：python-dateutil

### 开发工具
- **测试框架**：pytest、pytest-flask、pytest-cov
- **性能监控**：memory-profiler
- **文件监控**：watchdog

## 重要说明

### 启动和重启
- **每次更新代码后**，请使用 `./gallery_service_clean.sh restart` 重启服务器
- **推荐使用保活机制**：服务脚本会自动监控并重启崩溃的服务
- **默认端口5202**：避免与原版本端口冲突

### 图片根目录
- 默认位置：`~/pythoncode/pngs`
- 可通过环境变量 `GALLERY_IMAGES_ROOT` 自定义
- 支持两层目录结构：父文件夹/子文件夹/图片

### 认证配置
- 修改 `config/gallery_config.json` 来添加/删除用户
- 支持多种认证方式的组合使用
- 生产环境建议启用HTTPS认证

### 日志和监控
- 日志文件：`logs/gallery.log`
- 实时日志：`./gallery_service_clean.sh logs`
- 服务状态：`./gallery_service_clean.sh status`

## 架构优势

1. **模块化设计**：前后端分离，业务逻辑清晰
2. **可扩展性**：分层架构便于添加新功能
3. **易维护性**：代码结构清晰，职责分明
4. **高可用性**：内置保活机制，自动故障恢复
5. **性能优化**：缓存机制，静态资源分离
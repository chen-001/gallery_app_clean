# Gallery App 重构版本

## 项目结构

```
gallery_app_clean/
├── backend/                    # 后端代码
│   ├── api/                   # API路由模块
│   ├── auth/                  # 认证模块
│   ├── services/              # 业务逻辑服务
│   ├── utils/                 # 工具函数
│   ├── models/                # 数据模型
│   └── app.py                 # Flask应用入口
├── frontend/                   # 前端代码
│   ├── templates/             # Jinja2模板
│   ├── static/                # 静态资源
│   │   ├── css/              # 样式文件
│   │   ├── js/               # JavaScript文件
│   │   ├── icons/            # 图标文件
│   │   └── images/           # 图片资源
│   └── components/            # 可复用组件
├── config/                     # 配置文件
└── docs/                      # 文档
```

## 重构目标

1. **代码分离**: 将嵌入在Python代码中的HTML/CSS/JavaScript提取到独立文件
2. **模块化**: 按功能模块组织后端代码
3. **组件化**: 创建可复用的前端组件
4. **配置管理**: 统一管理配置文件
5. **易维护**: 清晰的代码结构，便于扩展和维护

## 运行方式

### 快速启动
```bash
cd gallery_app_clean
python start.py
```

### 开发模式
```bash
cd gallery_app_clean
python dev.py
```

### 完整启动脚本
```bash
cd gallery_app_clean
python run_server.py
```

### 测试应用
```bash
cd gallery_app_clean
python test_app.py
```

### 服务管理
```bash
cd gallery_app_clean

# 使用服务管理脚本
./gallery_service_clean.sh start     # 启动服务
./gallery_service_clean.sh stop      # 停止服务  
./gallery_service_clean.sh restart   # 重启服务
./gallery_service_clean.sh status    # 查看状态
./gallery_service_clean.sh logs      # 查看日志
./gallery_service_clean.sh test      # 测试应用

# 安装为系统服务
./install_service.sh                 # 安装服务脚本到系统
```

服务器将在 http://127.0.0.1:5202 启动（重构版本使用5202端口）

## 环境变量

可以通过环境变量配置应用：

```bash
export GALLERY_HOST=0.0.0.0          # 服务器地址
export GALLERY_PORT=5101             # 服务器端口
export GALLERY_DEBUG=true            # 调试模式
export GALLERY_IMAGES_ROOT=/path/to/images  # 图片根目录
```

## 重构成果

### ✅ 已完成
- [x] 前后端代码完全分离
- [x] 模块化的后端架构（API、服务层、工具层）
- [x] 独立的前端模板和静态资源
- [x] 配置管理系统
- [x] 认证和权限管理
- [x] 进度监控系统
- [x] 缓存机制
- [x] 错误处理和日志记录
- [x] 响应式前端设计

### 🎯 架构优势
1. **可维护性**: 代码结构清晰，职责分明
2. **可扩展性**: 模块化设计，易于添加新功能
3. **可复用性**: 组件化的前端代码
4. **可测试性**: 分层架构便于单元测试
5. **性能优化**: 缓存机制和静态资源分离
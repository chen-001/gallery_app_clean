# Gallery App 重构版本部署指南

## 🚀 快速开始

### 1. 测试应用
```bash
cd gallery_app_clean
python test_app.py
```

### 2. 启动应用
```bash
# 方式一：直接启动
python start.py

# 方式二：使用服务脚本
./gallery_service_clean.sh start

# 方式三：开发模式
python dev.py
```

### 3. 访问应用
- 主页：http://127.0.0.1:5202
- 画廊：http://127.0.0.1:5202/gallery

## 📋 服务管理

### 安装服务管理脚本
```bash
./install_service.sh
```

### 常用服务命令
```bash
# 基本操作
./gallery_service_clean.sh start      # 启动
./gallery_service_clean.sh stop       # 停止
./gallery_service_clean.sh restart    # 重启
./gallery_service_clean.sh status     # 状态

# 日志和监控
./gallery_service_clean.sh logs       # 实时日志
./gallery_service_clean.sh tail       # 最近日志
./gallery_service_clean.sh config     # 配置信息

# 系统服务
./gallery_service_clean.sh install-service  # 安装systemd服务
./gallery_service_clean.sh enable           # 开机自启
./gallery_service_clean.sh disable          # 取消自启

# 维护
./gallery_service_clean.sh test       # 功能测试
./gallery_service_clean.sh cleanup    # 清理文件
```

## ⚙️ 配置说明

### 环境变量配置
```bash
export GALLERY_HOST=127.0.0.1                    # 服务器地址
export GALLERY_PORT=5202                         # 服务器端口
export GALLERY_DEBUG=false                       # 调试模式
export GALLERY_IMAGES_ROOT=/path/to/images       # 图片根目录
```

### 配置文件
- **应用配置**: `config/settings.py`
- **认证配置**: `config/gallery_config.json`
- **环境模板**: `.env.example`

### 认证配置示例
编辑 `config/gallery_config.json`：
```json
{
    "auth_methods": ["header", "manual"],
    "users": {
        "admin": "admin123",
        "user": "user123"
    },
    "show_allowed_users": true
}
```

## 🔧 开发部署

### 开发环境
```bash
# 设置开发环境变量
export GALLERY_DEBUG=true
export GALLERY_PORT=5202

# 启动开发服务器
python dev.py
```

### 生产环境
```bash
# 设置生产环境变量
export GALLERY_DEBUG=false
export GALLERY_HOST=0.0.0.0
export GALLERY_PORT=80

# 安装依赖
pip install -r requirements.txt

# 启动生产服务器
./gallery_service_clean.sh start
```

### systemd 服务部署
```bash
# 安装服务
./gallery_service_clean.sh install-service

# 启用开机自启
./gallery_service_clean.sh enable

# 启动服务
systemctl --user start gallery-app-clean.service

# 查看状态
systemctl --user status gallery-app-clean.service
```

## 📁 目录结构

```
gallery_app_clean/
├── backend/                    # 后端代码
│   ├── api/                   # API路由
│   ├── services/              # 业务服务
│   ├── utils/                 # 工具模块
│   └── app.py                 # Flask应用
├── frontend/                   # 前端代码
│   ├── templates/             # 页面模板
│   └── static/                # 静态资源
├── config/                    # 配置文件
├── logs/                      # 日志文件
├── cache/                     # 缓存目录
├── start.py                   # 快速启动
├── gallery_service_clean.sh   # 服务管理
└── install_service.sh         # 服务安装
```

## 🐛 故障排查

### 常见问题

1. **启动失败**
   ```bash
   # 检查依赖
   python test_app.py
   
   # 查看日志
   ./gallery_service_clean.sh tail
   ```

2. **端口占用**
   ```bash
   # 检查端口
   netstat -tlnp | grep 5202
   
   # 更换端口
   export GALLERY_PORT=8080
   ./gallery_service_clean.sh start
   ```

3. **权限问题**
   ```bash
   # 检查文件权限
   ls -la gallery_service_clean.sh
   
   # 修复权限
   chmod +x gallery_service_clean.sh
   ```

4. **图片目录不存在**
   ```bash
   # 设置正确的图片目录
   export GALLERY_IMAGES_ROOT=/correct/path/to/images
   ./gallery_service_clean.sh restart
   ```

### 日志位置
- **应用日志**: `logs/gallery.log`
- **systemd日志**: `journalctl --user -u gallery-app-clean.service`

### 性能调优
```bash
# 设置环境变量
export GALLERY_CACHE_TIMEOUT=600    # 缓存超时（秒）
export GALLERY_MAX_WORKERS=4        # 工作进程数

# 清理缓存
./gallery_service_clean.sh cleanup
```

## 🔄 版本升级

### 从原版本迁移
1. 备份原有配置文件
2. 停止原服务：`/home/chenzongwei/pythoncode/gallery_service.sh stop`
3. 启动新版本：`./gallery_service_clean.sh start`
4. 验证功能正常

### 更新应用
```bash
# 停止服务
./gallery_service_clean.sh stop

# 更新代码
git pull

# 安装依赖
pip install -r requirements.txt

# 测试应用
python test_app.py

# 启动服务
./gallery_service_clean.sh start
```

## 📞 技术支持

- **测试命令**: `python test_app.py`
- **配置检查**: `./gallery_service_clean.sh config`
- **实时日志**: `./gallery_service_clean.sh logs`
- **状态检查**: `./gallery_service_clean.sh status`
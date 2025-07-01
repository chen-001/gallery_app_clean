#!/bin/bash

# Gallery App 重构版本服务安装脚本

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_NAME="gallery_service_clean.sh"
TARGET_DIR="/home/chenzongwei/pythoncode"
TARGET_SCRIPT="$TARGET_DIR/gallery_service_clean.sh"

echo -e "${BLUE}=== Gallery App 重构版本服务安装 ===${NC}"
echo -e "项目目录: ${BLUE}$PROJECT_DIR${NC}"
echo -e "目标位置: ${BLUE}$TARGET_SCRIPT${NC}"

# 检查源文件
if [ ! -f "$PROJECT_DIR/$SCRIPT_NAME" ]; then
    echo -e "${RED}✗ 源文件不存在: $PROJECT_DIR/$SCRIPT_NAME${NC}"
    exit 1
fi

# 创建目标目录
if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${YELLOW}创建目标目录: $TARGET_DIR${NC}"
    mkdir -p "$TARGET_DIR"
fi

# 备份现有文件
if [ -f "$TARGET_SCRIPT" ]; then
    echo -e "${YELLOW}备份现有文件...${NC}"
    cp "$TARGET_SCRIPT" "$TARGET_SCRIPT.backup.$(date +%Y%m%d_%H%M%S)"
fi

# 复制服务脚本
echo -e "${BLUE}复制服务脚本...${NC}"
cp "$PROJECT_DIR/$SCRIPT_NAME" "$TARGET_SCRIPT"

# 设置执行权限
chmod +x "$TARGET_SCRIPT"

# 验证安装
if [ -f "$TARGET_SCRIPT" ] && [ -x "$TARGET_SCRIPT" ]; then
    echo -e "${GREEN}✓ 服务脚本安装成功${NC}"
    echo -e "使用方法:"
    echo -e "  ${BLUE}$TARGET_SCRIPT start${NC}    # 启动服务"
    echo -e "  ${BLUE}$TARGET_SCRIPT status${NC}   # 查看状态"
    echo -e "  ${BLUE}$TARGET_SCRIPT help${NC}     # 查看帮助"
    
    # 创建软链接到 /usr/local/bin（可选）
    if [ -w "/usr/local/bin" ]; then
        echo -e "${BLUE}创建全局命令链接...${NC}"
        ln -sf "$TARGET_SCRIPT" "/usr/local/bin/gallery-clean"
        echo -e "${GREEN}✓ 可以使用 'gallery-clean' 命令${NC}"
    fi
    
    echo -e "\n${GREEN}安装完成！${NC}"
    echo -e "测试安装: ${BLUE}$TARGET_SCRIPT test${NC}"
else
    echo -e "${RED}✗ 服务脚本安装失败${NC}"
    exit 1
fi
#!/bin/bash

# Gallery App 重构版本 服务管理脚本
# 用于管理重构后的Gallery App应用

# 项目配置
PROJECT_DIR="/home/chenzongwei/gallery_app/gallery_app_clean"
PYTHON_PATH="/home/chenzongwei/.conda/envs/chenzongwei311/bin/python"
START_SCRIPT="start.py"
SERVICE_NAME="gallery-app-clean.service"
LOG_FILE="$PROJECT_DIR/logs/gallery.log"
PID_FILE="$PROJECT_DIR/gallery.pid"
DAEMON_PID_FILE="$PROJECT_DIR/daemon.pid"

# 默认配置
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="5202"
DEFAULT_DEBUG="false"
DEFAULT_IMAGES_ROOT="/home/chenzongwei/pythoncode/pngs"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}===========================================================${NC}"
    echo -e "${BLUE}           Gallery App 重构版本 服务管理工具${NC}"
    echo -e "${BLUE}===========================================================${NC}"
    echo -e "${CYAN}项目目录: ${PROJECT_DIR}${NC}"
    echo -e "${CYAN}Python: ${PYTHON_PATH}${NC}"
    echo -e "${CYAN}启动脚本: ${START_SCRIPT}${NC}"
}

check_dependencies() {
    echo -e "${BLUE}检查依赖...${NC}"
    
    # 检查Python路径
    if [ ! -f "$PYTHON_PATH" ]; then
        echo -e "${RED}✗ Python路径不存在: $PYTHON_PATH${NC}"
        return 1
    fi
    
    # 检查项目目录
    if [ ! -d "$PROJECT_DIR" ]; then
        echo -e "${RED}✗ 项目目录不存在: $PROJECT_DIR${NC}"
        return 1
    fi
    
    # 检查启动脚本
    if [ ! -f "$PROJECT_DIR/$START_SCRIPT" ]; then
        echo -e "${RED}✗ 启动脚本不存在: $PROJECT_DIR/$START_SCRIPT${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ 依赖检查通过${NC}"
    return 0
}

get_pid() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "$pid"
            return 0
        else
            rm -f "$PID_FILE"
        fi
    fi
    
    # 备用方法：通过进程名查找
    local pid=$(ps aux | grep "$START_SCRIPT" | grep -v grep | awk '{print $2}' | head -1)
    if [ -n "$pid" ]; then
        echo "$pid"
        return 0
    fi
    
    return 1
}

check_process() {
    local pid=$(get_pid)
    if [ -n "$pid" ]; then
        echo -e "${GREEN}Gallery App 重构版本正在运行 (PID: $pid)${NC}"
        
        # 显示监听端口
        local port=$(netstat -tlnp 2>/dev/null | grep ":$pid " | grep -o ":[0-9]*" | head -1 | cut -c2-)
        if [ -n "$port" ]; then
            echo -e "${CYAN}监听端口: $port${NC}"
            echo -e "${CYAN}访问地址: http://localhost:$port${NC}"
        fi
        return 0
    else
        echo -e "${RED}Gallery App 重构版本未运行${NC}"
        return 1
    fi
}

start_app() {
    # 设置环境变量
    export GALLERY_HOST="${GALLERY_HOST:-$DEFAULT_HOST}"
    export GALLERY_PORT="${GALLERY_PORT:-$DEFAULT_PORT}"
    export GALLERY_DEBUG="${GALLERY_DEBUG:-$DEFAULT_DEBUG}"
    export GALLERY_IMAGES_ROOT="${GALLERY_IMAGES_ROOT:-$DEFAULT_IMAGES_ROOT}"
    
    # 启动应用
    cd "$PROJECT_DIR"
    nohup "$PYTHON_PATH" "$START_SCRIPT" > "$LOG_FILE" 2>&1 &
    local pid=$!
    
    # 保存PID
    echo "$pid" > "$PID_FILE"
    
    return 0
}

daemon_process() {
    echo -e "${BLUE}启动守护进程保活模式...${NC}"
    
    # 创建日志目录
    mkdir -p "$(dirname "$LOG_FILE")"
    
    while true; do
        # 检查应用是否运行
        if ! check_process > /dev/null 2>&1; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') - 检测到服务已停止，正在重启..." >> "$LOG_FILE"
            start_app
            sleep 3
            
            if check_process > /dev/null 2>&1; then
                echo "$(date '+%Y-%m-%d %H:%M:%S') - 服务重启成功" >> "$LOG_FILE"
            else
                echo "$(date '+%Y-%m-%d %H:%M:%S') - 服务重启失败，等待下次尝试" >> "$LOG_FILE"
            fi
        fi
        
        # 每5秒检查一次
        sleep 5
    done
}

start_daemon() {
    echo -e "${BLUE}启动 Gallery App 保活守护模式...${NC}"
    
    # 检查依赖
    if ! check_dependencies; then
        return 1
    fi
    
    # 检查守护进程是否已运行
    if [ -f "$DAEMON_PID_FILE" ]; then
        local daemon_pid=$(cat "$DAEMON_PID_FILE" 2>/dev/null)
        if [ -n "$daemon_pid" ] && kill -0 "$daemon_pid" 2>/dev/null; then
            echo -e "${YELLOW}守护进程已在运行 (PID: $daemon_pid)${NC}"
            return 0
        else
            rm -f "$DAEMON_PID_FILE"
        fi
    fi
    
    # 设置环境变量
    export GALLERY_HOST="${GALLERY_HOST:-$DEFAULT_HOST}"
    export GALLERY_PORT="${GALLERY_PORT:-$DEFAULT_PORT}"
    export GALLERY_DEBUG="${GALLERY_DEBUG:-$DEFAULT_DEBUG}"
    export GALLERY_IMAGES_ROOT="${GALLERY_IMAGES_ROOT:-$DEFAULT_IMAGES_ROOT}"
    
    echo -e "${CYAN}环境配置:${NC}"
    echo -e "  HOST: $GALLERY_HOST"
    echo -e "  PORT: $GALLERY_PORT"
    echo -e "  DEBUG: $GALLERY_DEBUG"
    echo -e "  IMAGES_ROOT: $GALLERY_IMAGES_ROOT"
    
    # 启动守护进程
    daemon_process &
    local daemon_pid=$!
    echo "$daemon_pid" > "$DAEMON_PID_FILE"
    
    # 等待启动
    sleep 3
    
    if check_process > /dev/null; then
        echo -e "${GREEN}✓ Gallery App 保活守护模式启动成功${NC}"
        echo -e "守护进程PID: ${CYAN}$daemon_pid${NC}"
        echo -e "访问地址: ${BLUE}http://$GALLERY_HOST:$GALLERY_PORT${NC}"
        echo -e "日志文件: ${CYAN}$LOG_FILE${NC}"
        return 0
    else
        echo -e "${RED}✗ Gallery App 保活守护模式启动失败${NC}"
        kill "$daemon_pid" 2>/dev/null
        rm -f "$DAEMON_PID_FILE"
        echo -e "${YELLOW}查看日志文件获取详细信息: $LOG_FILE${NC}"
        return 1
    fi
}

start_service() {
    echo -e "${BLUE}启动 Gallery App 保活服务...${NC}"
    
    # 检查依赖
    if ! check_dependencies; then
        return 1
    fi
    
    # 检查守护进程是否已运行
    if [ -f "$DAEMON_PID_FILE" ]; then
        local daemon_pid=$(cat "$DAEMON_PID_FILE" 2>/dev/null)
        if [ -n "$daemon_pid" ] && kill -0 "$daemon_pid" 2>/dev/null; then
            echo -e "${YELLOW}保活服务已在运行 (守护进程PID: $daemon_pid)${NC}"
            check_process
            return 0
        else
            rm -f "$DAEMON_PID_FILE"
        fi
    fi
    
    # 设置环境变量
    export GALLERY_HOST="${GALLERY_HOST:-$DEFAULT_HOST}"
    export GALLERY_PORT="${GALLERY_PORT:-$DEFAULT_PORT}"
    export GALLERY_DEBUG="${GALLERY_DEBUG:-$DEFAULT_DEBUG}"
    export GALLERY_IMAGES_ROOT="${GALLERY_IMAGES_ROOT:-$DEFAULT_IMAGES_ROOT}"
    
    echo -e "${CYAN}环境配置:${NC}"
    echo -e "  HOST: $GALLERY_HOST"
    echo -e "  PORT: $GALLERY_PORT"
    echo -e "  DEBUG: $GALLERY_DEBUG"
    echo -e "  IMAGES_ROOT: $GALLERY_IMAGES_ROOT"
    
    # 启动守护进程
    daemon_process &
    local daemon_pid=$!
    echo "$daemon_pid" > "$DAEMON_PID_FILE"
    
    # 等待启动
    sleep 3
    
    if check_process > /dev/null; then
        echo -e "${GREEN}✓ Gallery App 保活服务启动成功${NC}"
        echo -e "守护进程PID: ${CYAN}$daemon_pid${NC}"
        echo -e "访问地址: ${BLUE}http://$GALLERY_HOST:$GALLERY_PORT${NC}"
        echo -e "日志文件: ${CYAN}$LOG_FILE${NC}"
        echo -e "${YELLOW}保活机制已启用 - 服务被杀死后会自动重启${NC}"
        return 0
    else
        echo -e "${RED}✗ Gallery App 保活服务启动失败${NC}"
        kill "$daemon_pid" 2>/dev/null
        rm -f "$DAEMON_PID_FILE"
        echo -e "${YELLOW}查看日志文件获取详细信息: $LOG_FILE${NC}"
        return 1
    fi
}

stop_service() {
    echo -e "${BLUE}停止 Gallery App 保活服务...${NC}"
    
    # 停止守护进程
    if [ -f "$DAEMON_PID_FILE" ]; then
        local daemon_pid=$(cat "$DAEMON_PID_FILE" 2>/dev/null)
        if [ -n "$daemon_pid" ] && kill -0 "$daemon_pid" 2>/dev/null; then
            echo -e "${YELLOW}正在停止守护进程 (PID: $daemon_pid)...${NC}"
            kill "$daemon_pid" 2>/dev/null
            
            # 等待守护进程结束
            local count=0
            while [ $count -lt 5 ]; do
                if ! kill -0 "$daemon_pid" 2>/dev/null; then
                    break
                fi
                sleep 1
                count=$((count + 1))
            done
            
            # 如果仍在运行，强制结束
            if kill -0 "$daemon_pid" 2>/dev/null; then
                kill -9 "$daemon_pid" 2>/dev/null
            fi
            
            echo -e "${GREEN}✓ 守护进程已停止${NC}"
        fi
        rm -f "$DAEMON_PID_FILE"
    fi
    
    # 停止应用
    local pid=$(get_pid)
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}正在停止应用进程 (PID: $pid)...${NC}"
        
        # 发送TERM信号
        kill "$pid" 2>/dev/null
        
        # 等待进程结束
        local count=0
        while [ $count -lt 10 ]; do
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 1
            count=$((count + 1))
        done
        
        # 如果仍在运行，强制结束
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}强制结束应用进程...${NC}"
            kill -9 "$pid" 2>/dev/null
            sleep 1
        fi
        
        # 清理PID文件
        rm -f "$PID_FILE"
        
        if ! check_process > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Gallery App 保活服务停止成功${NC}"
            return 0
        else
            echo -e "${RED}✗ Gallery App 保活服务停止失败${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}Gallery App 应用未运行${NC}"
        return 0
    fi
}

stop_direct() {
    echo -e "${BLUE}直接停止 Gallery App 重构版本...${NC}"
    
    local pid=$(get_pid)
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}正在停止进程 (PID: $pid)...${NC}"
        
        # 发送TERM信号
        kill "$pid" 2>/dev/null
        
        # 等待进程结束
        local count=0
        while [ $count -lt 10 ]; do
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 1
            count=$((count + 1))
        done
        
        # 如果仍在运行，强制结束
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}强制结束进程...${NC}"
            kill -9 "$pid" 2>/dev/null
            sleep 1
        fi
        
        # 清理PID文件
        rm -f "$PID_FILE"
        
        if ! check_process > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Gallery App 重构版本停止成功${NC}"
            return 0
        else
            echo -e "${RED}✗ Gallery App 重构版本停止失败${NC}"
            return 1
        fi
    else
        echo -e "${YELLOW}Gallery App 重构版本未运行${NC}"
        return 0
    fi
}

restart_service() {
    echo -e "${BLUE}重启 Gallery App 保活服务...${NC}"
    
    # 先停止保活服务
    stop_service
    
    # 等待一下
    sleep 2
    
    # 再启动保活服务
    start_service
}

test_app() {
    echo -e "${BLUE}测试应用功能...${NC}"
    
    cd "$PROJECT_DIR"
    "$PYTHON_PATH" test_app.py
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 应用测试通过${NC}"
        return 0
    else
        echo -e "${RED}✗ 应用测试失败${NC}"
        return 1
    fi
}

show_config() {
    echo -e "\n${BLUE}=== 当前配置 ===${NC}"
    echo -e "项目目录: ${CYAN}$PROJECT_DIR${NC}"
    echo -e "Python路径: ${CYAN}$PYTHON_PATH${NC}"
    echo -e "启动脚本: ${CYAN}$START_SCRIPT${NC}"
    echo -e "日志文件: ${CYAN}$LOG_FILE${NC}"
    echo -e "PID文件: ${CYAN}$PID_FILE${NC}"
    
    echo -e "\n${BLUE}=== 环境变量 ===${NC}"
    echo -e "GALLERY_HOST: ${CYAN}${GALLERY_HOST:-$DEFAULT_HOST}${NC}"
    echo -e "GALLERY_PORT: ${CYAN}${GALLERY_PORT:-$DEFAULT_PORT}${NC}"
    echo -e "GALLERY_DEBUG: ${CYAN}${GALLERY_DEBUG:-$DEFAULT_DEBUG}${NC}"
    echo -e "GALLERY_IMAGES_ROOT: ${CYAN}${GALLERY_IMAGES_ROOT:-$DEFAULT_IMAGES_ROOT}${NC}"
}

show_logs() {
    echo -e "\n${BLUE}=== 实时日志 ===${NC}"
    echo -e "日志文件: ${CYAN}$LOG_FILE${NC}"
    echo -e "按 ${YELLOW}Ctrl+C${NC} 退出"
    echo ""
    
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo -e "${YELLOW}日志文件不存在${NC}"
        return 1
    fi
}

show_logs_tail() {
    echo -e "\n${BLUE}=== 最近50行日志 ===${NC}"
    
    if [ -f "$LOG_FILE" ]; then
        tail -50 "$LOG_FILE"
    else
        echo -e "${YELLOW}日志文件不存在${NC}"
        return 1
    fi
}

print_status() {
    echo -e "\n${YELLOW}=== 服务状态 ===${NC}"
    
    check_process
    local status=$?
    
    # 检查守护进程状态
    if [ -f "$DAEMON_PID_FILE" ]; then
        local daemon_pid=$(cat "$DAEMON_PID_FILE" 2>/dev/null)
        if [ -n "$daemon_pid" ] && kill -0 "$daemon_pid" 2>/dev/null; then
            echo -e "${GREEN}守护进程正在运行 (PID: $daemon_pid)${NC}"
        else
            echo -e "${RED}守护进程未运行${NC}"
            rm -f "$DAEMON_PID_FILE"
        fi
    else
        echo -e "${YELLOW}守护进程未启用${NC}"
    fi
    
    echo -e "\n${BLUE}=== 系统信息 ===${NC}"
    echo -e "时间: ${CYAN}$(date)${NC}"
    echo -e "系统负载: ${CYAN}$(uptime | awk -F'load average:' '{print $2}')${NC}"
    
    # 检查端口占用
    local port="${GALLERY_PORT:-$DEFAULT_PORT}"
    local port_status=$(netstat -tln 2>/dev/null | grep ":$port ")
    if [ -n "$port_status" ]; then
        echo -e "端口 $port: ${GREEN}已监听${NC}"
    else
        echo -e "端口 $port: ${RED}未监听${NC}"
    fi
    
    # 检查日志文件
    if [ -f "$LOG_FILE" ]; then
        local log_size=$(du -h "$LOG_FILE" | awk '{print $1}')
        echo -e "日志文件: ${CYAN}存在 ($log_size)${NC}"
    else
        echo -e "日志文件: ${YELLOW}不存在${NC}"
    fi
    
    return $status
}

install_systemd_service() {
    echo -e "\n${GREEN}安装 systemd 用户服务...${NC}"
    
    local service_dir="$HOME/.config/systemd/user"
    mkdir -p "$service_dir"
    
    cat > "$service_dir/$SERVICE_NAME" << EOF
[Unit]
Description=Gallery App Clean Version
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=GALLERY_HOST=${GALLERY_HOST:-$DEFAULT_HOST}
Environment=GALLERY_PORT=${GALLERY_PORT:-$DEFAULT_PORT}
Environment=GALLERY_DEBUG=${GALLERY_DEBUG:-$DEFAULT_DEBUG}
Environment=GALLERY_IMAGES_ROOT=${GALLERY_IMAGES_ROOT:-$DEFAULT_IMAGES_ROOT}
ExecStart=$PYTHON_PATH $PROJECT_DIR/$START_SCRIPT
Restart=always
RestartSec=3
StandardOutput=append:$LOG_FILE
StandardError=append:$LOG_FILE

[Install]
WantedBy=default.target
EOF
    
    systemctl --user daemon-reload
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ systemd 服务安装成功${NC}"
        echo -e "服务文件: ${CYAN}$service_dir/$SERVICE_NAME${NC}"
        return 0
    else
        echo -e "${RED}✗ systemd 服务安装失败${NC}"
        return 1
    fi
}

cleanup() {
    echo -e "\n${BLUE}清理临时文件...${NC}"
    
    # 清理PID文件
    if [ -f "$PID_FILE" ]; then
        rm -f "$PID_FILE"
        echo -e "${GREEN}✓ 已清理PID文件${NC}"
    fi
    
    # 清理守护进程PID文件
    if [ -f "$DAEMON_PID_FILE" ]; then
        rm -f "$DAEMON_PID_FILE"
        echo -e "${GREEN}✓ 已清理守护进程PID文件${NC}"
    fi
    
    # 清理日志文件（可选）
    if [ "$1" = "logs" ] && [ -f "$LOG_FILE" ]; then
        rm -f "$LOG_FILE"
        echo -e "${GREEN}✓ 已清理日志文件${NC}"
    fi
}

show_help() {
    print_header
    echo -e "\n使用方法: $0 [命令] [选项]"
    echo -e "\n${GREEN}基本命令:${NC}"
    echo -e "  ${GREEN}start${NC}           - 启动保活服务（自动重启机制）"
    echo -e "  ${YELLOW}stop${NC}            - 停止保活服务"
    echo -e "  ${BLUE}restart${NC}         - 重启保活服务"
    echo -e "  ${BLUE}status${NC}          - 查看服务状态"
    echo -e "  ${PURPLE}test${NC}            - 测试应用"
    
    echo -e "\n${GREEN}日志和监控:${NC}"
    echo -e "  ${BLUE}logs${NC}            - 查看实时日志"
    echo -e "  ${BLUE}tail${NC}            - 查看最近日志"
    echo -e "  ${CYAN}config${NC}          - 显示配置信息"
    
    echo -e "\n${GREEN}系统服务:${NC}"
    echo -e "  ${GREEN}install-service${NC} - 安装systemd服务"
    echo -e "  ${GREEN}enable${NC}          - 启用开机自启"
    echo -e "  ${YELLOW}disable${NC}         - 禁用开机自启"
    
    echo -e "\n${GREEN}维护命令:${NC}"
    echo -e "  ${CYAN}cleanup${NC}         - 清理临时文件"
    echo -e "  ${CYAN}cleanup logs${NC}    - 清理临时文件和日志"
    echo -e "  ${BLUE}help${NC}            - 显示此帮助信息"
    
    echo -e "\n${GREEN}环境变量:${NC}"
    echo -e "  ${CYAN}GALLERY_HOST${NC}        - 服务器地址 (默认: $DEFAULT_HOST)"
    echo -e "  ${CYAN}GALLERY_PORT${NC}        - 服务器端口 (默认: $DEFAULT_PORT)"
    echo -e "  ${CYAN}GALLERY_DEBUG${NC}       - 调试模式 (默认: $DEFAULT_DEBUG)"
    echo -e "  ${CYAN}GALLERY_IMAGES_ROOT${NC} - 图片根目录 (默认: $DEFAULT_IMAGES_ROOT)"
    
    echo -e "\n${GREEN}保活机制说明:${NC}"
    echo -e "  ${YELLOW}所有启动命令都会自动启用保活机制${NC}"
    echo -e "  守护进程每5秒检查应用状态，如果应用被杀死会自动重启"
    echo -e "  即使杀死所有Python进程，服务也会在5秒内自动恢复"
    echo -e "  推荐使用此机制确保生产环境服务稳定运行"
    
    echo -e "\n${GREEN}示例:${NC}"
    echo -e "  $0 start                    # 启动保活服务"
    echo -e "  $0 restart                  # 重启保活服务" 
    echo -e "  $0 status                   # 查看服务状态"
    echo -e "  $0 stop                     # 停止保活服务"
    echo -e "  GALLERY_PORT=8080 $0 start  # 指定端口启动保活服务"
    echo -e "  $0 logs                     # 查看实时日志"
}

# 主程序
case "$1" in
    start)
        print_header
        start_service
        ;;
    stop)
        print_header
        stop_service
        ;;
    restart)
        print_header
        restart_service
        ;;
    status)
        print_header
        print_status
        ;;
    test)
        print_header
        test_app
        ;;
    config)
        print_header
        show_config
        ;;
    logs)
        print_header
        show_logs
        ;;
    tail)
        print_header
        show_logs_tail
        ;;
    install-service)
        print_header
        install_systemd_service
        ;;
    enable)
        print_header
        systemctl --user enable $SERVICE_NAME
        echo -e "${GREEN}✓ 服务已启用（开机自启）${NC}"
        ;;
    disable)
        print_header
        systemctl --user disable $SERVICE_NAME
        echo -e "${YELLOW}✓ 服务已禁用（取消开机自启）${NC}"
        ;;
    cleanup)
        print_header
        cleanup "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        exit 1
        ;;
esac
#!/bin/bash
# Noveris AI - 环境初始化脚本
# 支持: Linux/macOS (bash), Windows (PowerShell)

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 命令未找到，请先安装"
        return 1
    fi
    return 0
}

# 获取操作系统类型
get_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux" ;;
        Darwin*)    echo "macos" ;;
        CYGWIN*|MINGW*|MSYS*) echo "windows" ;;
        *)          echo "unknown" ;;
    esac
}

# 主函数
main() {
    local os_type
    os_type=$(get_os)

    log_info "Noveris AI 开发环境初始化脚本"
    log_info "检测到的操作系统: $os_type"
    echo

    # 检查必要的工具
    log_info "检查必要的工具..."

    # 检查Git
    if check_command "git"; then
        local git_version
        git_version=$(git --version | cut -d' ' -f3)
        log_success "Git 已安装: $git_version"
    else
        log_error "请安装 Git: https://git-scm.com/"
        exit 1
    fi

    # 检查Docker
    if check_command "docker"; then
        local docker_version
        docker_version=$(docker --version | cut -d' ' -f3 | tr -d ',')
        log_success "Docker 已安装: $docker_version"

        # 检查Docker Compose
        if check_command "docker-compose"; then
            local compose_version
            compose_version=$(docker-compose --version | cut -d' ' -f3)
            log_success "Docker Compose 已安装: $compose_version"
        elif docker compose version &> /dev/null; then
            local compose_version
            compose_version=$(docker compose version | cut -d' ' -f4)
            log_success "Docker Compose V2 已安装: $compose_version"
        else
            log_error "Docker Compose 未找到"
            exit 1
        fi
    else
        log_error "请安装 Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi

    # 检查Python (仅后端开发需要)
    if check_command "python3"; then
        local python_version
        python_version=$(python3 --version | cut -d' ' -f2)
        log_success "Python3 已安装: $python_version"
    elif check_command "python"; then
        local python_version
        python_version=$(python --version | cut -d' ' -f2)
        if [[ $python_version == 3* ]]; then
            log_success "Python 已安装: $python_version"
        else
            log_warning "Python 版本可能过低: $python_version，建议升级到 Python 3.11+"
        fi
    else
        log_warning "Python 未找到，后端开发需要 Python 3.11+"
    fi

    # 检查Node.js (仅前端开发需要)
    if check_command "node"; then
        local node_version
        node_version=$(node --version)
        log_success "Node.js 已安装: $node_version"

        if check_command "npm"; then
            local npm_version
            npm_version=$(npm --version)
            log_success "npm 已安装: $npm_version"
        else
            log_error "npm 未找到"
            exit 1
        fi
    else
        log_warning "Node.js 未找到，前端开发需要 Node.js 18+"
    fi

    # 检查Make (可选)
    if check_command "make"; then
        log_success "Make 已安装"
    else
        log_warning "Make 未找到，一些构建任务可能无法执行"
    fi

    echo
    log_info "环境检查完成，开始初始化项目..."

    # 创建必要的目录
    log_info "创建项目目录结构..."
    mkdir -p Backend Frontend Deploy/{Postgres,Redis,Minio,Elastic,Build} \
           Scripts/{bootstrap,db,ci,ops} Docs

    # 复制环境变量模板
    if [ -f "env-example-template.txt" ]; then
        if [ ! -f ".env" ]; then
            cp env-example-template.txt .env
            log_success "已创建 .env 文件，请根据需要修改配置"
        else
            log_warning ".env 文件已存在，跳过创建"
        fi
    else
        log_warning "env-example-template.txt 文件不存在"
    fi

    # 初始化Git仓库（如果还没有）
    if [ ! -d ".git" ]; then
        log_info "初始化Git仓库..."
        git init
        log_success "Git仓库已初始化"
    fi

    # 创建.gitignore（如果不存在）
    if [ ! -f ".gitignore" ]; then
        cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
lerna-debug.log*

# Environment variables
.env
.env.local
.env.development.local
.env.test.local
.env.production.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Docker
.docker/

# Temporary files
tmp/
temp/
EOF
        log_success "已创建 .gitignore 文件"
    fi

    # 设置目录权限
    log_info "设置目录权限..."
    find . -type d -exec chmod 755 {} \;
    find . -name "*.sh" -exec chmod +x {} \;

    echo
    log_success "项目初始化完成！"
    echo
    log_info "接下来你可以："
    echo "  1. 修改 .env 文件中的配置"
    echo "  2. 运行 'make up' 或 'docker-compose up -d' 启动开发环境"
    echo "  3. 查看 Docs/ 目录中的规范文档"
    echo "  4. 运行 'Scripts/bootstrap/setup-dev.sh' 进行开发环境设置"
    echo
    log_info "如需帮助，请查看 README.md 或 Docs/00-INDEX.md"
}

# 检查是否以正确方式运行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

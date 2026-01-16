#!/bin/bash
# Noveris AI - 代码检查脚本

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# 检查Python代码
check_python() {
    log_info "检查Python代码..."

    if [ ! -d "Backend" ]; then
        log_warning "Backend目录不存在，跳过Python检查"
        return 0
    fi

    cd Backend

    # 检查flake8
    if command -v flake8 &> /dev/null; then
        log_info "运行flake8..."
        if flake8 .; then
            log_success "flake8检查通过"
        else
            log_error "flake8检查失败"
            return 1
        fi
    else
        log_warning "flake8未安装，跳过"
    fi

    # 检查mypy
    if command -v mypy &> /dev/null; then
        log_info "运行mypy..."
        if mypy .; then
            log_success "mypy检查通过"
        else
            log_error "mypy检查失败"
            return 1
        fi
    else
        log_warning "mypy未安装，跳过"
    fi

    # 检查black
    if command -v black &> /dev/null; then
        log_info "检查black格式..."
        if black --check .; then
            log_success "black格式检查通过"
        else
            log_error "black格式检查失败"
            return 1
        fi
    else
        log_warning "black未安装，跳过"
    fi

    cd ..
}

# 检查JavaScript/TypeScript代码
check_javascript() {
    log_info "检查JavaScript/TypeScript代码..."

    if [ ! -d "Frontend" ]; then
        log_warning "Frontend目录不存在，跳过JS检查"
        return 0
    fi

    cd Frontend

    # 检查ESLint
    if command -v npx &> /dev/null; then
        log_info "运行ESLint..."
        if npx eslint .; then
            log_success "ESLint检查通过"
        else
            log_error "ESLint检查失败"
            return 1
        fi
    else
        log_warning "npx未找到，跳过ESLint检查"
    fi

    cd ..
}

# 检查配置文件
check_config() {
    log_info "检查配置文件..."

    # 检查环境变量硬编码
    log_info "检查环境变量硬编码..."
    if grep -r "os\.getenv\|process\.env" --include="*.py" --include="*.js" --include="*.ts" . | grep -v "os\.getenv\|process\.env" | grep -E "(localhost|127\.0\.0\.1|password|secret|key)" ; then
        log_error "发现可能的硬编码配置"
        return 1
    else
        log_success "未发现硬编码配置"
    fi
}

# 显示帮助信息
show_help() {
    cat << EOF
Noveris AI - 代码检查工具

用法:
  $0 [选项]

选项:
  --python      只检查Python代码
  --javascript  只检查JavaScript/TypeScript代码
  --config      只检查配置文件
  -h, --help    显示帮助信息

检查内容:
  Python: flake8, mypy, black
  JavaScript: ESLint
  Config: 硬编码检查

EOF
}

# 主函数
main() {
    local check_python=true
    local check_javascript=true
    local check_config=true

    # 参数解析
    while [[ $# -gt 0 ]]; do
        case $1 in
            --python)
                check_python=true
                check_javascript=false
                check_config=false
                shift
                ;;
            --javascript)
                check_python=false
                check_javascript=true
                check_config=false
                shift
                ;;
            --config)
                check_python=false
                check_javascript=false
                check_config=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知选项: $1"
                show_help
                exit 1
                ;;
        esac
    done

    log_info "开始代码检查..."

    local failed=false

    if [ "$check_python" = true ]; then
        if ! check_python; then
            failed=true
        fi
    fi

    if [ "$check_javascript" = true ]; then
        if ! check_javascript; then
            failed=true
        fi
    fi

    if [ "$check_config" = true ]; then
        if ! check_config; then
            failed=true
        fi
    fi

    if [ "$failed" = true ]; then
        log_error "代码检查失败"
        exit 1
    else
        log_success "所有代码检查通过"
    fi
}

main "$@"

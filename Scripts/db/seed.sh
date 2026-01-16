#!/bin/bash
# Noveris AI - 数据库种子数据脚本

set -e

# 加载环境变量
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 默认配置
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-noveris_db}
DB_USER=${DB_USER:-noveris_user}
DB_PASSWORD=${DB_PASSWORD:-password}
SEED_DIR=${SEED_DIR:-Scripts/db/seeds}

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

# 检查数据库连接
check_db_connection() {
    log_info "检查数据库连接..."

    if command -v psql &> /dev/null; then
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
            log_success "数据库连接正常"
            return 0
        fi
    fi

    log_error "数据库连接失败"
    return 1
}

# 执行种子文件
run_seed() {
    local seed_file="$1"
    local table_name
    table_name=$(basename "$seed_file" .sql)

    log_info "执行种子数据: $table_name"

    if command -v psql &> /dev/null; then
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$seed_file"; then
            log_success "种子数据 $table_name 执行成功"
        else
            log_error "种子数据 $table_name 执行失败"
            return 1
        fi
    else
        log_error "psql 命令未找到"
        return 1
    fi
}

# 显示帮助信息
show_help() {
    cat << EOF
Noveris AI - 数据库种子数据工具

用法:
  $0 [run|list|create] [选项]

命令:
  run [table]     执行所有种子文件或指定表
  list            列出所有种子文件
  create <table>  创建新的种子文件

选项:
  -d, --dir DIR   种子文件目录 (默认: Scripts/db/seeds)
  -h, --help      显示帮助信息

环境变量:
  DB_HOST         数据库主机
  DB_PORT         数据库端口
  DB_NAME         数据库名
  DB_USER         数据库用户
  DB_PASSWORD     数据库密码

示例:
  $0 run
  $0 run users
  $0 list
  $0 create categories

EOF
}

# 创建种子文件
create_seed() {
    local table_name="$1"

    if [ -z "$table_name" ]; then
        log_error "请提供表名"
        exit 1
    fi

    mkdir -p "$SEED_DIR"

    local seed_file="$SEED_DIR/${table_name}.sql"

    if [ -f "$seed_file" ]; then
        log_error "种子文件已存在: $seed_file"
        exit 1
    fi

    cat > "$seed_file" << EOF
-- Seed data for ${table_name} table
-- Created: $(date)
-- Description: Initial seed data for ${table_name}

BEGIN;

-- 在这里添加种子数据
-- 示例:
-- INSERT INTO ${table_name} (name, description, created_at) VALUES
-- ('示例数据1', '描述1', NOW()),
-- ('示例数据2', '描述2', NOW())
-- ON CONFLICT DO NOTHING;

COMMIT;
EOF

    log_success "种子文件已创建: $seed_file"
}

# 主函数
main() {
    local command="$1"
    shift

    case "$command" in
        run)
            if ! check_db_connection; then
                exit 1
            fi

            local table_name="$1"

            if [ -n "$table_name" ]; then
                # 执行指定种子文件
                local seed_file="$SEED_DIR/${table_name}.sql"
                if [ -f "$seed_file" ]; then
                    run_seed "$seed_file"
                else
                    log_error "种子文件不存在: $seed_file"
                    exit 1
                fi
            else
                # 执行所有种子文件
                log_info "查找种子文件..."
                local seed_files
                seed_files=$(find "$SEED_DIR" -name "*.sql" | sort)

                if [ -z "$seed_files" ]; then
                    log_info "没有找到种子文件"
                    exit 0
                fi

                local executed_count=0
                while IFS= read -r file; do
                    if run_seed "$file"; then
                        ((executed_count++))
                    fi
                done <<< "$seed_files"

                log_success "种子数据执行完成: 执行了 $executed_count 个文件"
            fi
            ;;

        list)
            log_info "可用的种子文件:"
            if [ -d "$SEED_DIR" ]; then
                find "$SEED_DIR" -name "*.sql" -exec basename {} \; | sed 's/\.sql$//' | while read -r file; do
                    echo "  - $file"
                done
            else
                log_info "种子目录不存在: $SEED_DIR"
            fi
            ;;

        create)
            create_seed "$1"
            ;;

        "")
            show_help
            exit 1
            ;;

        *)
            log_error "未知命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 参数解析
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dir)
            SEED_DIR="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            break
            ;;
    esac
done

main "$@"

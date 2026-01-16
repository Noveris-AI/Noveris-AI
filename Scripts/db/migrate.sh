#!/bin/bash
# Noveris AI - 数据库迁移脚本
# 支持: Linux/macOS (bash), Windows (WSL/Git Bash)

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
MIGRATION_DIR=${MIGRATION_DIR:-Backend/migrations}

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
        else
            log_error "数据库连接失败"
            return 1
        fi
    else
        log_warning "psql 命令未找到，使用Docker检查连接"
        if command -v docker &> /dev/null; then
            if docker exec postgres pg_isready -h localhost -U "$DB_USER" -d "$DB_NAME" &> /dev/null; then
                log_success "数据库连接正常 (通过Docker)"
                return 0
            fi
        fi
        log_error "无法验证数据库连接"
        return 1
    fi
}

# 创建迁移表
create_migration_table() {
    log_info "创建迁移表..."

    local sql="
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version VARCHAR(255) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        checksum VARCHAR(255)
    );

    CREATE INDEX IF NOT EXISTS idx_schema_migrations_applied_at
    ON schema_migrations(applied_at);
    "

    if command -v psql &> /dev/null; then
        echo "$sql" | PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"
    else
        log_error "psql 命令未找到，无法创建迁移表"
        return 1
    fi

    log_success "迁移表创建完成"
}

# 获取已应用的迁移
get_applied_migrations() {
    local sql="SELECT version FROM schema_migrations ORDER BY version;"

    if command -v psql &> /dev/null; then
        PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "$sql" | tr -d ' '
    fi
}

# 应用迁移
apply_migration() {
    local migration_file="$1"
    local version
    version=$(basename "$migration_file" | cut -d'_' -f1)
    local name
    name=$(basename "$migration_file" | sed 's/^V[0-9]\+_//' | sed 's/\.sql$//')

    log_info "应用迁移: $version - $name"

    # 检查是否已应用
    if echo "$APPLIED_MIGRATIONS" | grep -q "^${version}$"; then
        log_warning "迁移 $version 已应用，跳过"
        return 0
    fi

    # 执行迁移
    if command -v psql &> /dev/null; then
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$migration_file"; then
            # 记录迁移
            local record_sql="
            INSERT INTO schema_migrations (version, name, checksum)
            VALUES ('$version', '$name', '$(sha256sum "$migration_file" | cut -d' ' -f1)');
            "
            echo "$record_sql" | PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"
            log_success "迁移 $version 应用成功"
        else
            log_error "迁移 $version 应用失败"
            return 1
        fi
    else
        log_error "psql 命令未找到，无法执行迁移"
        return 1
    fi
}

# 回滚迁移
rollback_migration() {
    local migration_file="$1"
    local version
    version=$(basename "$migration_file" | cut -d'_' -f1)
    local name
    name=$(basename "$migration_file" | sed 's/^V[0-9]\+_//' | sed 's/_rollback\.sql$//')

    log_info "回滚迁移: $version - $name"

    # 检查是否已应用
    if ! echo "$APPLIED_MIGRATIONS" | grep -q "^${version}$"; then
        log_warning "迁移 $version 未应用，跳过回滚"
        return 0
    fi

    # 查找回滚文件
    local rollback_file="${migration_file%.*}_rollback.sql"
    if [ ! -f "$rollback_file" ]; then
        log_error "回滚文件不存在: $rollback_file"
        return 1
    fi

    # 执行回滚
    if command -v psql &> /dev/null; then
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$rollback_file"; then
            # 删除迁移记录
            local delete_sql="DELETE FROM schema_migrations WHERE version = '$version';"
            echo "$delete_sql" | PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"
            log_success "迁移 $version 回滚成功"
        else
            log_error "迁移 $version 回滚失败"
            return 1
        fi
    else
        log_error "psql 命令未找到，无法执行回滚"
        return 1
    fi
}

# 显示帮助信息
show_help() {
    cat << EOF
Noveris AI - 数据库迁移工具

用法:
  $0 [up|down|status|create] [选项]

命令:
  up          应用所有待迁移的文件
  down [n]    回滚最近 n 个迁移 (默认 1)
  status      显示迁移状态
  create <name> 创建新的迁移文件

选项:
  -d, --dir DIR     迁移文件目录 (默认: Backend/migrations)
  -h, --help        显示帮助信息

环境变量:
  DB_HOST           数据库主机 (默认: localhost)
  DB_PORT           数据库端口 (默认: 5432)
  DB_NAME           数据库名 (默认: noveris_db)
  DB_USER           数据库用户 (默认: noveris_user)
  DB_PASSWORD       数据库密码 (默认: password)

示例:
  $0 up
  $0 down 2
  $0 status
  $0 create add_user_profiles_table

EOF
}

# 创建新的迁移文件
create_migration() {
    local name="$1"
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local version="V${timestamp}"

    # 创建迁移目录
    mkdir -p "$MIGRATION_DIR"

    # 创建迁移文件
    local migration_file="$MIGRATION_DIR/${version}__${name}.sql"
    local rollback_file="$MIGRATION_DIR/${version}__${name}_rollback.sql"

    # 迁移文件模板
    cat > "$migration_file" << EOF
-- Migration: $version - $name
-- Created: $(date)
-- Description: $name

BEGIN;

-- 在这里添加迁移SQL语句
-- 示例:
-- CREATE TABLE example (
--     id BIGSERIAL PRIMARY KEY,
--     name VARCHAR(255) NOT NULL,
--     created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
-- );

COMMIT;
EOF

    # 回滚文件模板
    cat > "$rollback_file" << EOF
-- Rollback: $version - $name
-- Created: $(date)
-- Description: Rollback $name

BEGIN;

-- 在这里添加回滚SQL语句
-- 示例:
-- DROP TABLE IF EXISTS example;

COMMIT;
EOF

    log_success "迁移文件已创建:"
    log_info "  迁移: $migration_file"
    log_info "  回滚: $rollback_file"
}

# 主函数
main() {
    local command="$1"
    shift

    case "$command" in
        up)
            if ! check_db_connection; then
                exit 1
            fi

            create_migration_table
            APPLIED_MIGRATIONS=$(get_applied_migrations)

            log_info "查找迁移文件..."
            local migration_files
            migration_files=$(find "$MIGRATION_DIR" -name "V*.sql" -not -name "*_rollback.sql" | sort)

            if [ -z "$migration_files" ]; then
                log_info "没有找到迁移文件"
                exit 0
            fi

            local applied_count=0
            local skipped_count=0

            while IFS= read -r file; do
                if apply_migration "$file"; then
                    ((applied_count++))
                else
                    ((skipped_count++))
                fi
            done <<< "$migration_files"

            log_success "迁移完成: 应用 $applied_count 个，跳过 $skipped_count 个"
            ;;

        down)
            local steps="${1:-1}"

            if ! check_db_connection; then
                exit 1
            fi

            APPLIED_MIGRATIONS=$(get_applied_migrations)

            log_info "查找要回滚的迁移..."
            # 获取最近的迁移文件
            local migration_files
            migration_files=$(find "$MIGRATION_DIR" -name "V*.sql" -not -name "*_rollback.sql" | sort -r | head -n "$steps")

            if [ -z "$migration_files" ]; then
                log_info "没有找到要回滚的迁移"
                exit 0
            fi

            local rolled_back=0

            while IFS= read -r file; do
                if rollback_migration "$file"; then
                    ((rolled_back++))
                fi
            done <<< "$migration_files"

            log_success "回滚完成: 回滚了 $rolled_back 个迁移"
            ;;

        status)
            if ! check_db_connection; then
                exit 1
            fi

            APPLIED_MIGRATIONS=$(get_applied_migrations)

            log_info "迁移状态:"

            local migration_files
            migration_files=$(find "$MIGRATION_DIR" -name "V*.sql" -not -name "*_rollback.sql" | sort)

            while IFS= read -r file; do
                local version
                version=$(basename "$file" | cut -d'_' -f1)
                local name
                name=$(basename "$file" | sed 's/^V[0-9]\+_//' | sed 's/\.sql$//')

                if echo "$APPLIED_MIGRATIONS" | grep -q "^${version}$"; then
                    echo -e "  ${GREEN}✓${NC} $version - $name"
                else
                    echo -e "  ${YELLOW}○${NC} $version - $name"
                fi
            done <<< "$migration_files"
            ;;

        create)
            local name="$1"
            if [ -z "$name" ]; then
                log_error "请提供迁移名称"
                echo "用法: $0 create <name>"
                exit 1
            fi

            create_migration "$name"
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
            MIGRATION_DIR="$2"
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

# 执行主函数
main "$@"

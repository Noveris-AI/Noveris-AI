# 数据库设计规范

## 目的
建立统一的数据库设计规范，确保数据模型的一致性、可维护性和性能，涵盖命名、约束、索引、迁移、审计等关键方面。

## 适用范围
- **强制**: Backend (Python+FastAPI) - 所有数据库操作
- **验证**: 数据库迁移时必须遵循，代码审查时检查

## 核心原则

### MUST - 强制规则
1. **命名规范**: 使用 snake_case，小写字母和下划线
2. **必备字段**: 所有表必须包含 `id`, `created_at`, `updated_at`
3. **主键策略**: 使用自增 BIGINT 或 UUID 作为主键
4. **外键约束**: 必须设置外键约束，级联删除谨慎使用
5. **索引设计**: 频繁查询字段必须建立适当索引
6. **迁移记录**: 所有变更必须通过迁移脚本执行

### SHOULD - 建议规则
1. 使用软删除代替物理删除
2. 添加数据库级别的检查约束
3. 定期分析和优化查询性能
4. 实施数据归档策略

## 表命名规范

### 基础命名规则
```sql
-- 正确示例
users                    -- 用户表
user_profiles           -- 用户档案表
posts                   -- 文章表
post_comments          -- 文章评论表
categories             -- 分类表

-- 错误示例
User                    -- 大写开头
user-profile           -- 使用连字符
tbl_users             -- 前缀冗余
```

### 多租户支持
```sql
-- 所有业务表包含 tenant_id
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,           -- 多租户标识
    email VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 唯一约束包含 tenant_id
ALTER TABLE users
ADD CONSTRAINT users_tenant_email_unique
UNIQUE (tenant_id, email);
```

## 字段设计规范

### 必备字段
```sql
CREATE TABLE example_table (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,

    -- 审计字段
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by BIGINT,                              -- 创建者ID
    updated_by BIGINT,                              -- 更新者ID

    -- 软删除字段
    deleted_at TIMESTAMP WITH TIME ZONE,
    deleted_by BIGINT,

    -- 业务字段
    name VARCHAR(255) NOT NULL,
    description TEXT
);

-- 索引
CREATE INDEX idx_example_table_tenant_id ON example_table(tenant_id);
CREATE INDEX idx_example_table_created_at ON example_table(created_at);
CREATE INDEX idx_example_table_deleted_at ON example_table(deleted_at) WHERE deleted_at IS NULL;
```

### 数据类型选择
```sql
-- 推荐数据类型
id              BIGSERIAL           -- 主键
tenant_id       BIGINT              -- 多租户ID
email           VARCHAR(255)         -- 邮箱
phone           VARCHAR(20)          -- 手机号
name            VARCHAR(100)         -- 姓名
title           VARCHAR(200)         -- 标题
description     TEXT                 -- 长文本
amount          DECIMAL(15,2)        -- 金额
quantity        INTEGER              -- 数量
is_active       BOOLEAN DEFAULT TRUE -- 状态
metadata        JSONB                -- 扩展数据
tags            TEXT[]               -- 标签数组

-- 日期时间
created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
deleted_at      TIMESTAMP WITH TIME ZONE
scheduled_at    TIMESTAMP WITH TIME ZONE
```

## 索引设计规范

### 索引命名规范
```sql
-- 索引命名格式: idx_[table_name]_[column1]_[column2]
CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tenant_email ON users(tenant_id, email);
CREATE INDEX idx_posts_tenant_created ON posts(tenant_id, created_at DESC);
```

### 复合索引策略
```sql
-- 常用查询模式的索引
-- 1. 多租户 + 状态 + 时间
CREATE INDEX idx_orders_tenant_status_created
ON orders(tenant_id, status, created_at DESC);

-- 2. 多租户 + 用户 + 时间
CREATE INDEX idx_posts_tenant_user_created
ON posts(tenant_id, user_id, created_at DESC);

-- 3. 全文搜索索引
CREATE INDEX idx_posts_tenant_content_gin
ON posts(tenant_id, content gin_trgm_ops);
```

### 索引使用检查
```sql
-- 查看索引使用情况
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,      -- 索引扫描次数
    idx_tup_read,  -- 通过索引读取的元组数
    idx_tup_fetch  -- 通过索引获取的元组数
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- 查看未使用索引
SELECT
    indexrelname,
    tablename,
    idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY indexrelname;
```

## 约束设计规范

### 唯一约束
```sql
-- 单字段唯一约束
ALTER TABLE users
ADD CONSTRAINT users_email_unique UNIQUE (email);

-- 多租户唯一约束
ALTER TABLE users
ADD CONSTRAINT users_tenant_email_unique UNIQUE (tenant_id, email);

-- 复合唯一约束
ALTER TABLE user_permissions
ADD CONSTRAINT user_permissions_unique UNIQUE (user_id, permission_id);
```

### 检查约束
```sql
-- 字段值范围检查
ALTER TABLE products
ADD CONSTRAINT products_price_positive CHECK (price > 0);

-- 枚举值检查
ALTER TABLE orders
ADD CONSTRAINT orders_status_valid
CHECK (status IN ('pending', 'processing', 'shipped', 'delivered', 'cancelled'));

-- 字段间逻辑检查
ALTER TABLE discounts
ADD CONSTRAINT discounts_percentage_valid
CHECK (percentage >= 0 AND percentage <= 100);
```

### 外键约束
```sql
-- 标准外键
ALTER TABLE posts
ADD CONSTRAINT posts_user_id_fk
FOREIGN KEY (user_id) REFERENCES users(id);

-- 多租户外键（确保引用同一租户）
ALTER TABLE posts
ADD CONSTRAINT posts_tenant_user_fk
FOREIGN KEY (tenant_id, user_id) REFERENCES users(tenant_id, id);

-- 级联删除（谨慎使用）
ALTER TABLE post_comments
ADD CONSTRAINT post_comments_post_fk
FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE;
```

## 迁移策略

### 迁移文件命名
```
V001__create_users_table.sql
V002__add_user_profiles.sql
V003__create_posts_table.sql
V004__add_soft_delete.sql
V005__create_indexes.sql
```

### 迁移脚本结构
```sql
-- V001__create_users_table.sql
BEGIN;

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 索引
CREATE INDEX CONCURRENTLY idx_users_tenant_id ON users(tenant_id);
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY idx_users_active ON users(is_active) WHERE is_active = true;

-- 约束
ALTER TABLE users
ADD CONSTRAINT users_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$');

COMMENT ON TABLE users IS '用户表';
COMMENT ON COLUMN users.id IS '主键ID';
COMMENT ON COLUMN users.tenant_id IS '租户ID';

COMMIT;
```

### 回滚策略
```sql
-- V001__create_users_table_rollback.sql
BEGIN;

DROP TABLE IF EXISTS users;

COMMIT;
```

## 数据字典规范

### 表结构文档
```markdown
### users - 用户表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGSERIAL | PK | 主键ID |
| tenant_id | BIGINT | NOT NULL | 租户ID |
| email | VARCHAR(255) | UNIQUE, NOT NULL | 用户邮箱 |
| password_hash | VARCHAR(255) | NOT NULL | 密码哈希 |
| is_active | BOOLEAN | DEFAULT TRUE | 是否激活 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新时间 |

**索引：**
- idx_users_tenant_id (tenant_id)
- idx_users_email (email)
- idx_users_active (is_active) WHERE is_active = true

**约束：**
- users_email_unique (email)
- users_email_format (邮箱格式检查)
```

## 备份恢复规范

### 备份策略
```bash
# 全量备份脚本
#!/bin/bash
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="noveris_db"

pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME \
    --format=custom \
    --compress=9 \
    --file="$BACKUP_DIR/${DB_NAME}_full_$TIMESTAMP.backup"

# 保留最近7天的备份
find $BACKUP_DIR -name "${DB_NAME}_*.backup" -mtime +7 -delete
```

### 恢复测试
```bash
# 创建测试数据库
createdb -h $DB_HOST -U $DB_USER test_restore

# 从备份恢复
pg_restore -h $DB_HOST -U $DB_USER \
    -d test_restore \
    --format=custom \
    "$BACKUP_DIR/backup_file.backup"

# 验证数据完整性
psql -h $DB_HOST -U $DB_USER -d test_restore -c "SELECT COUNT(*) FROM users;"
```

### RTO/RPO目标
- **RTO (Recovery Time Objective)**: 4小时内恢复服务
- **RPO (Recovery Point Objective)**: 最多丢失15分钟数据
- **备份频率**: 全量备份每日一次，增量备份每小时一次
- **保留策略**: 全量备份保留30天，增量备份保留7天

## 性能优化策略

### 查询优化
```sql
-- 避免全表扫描
EXPLAIN ANALYZE SELECT * FROM users WHERE tenant_id = 1 AND created_at > '2024-01-01';

-- 使用分页查询
SELECT * FROM posts
WHERE tenant_id = 1
ORDER BY created_at DESC
LIMIT 20 OFFSET 0;

-- 优化JOIN查询
SELECT u.name, p.title
FROM users u
INNER JOIN posts p ON u.id = p.user_id AND u.tenant_id = p.tenant_id
WHERE u.tenant_id = 1;
```

### 分区策略
```sql
-- 按时间分区
CREATE TABLE posts_y2024m01 PARTITION OF posts
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- 按租户分区（如果租户数量巨大）
CREATE TABLE posts_tenant_1 PARTITION OF posts
    FOR VALUES IN (1);
```

## 检查清单

### 表设计检查
- [ ] 表名使用 snake_case 命名
- [ ] 包含所有必备字段 (id, created_at, updated_at)
- [ ] 多租户表包含 tenant_id 字段
- [ ] 设置了适当的外键约束
- [ ] 添加了必要的唯一约束
- [ ] 字段类型选择合理

### 索引设计检查
- [ ] 频繁查询字段有索引
- [ ] 复合索引顺序合理
- [ ] 索引命名符合规范
- [ ] 定期清理未使用索引

### 迁移检查
- [ ] 迁移文件命名正确
- [ ] 包含回滚脚本
- [ ] 测试过迁移过程
- [ ] 更新了数据字典

### 性能检查
- [ ] 执行过 EXPLAIN ANALYZE
- [ ] 避免了 N+1 查询问题
- [ ] 合理使用分页查询
- [ ] 监控慢查询日志

## 示例代码

### SQLAlchemy模型定义
```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系定义
    posts = relationship("Post", back_populates="author")

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系定义
    author = relationship("User", back_populates="posts")
```

## 相关文档
- [配置规范](10-Config-Standard.md) - 数据库配置管理
- [API规范](30-API-Standard.md) - 数据查询接口设计
- [安全规范](60-Security-Standard.md) - 数据安全保护
- [性能规范](70-Performance-Standard.md) - 数据库性能优化

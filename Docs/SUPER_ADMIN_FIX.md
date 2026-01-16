# 超级管理员账号创建问题修复

## 问题描述

用户报告数据库中没有找到超级管理员用户，环境变量已正确配置：
- `ADMIN_AUTO_CREATE=true`
- `ADMIN_EMAIL=admin@noveris.ai`
- `ADMIN_PASSWORD=admin@noveris.ai`
- `ADMIN_NAME=Noveris`

## 根本原因

经过排查，发现了以下问题：

### 1. **User模型缺少必需字段**

`Backend/app/models/user.py` 中缺少两个关键字段：
- `tenant_id`: 多租户支持字段
- `is_superuser`: 超级管理员标识字段

但 `Backend/app/core/init_admin.py` 在创建超级管理员时尝试使用这些字段，导致创建失败。

### 2. **字段名不匹配**

- User模型使用 `password_hash`
- init_admin.py 使用 `hashed_password`

### 3. **数据库schema缺少字段**

数据库迁移文件 `Backend/alembic_migrations/versions/20250114_0000_initial_schema.py` 创建的 `users` 表不包含 `tenant_id` 和 `is_superuser` 字段。

## 修复内容

### 1. 更新User模型

**文件**: `Backend/app/models/user.py`

添加了以下字段：

```python
# Multi-tenancy
tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
    UUID(as_uuid=True),
    nullable=True,
    index=True,
    comment="Tenant ID for multi-tenancy support"
)

# Status (在is_verified后添加)
is_superuser: Mapped[bool] = mapped_column(
    Boolean,
    default=False,
    nullable=False,
    index=True,
    comment="Super admin with full system access"
)
```

### 2. 修复init_admin.py字段名

**文件**: `Backend/app/core/init_admin.py`

修改前（第69行）:
```python
hashed_password=hashed_password,
```

修改后:
```python
password_hash=hashed_password,
```

### 3. 创建数据库迁移

**文件**: `Backend/alembic_migrations/versions/20260117_0001_add_tenant_and_superuser.py`

新增迁移文件，添加 `tenant_id` 和 `is_superuser` 字段到 `users` 表。

## 执行步骤

### 方法一：自动迁移（推荐）

Backend配置了自动迁移（`auto_migrate=True`），只需重启backend服务：

```bash
# 停止当前backend服务（如果正在运行）
# Ctrl+C 或者

# 重启backend
cd Backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动时会自动：
1. 运行数据库迁移 `alembic upgrade head`
2. 创建超级管理员账号

### 方法二：手动迁移

如果需要手动控制，可以先运行迁移：

```bash
cd Backend

# 运行数据库迁移
alembic upgrade head

# 然后启动backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 验证步骤

### 1. 检查数据库迁移

```bash
cd Backend
alembic current
```

应该显示:
```
002 (head)
```

### 2. 检查数据库中的超级管理员

连接到PostgreSQL数据库：

```sql
-- 连接到数据库
psql -U noveris -d noveris

-- 查询超级管理员
SELECT id, email, name, is_superuser, is_active, tenant_id
FROM users
WHERE email = 'admin@noveris.ai';
```

应该看到：
```
| id      | email              | name    | is_superuser | is_active | tenant_id                            |
|---------|--------------------|---------|--------------|-----------|--------------------------------------|
| <uuid>  | admin@noveris.ai   | Noveris | true         | true      | 00000000-0000-0000-0000-000000000001 |
```

### 3. 测试登录

使用以下凭据登录前端：

- **邮箱**: admin@noveris.ai
- **密码**: admin@noveris.ai

应该能够成功登录并访问所有功能。

### 4. 检查Backend日志

Backend启动时应该看到类似的日志：

```
INFO: Database tables verified via init_db
INFO: ✅ Super admin user created successfully: admin@noveris.ai
WARNING: ⚠️  SECURITY: Please change the default admin password immediately!
```

或者如果用户已存在：

```
INFO: Super admin user already exists: admin@noveris.ai
```

## 如果问题仍然存在

### 1. 检查数据库连接

确认 `.env` 中的数据库配置正确：

```bash
DATABASE_URL=postgresql://noveris:noveris123@localhost:5432/noveris
```

测试连接：

```bash
psql -U noveris -d noveris
```

### 2. 手动检查表结构

```sql
-- 查看users表结构
\d users

-- 应该包含以下列：
-- - tenant_id (uuid, nullable)
-- - is_superuser (boolean, not null, default false)
```

### 3. 清空并重建

**警告**: 这会删除所有数据！

```bash
cd Backend

# 降级到初始状态
alembic downgrade base

# 重新运行所有迁移
alembic upgrade head

# 重启backend（会自动创建超级管理员）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 查看详细错误日志

如果Backend启动失败，检查控制台输出中的错误信息：

```bash
# 使用更详细的日志级别启动
LOG_LEVEL=DEBUG python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 安全建议

超级管理员创建成功后，**立即修改默认密码**：

1. 登录系统
2. 进入 **设置 > 安全**
3. 修改密码为更强的密码（包含大小写字母、数字和特殊字符）
4. 修改后，更新 `.env` 文件中的 `ADMIN_AUTO_CREATE=false` 以禁用自动创建

## 相关文件

- ✅ `Backend/app/models/user.py` - 添加tenant_id和is_superuser字段
- ✅ `Backend/app/core/init_admin.py` - 修复字段名（hashed_password → password_hash）
- ✅ `Backend/alembic_migrations/versions/20260117_0001_add_tenant_and_superuser.py` - 新增数据库迁移

# Data Model: 后端登录鉴权系统重构

**Feature**: 003-auth-refactor
**Date**: 2026-01-17
**Status**: Complete

## 概述

本文档定义认证系统中的核心数据实体。重构主要聚焦在Session会话管理，不涉及User模型的schema变更。

## 核心实体

### 1. User (已存在，无变更)

**用途**: 存储用户账号信息，用于认证和授权

**存储**: PostgreSQL `users` 表

**属性**:
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK, NOT NULL | 用户唯一标识 |
| email | String(255) | UNIQUE, NOT NULL | 登录邮箱（小写） |
| password_hash | String(255) | NOT NULL | bcrypt哈希（cost=12） |
| name | String(100) | NOT NULL | 显示名称 |
| is_active | Boolean | NOT NULL, DEFAULT true | 账号是否激活 |
| is_verified | Boolean | NOT NULL, DEFAULT false | 邮箱是否验证 |
| is_superuser | Boolean | NOT NULL, DEFAULT false | 是否超级管理员 |
| tenant_id | UUID | NULLABLE, INDEX | 租户ID（多租户支持） |
| last_login_at | Timestamp | NULLABLE | 最后登录时间 |
| last_login_ip | String(45) | NULLABLE | 最后登录IP |
| created_at | Timestamp | NOT NULL | 创建时间 |
| updated_at | Timestamp | NOT NULL | 更新时间 |
| deleted_at | Timestamp | NULLABLE | 软删除时间戳 |

**索引**:
- `idx_users_email` (UNIQUE): 邮箱查询
- `idx_users_tenant_id`: 多租户隔离
- `idx_users_is_superuser`: 管理员查询

**关系**:
- 一个User可以有多个活跃Session（1:N）

---

### 2. Session (Redis存储，无数据库表)

**用途**: 存储用户会话状态，用于认证和跨请求状态保持

**存储**: Redis
- Key pattern: `session:{session_id}`
- Value: JSON序列化的SessionData
- TTL: 1800秒（普通）或 2592000秒（记住我）

**数据结构** (Python class):
```python
class SessionData:
    user_id: str          # 用户UUID（字符串格式）
    email: str            # 用户邮箱（冗余，避免每次查DB）
    name: str             # 用户名称（冗余，用于显示）
    ip_address: str | None  # 登录IP（可选，用于审计）
    user_agent: str | None  # User-Agent（可选，设备识别）
    remember_me: bool     # 是否"记住我"（影响TTL）
    created_at: datetime  # 会话创建时间（UTC）
    expires_at: datetime  # 会话过期时间（UTC）
```

**JSON示例**:
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "admin@noveris.ai",
  "name": "Noveris",
  "ip_address": "127.0.0.1",
  "user_agent": "Mozilla/5.0 ...",
  "remember_me": false,
  "created_at": "2026-01-17T10:30:00.000Z",
  "expires_at": "2026-01-17T11:00:00.000Z"
}
```

**字段说明**:
- `user_id`: 关联User表的主键，用于反查用户信息
- `email`, `name`: 冗余字段，避免每次请求查询数据库（性能优化）
- `ip_address`, `user_agent`: 用于审计日志和设备管理（P3功能）
- `remember_me`: 影响TTL和续期策略
- `created_at`: 用于显示"登录于X天前"
- `expires_at`: 用于判断会话是否过期（虽然Redis TTL也能判断，但这个字段用于业务逻辑）

**索引** (Redis Sets):
- Key: `session:user:{user_id}`
- Value: Set of session IDs
- 用途: 查找用户的所有活跃会话（P3功能：跨设备管理）

---

### 3. AuthenticationAttempt (可选，P2功能)

**用途**: 记录登录尝试，用于速率限制和审计

**存储**: Redis (短期) + PostgreSQL (长期归档)

**Redis结构** (用于速率限制):
- Key pattern: `auth:attempts:{ip}:{email}`
- Value: 整数（失败次数）
- TTL: 600秒（10分钟）

**PostgreSQL表结构** (用于审计):
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BigInt | PK, AUTO | 记录ID |
| email | String(255) | INDEX | 尝试登录的邮箱 |
| ip_address | String(45) | INDEX | 请求IP |
| user_agent | String(500) | NULLABLE | User-Agent |
| success | Boolean | NOT NULL | 是否成功 |
| failure_reason | String(100) | NULLABLE | 失败原因（invalid_password, account_disabled等） |
| created_at | Timestamp | NOT NULL, INDEX | 尝试时间 |

**索引**:
- `idx_attempts_email_created`: 查询用户的登录历史
- `idx_attempts_ip_created`: 查询IP的登录行为
- `idx_attempts_created`: 时间范围查询

---

## 数据流

### 登录流程

```
1. POST /api/v1/auth/login
   ↓
2. 验证用户凭据 (email + password)
   - 查询User表（email索引）
   - 验证password_hash (bcrypt)
   ↓
3. 创建Session
   - 生成session_id (随机32字节, base64编码)
   - 构建SessionData对象
   - 存储到Redis: SET session:{id} {json} EX {ttl}
   - 添加到用户会话集合: SADD session:user:{user_id} {session_id}
   ↓
4. 设置Cookie
   - Set-Cookie: session_id={session_id}; HttpOnly; SameSite=lax; Max-Age={ttl}
   ↓
5. 更新User.last_login_at, last_login_ip
   ↓
6. 返回登录成功响应
```

### 认证验证流程

```
1. 受保护的API请求 (GET /api/v1/auth/me)
   ↓
2. 提取Cookie
   - 从request.cookies获取session_id
   - 如果不存在 → 401 Unauthorized
   ↓
3. 从Redis获取Session
   - GET session:{session_id}
   - 如果不存在 → 401 (会话已过期或无效)
   ↓
4. 反序列化SessionData
   - 解析JSON
   - 检查expires_at是否过期
   ↓
5. (可选) 验证User是否仍然is_active
   - 查询User表（PK查询，缓存友好）
   - 如果不活跃 → 销毁会话 → 401
   ↓
6. (可选) 续期Session
   - 如果 (expires_at - now) < ttl/2:
     - 更新expires_at
     - SETEX session:{session_id} {json} {new_ttl}
   ↓
7. 返回SessionData（包含user_id, email, name）
```

### 登出流程

```
1. POST /api/v1/auth/logout
   ↓
2. 获取当前session_id（从cookie）
   ↓
3. 从Redis删除Session
   - DEL session:{session_id}
   - SREM session:user:{user_id} {session_id}
   ↓
4. 清除Cookie
   - Set-Cookie: session_id=; Max-Age=0; Path=/
   ↓
5. 返回登出成功响应
```

## 状态转换

### Session生命周期

```
┌─────────┐
│ 未创建  │
└────┬────┘
     │ 用户登录成功
     ↓
┌─────────┐
│ 活跃    │ ←──┐
└────┬────┘    │ 条件续期 (活动时)
     │         │
     │         └─────────┐
     │                   │
     │ TTL到期 或        │
     │ 用户登出 或       │
     │ 手动销毁          │
     ↓                   │
┌─────────┐              │
│ 已过期  │──────────────┘
└─────────┘   清理后重新登录
```

**触发条件**:
- 活跃 → 已过期:
  - Redis TTL到期（自动）
  - 用户点击登出（手动）
  - 用户被禁用（管理员操作）
  - 达到最大会话数限制（旧会话被挤掉）

- 活跃 → 活跃（续期）:
  - 条件: `expires_at - now < ttl / 2`
  - 频率: 每次请求最多检查一次
  - 操作: 更新Redis TTL和expires_at

## 验证规则

### Session创建

- `session_id` 必须唯一（通过随机性保证，碰撞概率 < 2^-128）
- `user_id` 必须对应存在的User
- `email`, `name` 必须非空
- `created_at` 必须 ≤ 当前时间
- `expires_at` 必须 > `created_at`
- TTL必须在合理范围（30秒 ~ 30天）

### Session验证

- `session_id` 必须存在于Redis
- `expires_at` 必须 > 当前时间（业务层检查）
- 对应的User必须 `is_active=true`（可选检查）

### Session续期

- 仅当 `expires_at - now < ttl / 2` 时续期（性能优化）
- 续期后 `expires_at = now + ttl`
- 更新Redis TTL

## 性能考虑

### Redis内存使用估算

**单个Session大小**:
```
Session ID (key): ~50 bytes
SessionData (JSON): ~450 bytes
Redis overhead: ~50 bytes
Total: ~550 bytes/session
```

**10k活跃用户**:
```
10,000 sessions × 550 bytes = 5.5 MB
User session sets: ~1 MB
Total: ~6.5 MB
```

**100k活跃用户**: ~65 MB

### 查询性能

| 操作 | Redis命令 | 时间复杂度 | 预期延迟 |
|------|-----------|------------|----------|
| 创建Session | SET + SADD | O(1) | <1ms |
| 获取Session | GET | O(1) | <1ms |
| 续期Session | SETEX | O(1) | <1ms |
| 删除Session | DEL + SREM | O(1) | <1ms |
| 查询用户会话 | SMEMBERS | O(N) N=会话数 | <5ms (N≤10) |

### 优化策略

1. **连接池复用**: 减少TCP连接开销（10-30倍性能提升）
2. **条件续期**: 减少Redis写操作（50%减少）
3. **冗余字段**: 避免每次请求查询User表（数据库压力 -80%）
4. **Pipeline**: 批量操作时使用Redis pipeline（待P3实现）

## 数据一致性

### 弱一致性场景（可接受）

- User被禁用后，已有Session可能仍然有效（最多TTL时间）
- 缓解措施: 在关键操作前再次验证User.is_active

### 强一致性要求

- Session创建必须在Redis成功存储后才返回给用户（避免幻影session）
- Session删除必须确认Redis删除成功（避免残留token）

### 故障恢复

- Redis故障: 所有会话丢失，用户需重新登录（接受）
- 数据库故障: 认证失败，返回503 Service Unavailable

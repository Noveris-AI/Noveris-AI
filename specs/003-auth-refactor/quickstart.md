# Quick Start: 后端登录鉴权系统重构

**Feature**: 003-auth-refactor
**Date**: 2026-01-17
**Audience**: 开发者（实施本重构）

## 概述

本重构修复当前登录鉴权系统中session cookie未正确传递的问题，确保用户登录后能够可靠访问受保护资源。

**核心修复**:
1. Cookie domain配置（`domain=None`）
2. OPTIONS预检请求跳过认证
3. Redis连接池优化（单例模式）
4. 添加详细调试日志

**预期结果**:
- ✅ 登录后访问/auth/me返回200（不再401）
- ✅ 刷新页面保持登录状态
- ✅ 新标签页共享登录状态
- ✅ 登录响应时间 <100ms
- ✅ 清晰的调试日志用于问题排查

## 环境准备

### 1. 确认依赖

所有依赖已在pyproject.toml中定义，无需添加新包：

```bash
cd Backend
uv sync  # 或 pip install -e .
```

**关键依赖**:
- FastAPI 0.109+
- Redis 5.0+
- Pydantic 2.5+
- Structlog (日志)
- Passlib (bcrypt)

### 2. 配置Redis

确认Redis服务运行中：

```bash
redis-cli ping
# 期望输出: PONG
```

检查Redis密码配置（Backend/.env）：

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=noveris_redis_pass_2025
REDIS_DB=0
REDIS_MAX_CONNECTIONS=50
```

### 3. 检查CORS配置

确认CORS允许前端域名（Backend/.env）：

```bash
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CORS_CREDENTIALS=true
```

**重要**: `CORS_CREDENTIALS=true` 是cookie传递的必要条件。

## 实施步骤

### Phase 1: 修复Cookie配置

**文件**: `Backend/app/api/v1/auth.py`

**位置**: `/auth/login` 端点中的 `response.set_cookie()` 调用

**修改前**:
```python
response.set_cookie(
    key=settings.session.cookie_name,
    value=session_id,
    httponly=True,
    secure=settings.session.cookie_secure,
    samesite=settings.session.cookie_samesite,
    max_age=...,
    path="/",
    domain=settings.session.cookie_domain or None,  # ❌ 可能为空字符串
)
```

**修改后**:
```python
response.set_cookie(
    key=settings.session.cookie_name,
    value=session_id,
    httponly=True,
    secure=settings.session.cookie_secure,
    samesite=settings.session.cookie_samesite,
    max_age=settings.session.remember_ttl if credentials.remember_me else settings.session.ttl,
    path="/",
    domain=None,  # ✅ 明确设置为None（最安全）
)
```

**验证**:
```bash
# 启动backend
cd Backend
python main.py

# 在另一个终端测试登录
curl -v -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@noveris.ai","password":"admin@noveris.ai"}'

# 检查响应头中的Set-Cookie，应该类似:
# Set-Cookie: session_id=abc123...; Path=/; HttpOnly; SameSite=lax; Max-Age=1800
```

### Phase 2: 跳过OPTIONS预检请求

**文件**: `Backend/app/core/dependencies.py`

**位置**: `get_current_user_optional()` 函数开头

**修改前**:
```python
async def get_current_user_optional(
    request: Request,
    response: Response,
    session_manager: SessionManagerDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Optional[SessionData]:
    """Get current user from session cookie (optional)."""
    session_id = request.cookies.get(settings.session.cookie_name)
    # ... 直接开始认证检查
```

**修改后**:
```python
async def get_current_user_optional(
    request: Request,
    response: Response,
    session_manager: SessionManagerDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Optional[SessionData]:
    """Get current user from session cookie (optional)."""

    # ✅ 第一步：跳过OPTIONS预检请求
    if request.method == "OPTIONS":
        return None

    session_id = request.cookies.get(settings.session.cookie_name)
    # ... 后续认证检查
```

**验证**:
```bash
# 测试OPTIONS请求（CORS预检）
curl -v -X OPTIONS http://localhost:8000/api/v1/auth/me \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET"

# 应该返回200 OK（不再401）
```

### Phase 3: 优化Redis连接池

**文件**: `Backend/app/core/dependencies.py`

**位置**: Redis依赖注入部分

**修改前** (每次请求创建新连接):
```python
async def get_redis() -> Redis:
    redis_client = Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password,
        ...
    )
    try:
        yield redis_client
    finally:
        await redis_client.close()  # ❌ 每次关闭连接
```

**修改后** (单例连接池):
```python
# 全局连接池
_redis_pool: Redis | None = None

async def get_redis_pool() -> Redis:
    """Get or create global Redis connection pool."""
    global _redis_pool

    if _redis_pool is None:
        _redis_pool = Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password if settings.redis.password else None,
            db=settings.redis.db,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.redis.pool_size,
        )
        try:
            await _redis_pool.ping()
        except Exception as e:
            _redis_pool = None
            raise RuntimeError(f"Failed to connect to Redis: {e}")

    return _redis_pool

async def get_redis() -> Redis:
    """Get Redis client - returns shared pool."""
    return await get_redis_pool()
```

**验证**:
```bash
# 性能测试（使用Apache Bench或类似工具）
ab -n 1000 -c 10 http://localhost:8000/api/v1/health

# 预期：响应时间显著降低（10-30倍）
```

### Phase 4: 添加调试日志

**文件1**: `Backend/app/api/v1/auth.py` (登录端点)

在session创建后添加：
```python
# DEBUG: Log session creation
import structlog
logger = structlog.get_logger(__name__)
logger.info(
    "Session created for login",
    session_id=session_id,
    user_id=str(user.id),
    email=user.email,
    cookie_name=settings.session.cookie_name,
    ttl=settings.session.remember_ttl if credentials.remember_me else settings.session.ttl,
)
```

**文件2**: `Backend/app/core/session.py` (Session管理)

在`create()`方法中添加存储验证：
```python
await self.redis.setex(session_key, ttl, session_data_json)

# ✅ 验证存储成功
verify_data = await self.redis.get(session_key)
logger.info(
    "Session storage verified",
    session_id=session_id,
    stored_successfully=verify_data is not None,
    ttl_remaining=await self.redis.ttl(session_key),
)
```

在`get()`方法中添加检索日志：
```python
logger.info(
    "Getting session from Redis",
    session_id=session_id[:20] + "...",
    session_key=session_key,
    data_found=data is not None,
)
```

**文件3**: `Backend/app/core/dependencies.py` (认证检查)

在`get_current_user_optional()`中添加：
```python
logger.info(
    "Checking auth session",
    method=request.method,
    session_id=session_id[:20] + "..." if session_id else None,
    cookie_name=settings.session.cookie_name,
    all_cookies=list(request.cookies.keys()),
    path=request.url.path,
)
```

**验证**:
```bash
# 启动backend（已添加日志）
cd Backend
python main.py

# 在前端登录，观察backend控制台输出
# 应该看到详细的日志：
# - "Session created for login"
# - "Session storage verified"
# - "Checking auth session"
# - "Getting session from Redis"
# - "Session retrieved successfully"
```

## 测试验证

### 手动测试清单

**测试1: 登录成功**
```bash
# 1. 打开浏览器开发者工具 (F12)
# 2. 访问登录页面: http://localhost:3000/login
# 3. 输入 admin@noveris.ai / admin@noveris.ai
# 4. 点击登录
# 5. 检查Network标签:
#    - POST /auth/login: 200 OK
#    - Response Headers有Set-Cookie: session_id=...
# 6. 检查Application标签 → Cookies:
#    - 应该看到session_id cookie
#    - Domain: localhost
#    - Path: /
#    - HttpOnly: ✓
#    - SameSite: Lax
```

**测试2: 访问受保护资源**
```bash
# 接上测试1，登录成功后：
# 7. 浏览器会自动跳转到首页
# 8. 检查Network标签:
#    - GET /auth/me: 200 OK （不再401）
#    - Request Headers有Cookie: session_id=...
# 9. 首页显示用户名称（例如：Noveris）
```

**测试3: 刷新页面保持登录**
```bash
# 10. 按F5刷新页面
# 11. 检查Network标签:
#     - GET /auth/me: 200 OK
#     - 仍然携带session_id cookie
# 12. 页面正常显示，不会跳转到登录页
```

**测试4: 新标签页共享会话**
```bash
# 13. 在同一浏览器打开新标签页
# 14. 访问 http://localhost:3000
# 15. 应该自动显示已登录状态（不需要重新登录）
```

**测试5: 登出清除会话**
```bash
# 16. 点击登出按钮
# 17. 检查Network标签:
#     - POST /auth/logout: 200 OK
#     - Response Headers有Set-Cookie: session_id=; Max-Age=0
# 18. 检查Application标签 → Cookies:
#     - session_id cookie已被删除
# 19. 尝试访问/dashboard → 被重定向到登录页
```

### 自动化测试

**单元测试**:
```bash
cd Backend
pytest tests/unit/test_session.py -v
pytest tests/unit/test_dependencies.py -v
pytest tests/unit/test_cookie_handling.py -v
```

**集成测试**:
```bash
pytest tests/integration/test_auth_flow.py -v
pytest tests/integration/test_session_lifecycle.py -v
```

**覆盖率检查**:
```bash
pytest --cov=app --cov-report=term-missing --cov-report=html
# 目标: 80%+ 覆盖率
```

## 常见问题排查

### 问题1: 登录后仍然401

**症状**: POST /auth/login返回200，但GET /auth/me返回401

**排查步骤**:
1. 检查浏览器开发者工具 → Application → Cookies
   - session_id cookie是否存在？
   - Domain是否正确（localhost）？
   - Path是否为 `/`？

2. 检查Network标签 → /auth/me请求
   - Request Headers是否包含 `Cookie: session_id=...`？
   - 如果没有：浏览器阻止了cookie（检查SameSite设置）

3. 检查Backend日志
   - 是否有 "No session cookie found"？
   - 是否有 "Session not found in Redis"？

**解决方案**:
- 如果cookie未设置：检查Phase 1的修改（domain=None）
- 如果cookie未发送：检查CORS配置（CORS_CREDENTIALS=true）
- 如果Redis找不到：检查Phase 3的修改（连接池）

### 问题2: OPTIONS请求返回401

**症状**: 浏览器Network标签显示OPTIONS请求失败（401），真正的GET/POST被阻止

**排查步骤**:
1. 检查Network标签
   - 是否有OPTIONS /auth/me请求？
   - 状态码是401还是200？

2. 检查Backend日志
   - OPTIONS请求是否触发了 "Checking auth session"？

**解决方案**:
- 确认Phase 2的修改（跳过OPTIONS）已生效
- 重启Backend确保代码更新

### 问题3: 登录很慢（>1秒）

**症状**: POST /auth/login响应时间 >1秒

**排查步骤**:
1. 检查Backend日志的时间戳
   - Session创建和存储之间的时间差？

2. 检查Redis连接
   ```bash
   redis-cli ping
   redis-cli --latency
   ```

**解决方案**:
- 确认Phase 3的修改（连接池单例）已生效
- 检查Redis性能（latency应该 <1ms）

### 问题4: 日志太多或太少

**症状**: Backend控制台输出过多SQLAlchemy日志，或者没有认证相关日志

**排查步骤**:
1. 检查Backend/app/core/config.py
   ```python
   app_debug: bool = True
   ```

2. 检查Backend/app/core/database.py
   ```python
   engine = create_async_engine(
       ...,
       echo=False,  # ✅ 应该是False
   )
   ```

**解决方案**:
- 确认Phase 4的调试日志已添加
- 如果SQLAlchemy日志太多：设置 `echo=False`

## 性能基准

重构后应达到的性能指标：

| 指标 | 目标 | 测量方法 |
|------|------|----------|
| 登录响应时间 (p95) | <100ms | Apache Bench: `ab -n 100 -c 10` |
| 会话验证时间 (p95) | <10ms | 日志时间戳差值 |
| 并发登录请求 | 1000 req/s | Apache Bench: `ab -n 10000 -c 100` |
| Redis连接数 | <50 | `redis-cli client list | wc -l` |
| 内存使用 (10k会话) | <50MB | `redis-cli info memory` |

## 下一步

重构完成后：

1. **运行完整测试套件**
   ```bash
   pytest tests/ -v --cov=app
   ```

2. **手动验证所有用户故事**（参考spec.md）
   - P1: 登录成功并访问受保护资源
   - P1: 登录失败并收到清晰提示
   - P1: 安全退出登录

3. **性能测试**
   ```bash
   ab -n 1000 -c 50 http://localhost:8000/api/v1/auth/login \
     -p login_payload.json -T application/json
   ```

4. **部署到测试环境**
   - 确认生产环境配置正确（COOKIE_SECURE=true, HTTPS）

5. **监控日志和指标**
   - 登录成功率
   - 401错误率
   - 平均响应时间

## 回滚计划

如果重构导致问题：

1. **立即回滚代码**
   ```bash
   git checkout main
   git cherry-pick <working-commit>
   ```

2. **恢复Redis数据**（如果需要）
   - Session数据会自动过期，无需手动清理

3. **通知用户**
   - 提示用户重新登录（会话可能已失效）

4. **分析失败原因**
   - 检查错误日志
   - 复现问题场景
   - 修复后再次部署

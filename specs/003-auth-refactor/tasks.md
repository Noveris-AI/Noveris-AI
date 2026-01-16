# Tasks: 后端登录鉴权系统重构

**Feature**: 003-auth-refactor | **Branch**: `003-auth-refactor` | **Date**: 2026-01-17

## Overview

本任务列表包含 **32个任务**，按照用户故事组织，确保系统化地修复session cookie传递问题。

**预计时间**: 2-3天（1名开发者）
**关键路径**: Phase 2（基础优化）→ Phase 3（US1核心登录）→ Phase 4（US2错误处理）

## Phase 1: Setup & Preparation

### Infrastructure & Configuration

- [x] [T001] [P1] 确认开发环境依赖已安装（Redis 5.0+, Python 3.11+, uv或pip）
  - 运行 `redis-cli ping` 验证Redis可访问
  - 运行 `cd Backend && uv sync` 安装Python依赖
  - 验证 `Backend/.env` 中Redis密码配置正确（REDIS_PASSWORD=noveris_redis_pass_2025）

- [x] [T002] [P1] 验证CORS配置支持cookie传递
  - 检查 `Backend/.env` 中 `CORS_CREDENTIALS=true`
  - 检查 `CORS_ORIGINS` 包含前端域名（http://localhost:3000）
  - 文件：`Backend/app/main.py:40-47` (CORSMiddleware配置)

- [x] [T003] [P1] 创建测试用超级管理员账号（如果不存在）
  - 验证 `Backend/.env` 中 `ADMIN_AUTO_CREATE=True`
  - 启动backend确认日志中显示"Admin user created"
  - 测试凭据：admin@noveris.ai / admin@noveris.ai

---

## Phase 2: Foundational (Blocking Prerequisites)

### Redis Connection Pool Optimization

- [x] [T004] [P1] **BLOCKER** 实现Redis连接池单例模式
  - 文件：`Backend/app/core/dependencies.py`
  - 添加全局变量 `_redis_pool: Redis | None = None`
  - 创建 `async def get_redis_pool() -> Redis` 函数（单例模式）
  - 修改 `get_redis()` 函数返回连接池而非每次创建新连接
  - 参考：`specs/003-auth-refactor/quickstart.md:191-221`

- [x] [T005] [P1] **BLOCKER** 添加Redis连接健康检查
  - 文件：`Backend/app/core/dependencies.py`
  - 在 `get_redis_pool()` 中添加 `await _redis_pool.ping()` 检查
  - 连接失败时抛出 `RuntimeError` 并清空 `_redis_pool`
  - 添加日志：`logger.info("Redis connection pool initialized", max_connections=...)`

### Authentication Dependency Fix

- [x] [T006] [P1] **BLOCKER** 修复OPTIONS预检请求跳过认证
  - 文件：`Backend/app/core/dependencies.py:97-113`
  - 在 `get_current_user_optional()` 函数开头添加：
    ```python
    if request.method == "OPTIONS":
        return None
    ```
  - 参考：`specs/003-auth-refactor/research.md:103-117`

- [x] [T007] [P1] **BLOCKER** 添加认证检查日志（用于调试）
  - 文件：`Backend/app/core/dependencies.py`
  - 在 `get_current_user_optional()` 中记录：method, session_id前20字符, cookie_name, all_cookies, path
  - 使用 `structlog.get_logger(__name__)`
  - 参考：`specs/003-auth-refactor/quickstart.md:276-288`

---

## Phase 3: User Story 1 - 用户成功登录并访问受保护资源 (P1)

### Cookie Configuration Fix

- [x] [T008] [P1] [Story 1] **CRITICAL** 修复登录端点的cookie domain配置
  - 文件：`Backend/app/api/v1/auth.py` (POST /auth/login端点)
  - 定位 `response.set_cookie()` 调用
  - 修改 `domain=settings.session.cookie_domain or None` 为 `domain=None`
  - 确认其他参数：`httponly=True`, `samesite="lax"`, `path="/"`
  - 参考：`specs/003-auth-refactor/quickstart.md:80-106`

- [x] [T009] [P1] [Story 1] 验证cookie设置的TTL正确性
  - 文件：`Backend/app/api/v1/auth.py`
  - 检查 `max_age` 参数：`remember_me` 时为 `settings.session.remember_ttl`，否则为 `settings.session.ttl`
  - 验证默认值：TTL=1800（30分钟），REMEMBER_TTL=2592000（30天）

### Session Creation Logging

- [x] [T010] [P1] [Story 1] 添加session创建成功日志
  - 文件：`Backend/app/api/v1/auth.py` (POST /auth/login端点)
  - 在session创建后添加日志：session_id, user_id, email, cookie_name, ttl
  - 使用 `structlog.get_logger(__name__)`
  - 参考：`specs/003-auth-refactor/quickstart.md:233-248`

- [x] [T011] [P1] [Story 1] 添加session存储验证日志
  - 文件：`Backend/app/core/session.py` (SessionManager.create方法)
  - 在 `setex()` 后使用 `get()` 和 `ttl()` 验证存储成功
  - 记录：session_id, stored_successfully, ttl_remaining
  - 参考：`specs/003-auth-refactor/quickstart.md:250-264`

### Current User Endpoint

- [x] [T012] [P1] [Story 1] 验证 /auth/me 端点正确使用认证依赖
  - 文件：`Backend/app/api/v1/auth.py` (GET /auth/me端点)
  - 确认使用 `Depends(get_current_user)` 而非 `get_current_user_optional`
  - 验证返回 `UserResponse` schema（包含id, email, name, is_superuser等）
  - 参考：`specs/003-auth-refactor/contracts/auth-api.yaml:123-153`

- [x] [T013] [P1] [Story 1] 添加session检索日志
  - 文件：`Backend/app/core/session.py` (SessionManager.get方法)
  - 记录：session_id前20字符, session_key, data_found
  - 参考：`specs/003-auth-refactor/quickstart.md:266-274`

### Integration Testing

- [x] [T014] [P1] [Story 1] 手动测试：登录成功并访问 /auth/me
  - 启动backend：`cd Backend && python main.py`
  - 使用浏览器或curl测试登录流程
  - 验证：POST /auth/login返回200 + Set-Cookie ✅
  - 验证：GET /auth/me返回200 + 用户信息（不再401） ✅
  - 参考：`specs/003-auth-refactor/quickstart.md:308-334`
  - **VERIFIED**: 使用 http://localhost:3000 访问，登录和会话验证均正常工作

- [x] [T015] [P1] [Story 1] 手动测试：刷新页面保持登录状态
  - 登录成功后按F5刷新页面
  - 验证：GET /auth/me仍然返回200 ✅
  - 验证：浏览器仍然携带session_id cookie ✅
  - 参考：`specs/003-auth-refactor/quickstart.md:336-343`
  - **VERIFIED**: Cookie正确持久化，刷新页面保持登录状态

- [x] [T016] [P1] [Story 1] 手动测试：新标签页共享会话
  - 登录成功后在同一浏览器打开新标签页
  - 访问受保护页面（如首页）
  - 验证：新标签页自动显示已登录状态 ✅
  - 参考：`specs/003-auth-refactor/quickstart.md:345-350`
  - **VERIFIED**: Session cookie在同一浏览器的所有标签页间正确共享

---

## Phase 4: User Story 2 - 用户登录失败并收到清晰提示 (P1)

### Error Handling Enhancement

- [x] [T017] [P1] [Story 2] 统一错误响应格式
  - 文件：`Backend/app/api/v1/auth.py` (POST /auth/login端点)
  - 验证错误响应包含：`success: false`, `error.code`, `error.message`
  - 支持的错误码：INVALID_CREDENTIALS, ACCOUNT_DISABLED, RATE_LIMIT_EXCEEDED
  - 参考：`specs/003-auth-refactor/contracts/auth-api.yaml:335-381`

- [x] [T018] [P1] [Story 2] 实现登录失败计数（速率限制）
  - 文件：`Backend/app/services/auth_service.py` 或 `Backend/app/api/v1/auth.py`
  - 使用Redis存储：`auth:attempts:{ip}:{email}`，TTL=600秒
  - 失败5次后锁定10分钟，返回429错误
  - 参考：`specs/003-auth-refactor/data-model.md:97-107`

- [x] [T019] [P1] [Story 2] 添加账号禁用状态检查
  - 文件：`Backend/app/api/v1/auth.py` (POST /auth/login端点)
  - 在密码验证后检查 `user.is_active`
  - 如果禁用，返回401错误，code=ACCOUNT_DISABLED

### Validation & Testing

- [x] [T020] [P1] [Story 2] 手动测试：错误的邮箱/密码
  - 测试1：不存在的邮箱 → 返回401 + "邮箱或密码错误" ✅
  - 测试2：正确邮箱 + 错误密码 → 返回401 + "邮箱或密码错误" ✅
  - 验证：不泄露邮箱是否存在（安全性） ✅
  - 参考：`spec.md:45-48`
  - **VERIFIED**: 错误处理和结构化错误响应已通过测试

- [ ] [T021] [P2] [Story 2] 手动测试：速率限制
  - 连续5次输入错误密码
  - 验证：第6次返回429 + "尝试次数过多，请10分钟后再试"
  - 等待10分钟后验证可以再次尝试
  - 参考：`spec.md:48`
  - **NOTE**: 代码已完成，需要专门测试速率限制功能

---

## Phase 5: User Story 3 - 用户安全退出登录 (P1)

### Logout Implementation

- [x] [T022] [P1] [Story 3] 实现登出端点清除Redis会话
  - 文件：`Backend/app/api/v1/auth.py` (POST /auth/logout端点)
  - 使用 `session_manager.delete(session_id)` 删除Redis中的session
  - 从用户会话集合中移除：`SREM session:user:{user_id} {session_id}`
  - 参考：`specs/003-auth-refactor/data-model.md:181-195`

- [x] [T023] [P1] [Story 3] 实现登出端点清除Cookie
  - 文件：`Backend/app/api/v1/auth.py` (POST /auth/logout端点)
  - 调用 `response.delete_cookie(key=settings.session.cookie_name, path="/")`
  - 或设置 `response.set_cookie(..., max_age=0)`
  - 参考：`specs/003-auth-refactor/contracts/auth-api.yaml:107-112`

- [x] [T024] [P1] [Story 3] 手动测试：登出清除会话
  - 登录后点击登出按钮
  - 验证：POST /auth/logout返回200 ✅
  - 验证：浏览器Cookie中session_id已被删除 ✅
  - 验证：尝试访问 /auth/me 返回401 ✅
  - 参考：`specs/003-auth-refactor/quickstart.md:352-361`
  - **VERIFIED**: 登出功能正常，Cookie正确清除

---

## Phase 6: User Story 4 - 会话自动过期保护 (P2)

### Session Expiration Logic

- [x] [T025] [P2] [Story 4] 实现会话过期检查（已存在，验证）
  - 文件：`Backend/app/core/session.py` (SessionManager.get方法)
  - 验证：从Redis读取session后检查 `expires_at > now`
  - 如果过期，返回None并删除Redis中的key

- [x] [T026] [P2] [Story 4] 实现条件续期（Conditional Renewal）
  - 文件：`Backend/app/core/dependencies.py` (get_current_user_optional)
  - 添加续期逻辑：仅当 `expires_at - now < ttl / 2` 时续期
  - 调用 `session_manager.extend(session_id)` 更新TTL
  - 参考：`specs/003-auth-refactor/research.md:148-167`

- [x] [T027] [P2] [Story 4] 添加会话过期提示（前端配合）
  - 后端：确保401响应包含 `error.code=UNAUTHORIZED`, `message="Session expired"`
  - 前端（可选）：在401拦截器中区分"未登录"和"会话过期"
  - 参考：`spec.md:80`

### Testing

- [ ] [T028] [P2] [Story 4] 手动测试：会话自动过期
  - 方案1：临时修改 `SESSION_TTL=120`（2分钟）
  - 登录后等待2分钟不操作
  - 尝试访问 /auth/me，验证返回401 + "Session expired"
  - 参考：`spec.md:80`
  - **NOTE**: 代码修复已完成，待用户实际运行时验证

---

## Phase 7: User Story 5 - 跨设备登录管理 (P3)

### Session Management API

- [x] [T029] [P3] [Story 5] 实现查看活跃会话列表端点
  - 文件：`Backend/app/api/v1/auth.py` (GET /auth/sessions)
  - 使用Redis：`SMEMBERS session:user:{user_id}` 获取所有session_id
  - 返回：`{active_sessions: count, max_sessions: 5}`
  - 参考：`specs/003-auth-refactor/contracts/auth-api.yaml:154-191`

- [x] [T030] [P3] [Story 5] 实现注销所有其他设备会话端点
  - 文件：`Backend/app/api/v1/auth.py` (DELETE /auth/sessions)
  - 使用Redis：`SMEMBERS session:user:{user_id}` 获取所有session_id
  - 删除除当前session外的所有会话：`DEL session:{id}`
  - 清空用户会话集合并重新添加当前session
  - 参考：`specs/003-auth-refactor/contracts/auth-api.yaml:193-215`

- [ ] [T031] [P3] [Story 5] 手动测试：跨设备会话管理
  - 在浏览器A和B分别登录
  - 调用GET /auth/sessions，验证看到2个活跃会话
  - 在浏览器A调用DELETE /auth/sessions
  - 验证浏览器B自动退出登录（访问 /auth/me 返回401）
  - 参考：`spec.md:94-99`
  - **NOTE**: 代码已完成，待用户实际运行时验证

---

## Final Phase: Polish & Cross-Cutting Concerns

### Testing & Documentation

- [ ] [T032] [P1] 运行完整测试套件并确保通过
  - 单元测试：`pytest tests/unit/test_session.py tests/unit/test_dependencies.py -v`
  - 集成测试：`pytest tests/integration/test_auth_flow.py -v`
  - 覆盖率：`pytest --cov=app --cov-report=term-missing`
  - 目标：80%+ 覆盖率
  - 参考：`specs/003-auth-refactor/quickstart.md:363-383`
  - **NOTE**: tests目录尚未创建，建议用户实际运行时通过手动测试验证功能

---

## Task Dependency Graph

### Critical Path (P1 tasks)
```
T001-T003 (Setup)
    ↓
T004-T007 (BLOCKERS: Redis pool + OPTIONS fix)
    ↓
T008-T013 (US1: Cookie fix + Logging)
    ↓
T014-T016 (US1: Manual testing)
    ↓
T017-T021 (US2: Error handling)
    ↓
T022-T024 (US3: Logout)
    ↓
T032 (Final testing)
```

### Parallel Execution
- T001, T002, T003 可以并行执行（环境验证）
- T008, T009 可以并行执行（cookie配置）
- T010, T011, T013 可以并行执行（日志添加）
- T014, T015, T016 必须顺序执行（依赖浏览器状态）
- T025-T031 可以在P1任务完成后并行开发（P2/P3功能）

---

## Notes

**关键文件**:
- `Backend/app/api/v1/auth.py` - 登录/登出/me端点（修改8处）
- `Backend/app/core/dependencies.py` - 认证依赖（修改4处）
- `Backend/app/core/session.py` - Session管理（修改3处）

**测试策略**:
- 手动测试：浏览器 + 开发者工具（Cookie检查）
- 自动化测试：pytest单元测试 + 集成测试
- 性能测试：Apache Bench验证登录响应时间 <100ms

**回滚计划**:
如果重构导致问题，执行：
```bash
git checkout main
git cherry-pick <working-commit>
```

**参考文档**:
- 完整实施指南：`specs/003-auth-refactor/quickstart.md`
- 数据模型：`specs/003-auth-refactor/data-model.md`
- API契约：`specs/003-auth-refactor/contracts/auth-api.yaml`
- 研究文档：`specs/003-auth-refactor/research.md`

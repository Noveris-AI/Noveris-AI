# Auth Integration 调试会话记录

**日期**: 2026-01-16
**Feature**: 003-auth-refactor
**状态**: ✅ 已解决

## 问题描述

用户在浏览器中测试认证功能时遇到以下错误：
```
GET http://localhost:8000/api/v1/auth/me 401 (Unauthorized)
GET http://localhost:8000/api/v1/authz/me 401 (Unauthorized)
```

日志显示：
```
{"path": "/api/v1/auth/me", "event": "No session cookie found", "logger": "app.core.dependencies", "level": "warning"}
```

## 关键发现

### 测试验证结果

**curl 测试（命令行）**：✅ 完全正常
- 登录请求返回 200 OK + Set-Cookie
- `/auth/me` 请求携带 cookie 返回 200 OK + 用户数据
- CORS 头配置正确

**浏览器测试**：❌ 初始失败
- 登录成功但后续请求返回 401
- Cookie 未被浏览器发送到后端

## 根本原因

**域名不匹配导致的跨域 Cookie 问题**

用户实际访问的 URL：
```
http://127.0.0.1:3000/auth/login
```

前端配置的 API 基础 URL：
```
VITE_API_BASE_URL=http://localhost:8000
```

### 问题分析

1. **Cookie 域隔离**：
   - 浏览器将 `localhost` 和 `127.0.0.1` 视为**两个不同的域**
   - 当从 `127.0.0.1:3000` 访问 `localhost:8000` 时，属于跨域请求
   - 即使 CORS 配置正确，Cookie 也不会在跨域情况下自动发送（安全机制）

2. **Cookie 设置位置**：
   - 登录请求（测试代码）：`http://127.0.0.1:8000` → Cookie 设置到 `127.0.0.1` 域
   - 后续请求（前端代码）：`http://localhost:8000` → 从 `localhost` 域查找 Cookie（找不到）

3. **症状表现**：
   - ✅ 登录成功（cookie 被设置）
   - ❌ 后续请求 401（cookie 未被发送）
   - ✅ curl 测试成功（统一使用 localhost）

## 解决方案

### 方案 1：统一使用 localhost（推荐）✅

**操作**：在浏览器地址栏中访问
```
http://localhost:3000
```

而不是 `http://127.0.0.1:3000`

**优点**：
- ✅ 无需修改任何配置
- ✅ 无需重启服务
- ✅ 立即生效
- ✅ 符合安全最佳实践

**结果**：用户确认 "localhost能运行" ✅

### 方案 2：统一使用 127.0.0.1（备选）

修改 `.env` 配置：
```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

然后重启前端服务。

**优点**：
- 适用于需要使用 IP 地址的特殊场景

**缺点**：
- 需要重启前端
- 需要修改配置文件

## 技术细节

### Cookie 配置（已验证正确）

```http
Set-Cookie: session_id=...; HttpOnly; Max-Age=1800; Path=/; SameSite=lax
```

配置参数：
- `HttpOnly=true` - 防止 JavaScript 访问（安全）
- `Secure=false` - HTTP 可用（开发环境）
- `SameSite=lax` - 允许顶级导航携带 cookie
- `Max-Age=1800` - 30分钟有效期
- `Path=/` - 所有路径可用
- `domain=None` - 当前主机（最安全）

### CORS 配置（已验证正确）

```bash
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,...
CORS_CREDENTIALS=true
```

响应头：
```http
access-control-allow-origin: http://localhost:3000
access-control-allow-credentials: true
```

### Redis 会话存储（已验证正常）

- Redis 容器：正常运行
- Session 创建：成功
- Session 检索：成功
- TTL 管理：正常

## 调试过程中的关键步骤

### 1. 环境检查
- ✅ Python 3.13 安装
- ✅ Redis 容器运行（`docker-compose up -d`）
- ✅ 后端依赖安装（`pip install -e .`）
- ✅ 前端运行在端口 3000

### 2. 代码修复
- ✅ Cookie domain 设置为 `None`（3处）
- ✅ SESSION_TTL 修改为 1800s（30分钟）
- ✅ Rate limit window 修改为 600s（10分钟）
- ✅ 条件续期逻辑（仅在 TTL <50% 时）
- ✅ 结构化错误响应支持

### 3. 日志增强
添加详细的调试日志：
```python
logger.info(
    "Checking auth session",
    cookie_header=request.headers.get("cookie"),
    origin=request.headers.get("origin"),
    referer=request.headers.get("referer"),
)
```

### 4. 诊断工具
创建了 `test-auth.html` 调试页面（虽然最终因为 `file://` origin 问题未使用）

### 5. 最终验证
通过浏览器控制台测试脚本：
```javascript
console.log('🌐 当前URL:', window.location.href);
// 执行登录和会话验证测试
```

## 经验教训

### 1. 域名一致性至关重要
- 前后端必须使用**完全相同**的域名（localhost 或 127.0.0.1）
- Cookie 不会在不同域名间共享，即使 CORS 配置正确

### 2. 调试步骤
1. 先用 curl 验证后端功能（排除后端问题）
2. 检查浏览器实际访问的 URL（不是配置，而是地址栏）
3. 检查 Network 标签中的 Request/Response Headers
4. 检查 Application → Cookies 确认 cookie 是否被设置

### 3. Cookie 调试最佳实践
- 查看 Response Headers 的 `set-cookie`
- 查看 Request Headers 的 `cookie`
- 确认 domain/path/samesite 配置
- 验证 CORS credentials 配置

### 4. 浏览器安全限制
- `file://` 协议的 origin 是 `null`，不能用于 CORS 测试
- 必须通过 HTTP 服务器（如 Vite dev server）提供页面

## 任务完成状态

### P1 核心功能（已完成）✅
- [x] T001-T013: 环境、代码修复、日志
- [x] T014-T016: 浏览器集成测试
- [x] T017-T020: 错误处理
- [x] T022-T024: 登出功能

### P2/P3 功能（代码已完成，待测试）
- [x] T025-T027: 会话过期（代码完成）
- [x] T029-T030: 跨设备管理（代码完成）
- [ ] T021: 速率限制测试（需专门测试）
- [ ] T028: 会话过期测试（需等待30分钟）
- [ ] T031: 跨设备测试（需多浏览器）
- [ ] T032: 完整测试套件（pytest）

## 最终配置

### Backend/.env
```bash
# 使用 localhost（推荐）
VITE_API_BASE_URL=http://localhost:8000

# CORS 同时支持两种访问方式
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,...
CORS_CREDENTIALS=true

# Session 配置
SESSION_TTL=1800  # 30 minutes
SESSION_COOKIE_SECURE=false  # dev only
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=lax
```

### 访问方式
✅ **推荐**：`http://localhost:3000`
⚠️ **可用但需配置**：`http://127.0.0.1:3000`（需修改 VITE_API_BASE_URL）

## 相关文件

### 修改的文件
1. `Backend/app/api/v1/auth.py` - Cookie domain 修复
2. `Backend/app/core/config.py` - SESSION_TTL 修复
3. `Backend/app/core/dependencies.py` - 条件续期逻辑
4. `Backend/app/main.py` - 结构化错误响应
5. `Backend/.env` - CORS 配置

### 新增的文件
1. `test-auth.html` - Cookie 调试工具（最终未使用）
2. `specs/003-auth-refactor/debugging-session-notes.md` - 本文档

## 下一步建议

1. **生产环境配置**：
   - 修改 `SESSION_COOKIE_SECURE=true`
   - 使用 HTTPS
   - 修改 `SECRET_KEY` 和 `SESSION_SECRET`
   - 考虑 `SameSite=strict` 或 `none`（如果需要跨站）

2. **完整测试**：
   - 执行 T021（速率限制）
   - 执行 T028（会话过期）
   - 执行 T031（跨设备管理）
   - 编写自动化测试（pytest）

3. **性能优化**：
   - 监控 Redis 连接池使用情况
   - 监控会话续期频率（应降低 50%）
   - 添加会话统计指标

4. **安全加固**：
   - 定期轮换加密密钥
   - 实施会话固定攻击防护
   - 添加设备指纹识别
   - 实施异常登录检测

## 参考资料

- [MDN - HTTP Cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies)
- [MDN - CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [FastAPI - Cookie Parameters](https://fastapi.tiangolo.com/advanced/cookie-params/)
- [RFC 6265 - HTTP State Management Mechanism](https://tools.ietf.org/html/rfc6265)

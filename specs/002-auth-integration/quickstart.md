# Quick Start Guide: 前后端鉴权集成

**Feature**: 002-auth-integration
**Date**: 2026-01-16
**Status**: Ready for Implementation

## Overview

本快速入门指南帮助开发者快速理解和实现前后端真实鉴权集成。通过本指南,你将学会如何移除Mock鉴权、配置真实的会话管理、以及实现完整的登录流程。

---

## Prerequisites (前置要求)

### 环境检查

```bash
# 检查Python版本
python --version  # 应为 3.11+

# 检查Node版本
node --version    # 应为 18.0+

# 检查Redis是否运行
redis-cli ping   # 应返回 PONG
```

### 依赖安装

**后端**:
```bash
cd Backend
pip install -r requirements.txt
```

**前端**:
```bash
cd Frontend
npm install
```

---

## 5-Minute Quick Start (5分钟快速开始)

### Step 1: 配置环境变量

**Backend/.env**:
```bash
# 数据库配置(如果未配置)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=noveris_ai
DB_USER=postgres
DB_PASSWORD=yourpassword

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=  # 如无密码则留空

# 会话配置
SESSION_COOKIE_NAME=session_id
SESSION_TTL=86400  # 24小时
SESSION_REMEMBER_TTL=2592000  # 30天

# 调试模式
APP_DEBUG=true
```

**Frontend/.env**:
```bash
# API地址
VITE_API_BASE_URL=http://localhost:8000

# 禁用Mock鉴权(重要!)
VITE_USE_MOCK_AUTH=false
```

### Step 2: 启动服务

**启动后端**:
```bash
cd Backend
python main.py
```

应该看到:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

**启动前端**:
```bash
cd Frontend
npm run dev
```

应该看到:
```
  VITE v5.x.x  ready in 500 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### Step 3: 创建测试账号

**方式1: 通过API直接创建**:
```bash
# 发送验证码
curl -X POST http://localhost:8000/api/v1/auth/send-verification-code \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# 查看后端日志获取验证码(开发模式下会打印)
# 输出: Verification Code for test@example.com: 123456

# 注册账号
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "verification_code": "123456",
    "password": "TestPassword123!",
    "name": "测试用户"
  }'
```

**方式2: 通过前端注册**:
1. 访问 http://localhost:5173/auth/register
2. 输入邮箱,点击"发送验证码"
3. 查看后端日志获取验证码
4. 填写完整信息并提交

### Step 4: 测试登录

1. 访问 http://localhost:5173 或 http://localhost:5173/dashboard/homepage
2. 应该自动重定向到 http://localhost:5173/auth/login
3. 输入邮箱和密码,点击"登录"
4. 成功后应重定向到主页

### Step 5: 验证鉴权工作

打开浏览器开发者工具(F12):

**检查Cookie**:
- Application → Cookies → http://localhost:5173
- 应该看到 `session_id` Cookie
- 属性: HttpOnly, SameSite=Lax

**检查Network**:
- 访问任意API(如节点列表)
- Request Headers应包含 `Cookie: session_id=...`
- 不应再看到 `Authorization: Bearer mock-dev-token-for-testing`

**测试登出**:
- 点击用户头像 → 退出登录
- Cookie应被清除
- 再次访问Dashboard应重定向到登录页

---

## Common Workflows (常见工作流程)

### Workflow 1: 用户注册流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Frontend as 前端
    participant Backend as 后端
    participant Redis as Redis
    participant Email as 邮件服务

    User->>Frontend: 访问注册页面
    User->>Frontend: 输入邮箱,点击"发送验证码"
    Frontend->>Backend: POST /auth/send-verification-code
    Backend->>Redis: 存储验证码(TTL 5分钟)
    Backend->>Email: 发送验证码邮件
    Backend-->>Frontend: 返回成功
    Frontend-->>User: 显示"验证码已发送"

    User->>Frontend: 输入验证码、密码、姓名
    User->>Frontend: 点击"注册"
    Frontend->>Backend: POST /auth/register
    Backend->>Redis: 验证验证码
    Backend->>DB: 创建用户账号
    Backend->>Email: 发送欢迎邮件
    Backend-->>Frontend: 返回成功
    Frontend-->>User: 重定向到登录页
```

### Workflow 2: 用户登录流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Frontend as 前端
    participant Backend as 后端
    participant Redis as Redis
    participant DB as 数据库

    User->>Frontend: 访问受保护页面
    Frontend-->>User: 重定向到登录页

    User->>Frontend: 输入邮箱、密码
    User->>Frontend: 点击"登录"
    Frontend->>Backend: POST /auth/login
    Backend->>DB: 查询用户,验证密码
    Backend->>Redis: 创建会话(TTL 24小时)
    Backend->>DB: 更新last_login_at
    Backend->>DB: 记录登录历史
    Backend-->>Frontend: Set-Cookie: session_id
    Backend-->>Frontend: 返回用户信息
    Frontend->>Frontend: 保存用户信息到Context
    Frontend-->>User: 重定向到主页

    User->>Frontend: 访问API(如节点列表)
    Frontend->>Backend: GET /nodes (带Cookie)
    Backend->>Redis: 验证会话
    Redis-->>Backend: 返回会话数据
    Backend-->>Frontend: 返回节点列表
```

### Workflow 3: 会话过期处理

```mermaid
sequenceDiagram
    participant User as 用户
    participant Frontend as 前端
    participant Backend as 后端
    participant Redis as Redis

    User->>Frontend: 长时间未操作(>24小时)
    User->>Frontend: 访问API
    Frontend->>Backend: GET /some-api (带过期Cookie)
    Backend->>Redis: 查询会话
    Redis-->>Backend: 会话不存在或已过期
    Backend-->>Frontend: 401 Unauthorized
    Frontend->>Frontend: HTTP拦截器捕获401
    Frontend->>Frontend: 清除AuthContext状态
    Frontend-->>User: 重定向到登录页
    Frontend-->>User: 显示"会话已过期,请重新登录"
```

---

## Code Examples (代码示例)

### Example 1: 前端ProtectedRoute组件

```typescript
// Frontend/src/shared/components/routing/ProtectedRoute.tsx
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/features/auth/hooks/useAuth'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <LoadingSpinner />
  }

  if (!isAuthenticated) {
    // 保存原始URL,登录后跳转回来
    return <Navigate to="/auth/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}

// 使用方式
<Route
  path="/dashboard"
  element={
    <ProtectedRoute>
      <DashboardLayout />
    </ProtectedRoute>
  }
>
  {/* 子路由 */}
</Route>
```

### Example 2: 前端AuthContext

```typescript
// Frontend/src/features/auth/contexts/AuthContext.tsx
import { createContext, useContext, useState, useEffect, useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { authClient } from '../api/authClient'
import type { User } from '../api/authTypes'

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (credentials: LoginRequest) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const [shouldCheckAuth, setShouldCheckAuth] = useState(false)

  const { data: user, isLoading, error } = useQuery({
    queryKey: ['currentUser'],
    queryFn: () => authClient.getCurrentUser(),
    enabled: shouldCheckAuth,
    staleTime: 5 * 60 * 1000, // 5分钟
    retry: false,
  })

  const login = async (credentials: LoginRequest) => {
    const response = await authClient.login(credentials)
    setShouldCheckAuth(true)
    queryClient.invalidateQueries({ queryKey: ['currentUser'] })
  }

  const logout = async () => {
    await authClient.logout()
    setShouldCheckAuth(false)
    queryClient.clear()
  }

  const checkAuth = async () => {
    setShouldCheckAuth(true)
  }

  const value = useMemo(
    () => ({
      user: user ?? null,
      isAuthenticated: !!user,
      isLoading,
      login,
      logout,
      checkAuth,
    }),
    [user, isLoading]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
```

### Example 3: 后端会话依赖注入

```python
# Backend/app/core/dependencies.py
from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from app.services.session_service import SessionManager

async def get_session_manager(
    request: Request,
    redis: Annotated[object, Depends(get_redis)],
) -> SessionManager:
    """Get session manager instance."""
    return SessionManager(redis)

async def get_current_user(
    request: Request,
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> dict:
    """
    Get current authenticated user from session.

    Raises 401 if session is invalid or expired.
    """
    # 从Cookie获取session_id
    session_id = request.cookies.get(settings.session.cookie_name)

    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
        )

    # 从Redis获取会话数据
    session_data = await session_manager.get(session_id)

    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已过期",
        )

    return session_data

# 使用方式
CurrentUserDep = Annotated[dict, Depends(get_current_user)]

@router.get("/protected-endpoint")
async def protected_endpoint(current_user: CurrentUserDep):
    user_id = current_user["user_id"]
    # ... 处理业务逻辑
```

---

## Troubleshooting (故障排除)

### Problem 1: 登录后仍然401错误

**症状**: 登录成功,但访问API仍返回401

**检查**:
```bash
# 1. 检查Cookie是否设置成功
# 浏览器开发者工具 → Application → Cookies
# 应该看到 session_id

# 2. 检查Redis中是否有会话
redis-cli
> keys session:*
> hgetall session:abc123  # 替换为实际的session_id

# 3. 检查前端是否携带Cookie
# Network → 某个API请求 → Headers → Cookie
# 应该包含 session_id=...
```

**解决方案**:
- 确保前端配置了 `credentials: 'include'`(已在BaseApiClient中配置)
- 确保后端CORS配置允许credentials
- 确保前后端域名一致(或同一主域名)

---

### Problem 2: 前端仍在使用Mock token

**症状**: Network请求中看到 `Authorization: Bearer mock-dev-token-for-testing`

**检查**:
```bash
# 检查环境变量
cat Frontend/.env | grep VITE_USE_MOCK_AUTH
```

**解决方案**:
```bash
# 1. 设置环境变量
echo "VITE_USE_MOCK_AUTH=false" >> Frontend/.env

# 2. 重启前端服务
cd Frontend
npm run dev
```

---

### Problem 3: 会话提前过期

**症状**: 未到24小时就被登出

**检查**:
```bash
# 检查Redis TTL
redis-cli
> ttl session:abc123
# 应返回剩余秒数,如果是-2表示已过期
```

**原因**:
- Redis配置了maxmemory策略,导致会话被提前驱逐
- 后端配置的SESSION_TTL太短

**解决方案**:
```bash
# 1. 检查Redis配置
redis-cli config get maxmemory-policy

# 2. 修改为noeviction或allkeys-lru
redis-cli config set maxmemory-policy noeviction

# 3. 或增加Redis内存限制
redis-cli config set maxmemory 1gb
```

---

### Problem 4: 验证码收不到

**症状**: 点击"发送验证码"后,邮箱未收到邮件

**检查**:
```bash
# 1. 检查后端日志
tail -f Backend/logs/app.log | grep "Verification Code"

# 2. 开发模式下,验证码会打印到控制台
# 查看后端运行窗口的输出
```

**解决方案**:
- 开发环境:直接从后端日志获取验证码
- 生产环境:配置SMTP服务器(`Backend/.env`中配置SMTP相关参数)

---

### Problem 5: CORS错误

**症状**: 浏览器控制台显示CORS错误

```
Access to fetch at 'http://localhost:8000/api/v1/auth/login' from origin
'http://localhost:5173' has been blocked by CORS policy
```

**解决方案**:
```python
# Backend/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # 前端域名
    allow_credentials=True,  # 重要:允许Cookie
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Testing Guide (测试指南)

### Manual Testing Checklist

- [ ] **登录流程**
  - [ ] 输入错误密码,显示错误提示
  - [ ] 输入正确密码,成功登录并重定向到主页
  - [ ] 勾选"记住我",关闭浏览器重新打开仍保持登录

- [ ] **路由守卫**
  - [ ] 未登录访问Dashboard,自动重定向到登录页
  - [ ] 登录后访问原始URL

- [ ] **会话管理**
  - [ ] 点击登出,清除会话并重定向到登录页
  - [ ] 等待会话过期(调短TTL测试),访问API返回401

- [ ] **注册流程**
  - [ ] 发送验证码,收到邮件(或查看日志)
  - [ ] 输入验证码和密码,成功注册
  - [ ] 使用新账号登录

- [ ] **密码重置**
  - [ ] 请求重置链接,收到邮件
  - [ ] 点击链接,设置新密码
  - [ ] 使用新密码登录

### Automated Testing

**前端E2E测试** (Playwright):
```typescript
// Frontend/tests/e2e/auth.spec.ts
import { test, expect } from '@playwright/test'

test('login flow', async ({ page }) => {
  // 访问Dashboard,应重定向到登录页
  await page.goto('/dashboard/homepage')
  await expect(page).toHaveURL('/auth/login')

  // 输入凭据
  await page.fill('[name="email"]', 'test@example.com')
  await page.fill('[name="password"]', 'TestPassword123!')
  await page.click('button[type="submit"]')

  // 登录成功,重定向到主页
  await expect(page).toHaveURL('/dashboard/homepage')

  // 检查用户名显示
  await expect(page.locator('text=测试用户')).toBeVisible()
})
```

**后端集成测试** (pytest):
```python
# Backend/tests/integration/test_auth.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # 登录
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "TestPassword123!",
        "remember_me": False,
    })

    assert response.status_code == 200
    assert response.json()["success"] is True

    # 检查Cookie
    assert "session_id" in response.cookies

    # 使用session访问受保护端点
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
```

---

## Next Steps (下一步)

现在你已经完成了鉴权集成的基础设置,可以:

1. **移除Mock代码**: 参考 `MOCK_AUTH_GUIDE.md`,彻底删除Mock鉴权相关代码

2. **优化用户体验**:
   - 添加"记住我"功能的UI提示
   - 登录页显示密码强度指示器
   - 优化错误提示文案

3. **增强安全性**:
   - 配置生产环境的Secure Cookie
   - 启用HTTPS
   - 配置SMTP发送真实邮件

4. **实现高级功能**:
   - SSO集成(Google, Azure AD)
   - 多因素认证(MFA)
   - 设备管理和可信设备

5. **监控和日志**:
   - 配置登录失败告警
   - 分析登录历史,检测异常行为
   - 导出审计日志

---

## Resources (资源)

### Documentation
- [Feature Specification](./spec.md)
- [Data Model](./data-model.md)
- [API Contract](./contracts/auth-api.yaml)
- [Type Mapping](./contracts/type-mapping.md)
- [Research](./research.md)

### External Links
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [React Router Authentication](https://reactrouter.com/en/main/start/tutorial#authentication)
- [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)

---

**文档版本**: 1.0.0
**最后更新**: 2026-01-16
**审核状态**: Approved

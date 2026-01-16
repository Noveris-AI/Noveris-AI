# 前端空白页面问题修复

## 问题描述

访问首页时出现空白页面，浏览器控制台报错：

```
AuthContext.tsx:5 Uncaught SyntaxError: The requested module '/src/shared/lib/apiClient.ts' does not provide an export named 'apiClient'
```

## 根本原因

1. **缺少 apiClient 实例导出**: `apiClient.ts` 只导出了 `BaseApiClient` 类，没有创建和导出全局实例
2. **错误的导入路径**: `App.tsx` 从错误的位置导入 `useAuth`
3. **函数引用问题**: AuthContext 中的函数没有使用 `useCallback` 包装，导致依赖问题

## 修复内容

### 1. 创建并导出 apiClient 实例

**文件**: `Frontend/src/shared/lib/apiClient.ts`

```typescript
// Create and export a global API client instance
export const apiClient = new BaseApiClient()

export default BaseApiClient
```

### 2. 修复 App.tsx 导入

**文件**: `Frontend/src/App.tsx`

修改前:
```typescript
import { AuthProvider, useAuth } from './features/auth/contexts/AuthContext'
```

修改后:
```typescript
import { AuthProvider } from './features/auth/contexts/AuthContext'
import { useAuth } from './features/auth/hooks/useAuth'
```

### 3. 使用 useCallback 优化 AuthContext

**文件**: `Frontend/src/features/auth/contexts/AuthContext.tsx`

```typescript
import { useCallback } from 'react'

// ...

const login = useCallback(async (credentials: LoginRequest) => {
  await authClient.login(credentials)
  setShouldCheckAuth(true)
  queryClient.invalidateQueries({ queryKey: ['currentUser'] })
}, [queryClient])

const logout = useCallback(async () => {
  try {
    await authClient.logout()
  } catch (error) {
    console.warn('Logout request failed:', error)
  } finally {
    setShouldCheckAuth(false)
    queryClient.clear()
  }
}, [queryClient])

const checkAuth = useCallback(() => {
  setShouldCheckAuth(true)
}, [])
```

## 验证步骤

1. **清除浏览器缓存**: 按 `Ctrl+Shift+Delete` 清除缓存
2. **重启开发服务器**:
   ```bash
   cd Frontend
   npm run dev
   ```
3. **访问首页**: 打开 `http://localhost:3000`
4. **检查控制台**: 确认没有错误信息
5. **测试重定向**: 未登录时应自动跳转到 `/auth/login`

## 预期行为

- ✅ 页面正常加载，不再空白
- ✅ 未登录用户自动重定向到登录页
- ✅ 无 JavaScript 错误
- ✅ AuthProvider 正常工作
- ✅ ProtectedRoute 正常拦截

## 如果问题仍然存在

### 1. 检查浏览器控制台

按 `F12` 打开开发者工具，查看：
- Console 标签: 是否有其他错误
- Network 标签: API 请求是否正常

### 2. 清除 node_modules 重新安装

```bash
cd Frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### 3. 检查文件路径

确认以下文件存在：
- `Frontend/src/shared/lib/apiClient.ts`
- `Frontend/src/features/auth/contexts/AuthContext.tsx`
- `Frontend/src/features/auth/hooks/useAuth.ts`
- `Frontend/src/shared/components/routing/ProtectedRoute.tsx`

### 4. 检查 TypeScript 编译

```bash
cd Frontend
npm run build
```

查看是否有 TypeScript 类型错误。

## 相关文件清单

- ✅ `Frontend/src/shared/lib/apiClient.ts` - 添加 apiClient 实例导出
- ✅ `Frontend/src/App.tsx` - 修复导入路径
- ✅ `Frontend/src/features/auth/contexts/AuthContext.tsx` - 使用 useCallback 优化

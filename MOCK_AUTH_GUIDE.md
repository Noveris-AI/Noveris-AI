# Mock Authentication 使用指南

## 概述

为了避免在开发过程中遇到401鉴权错误，我们提供了一个mock authentication（模拟鉴权）方案。这个方案允许前端在不需要真实登录的情况下访问API。

## 🔧 工作原理

### 前端部分
- 在开发模式下，前端会自动在所有API请求中添加一个mock bearer token
- Token格式：`Bearer mock-dev-token-for-testing`
- 通过环境变量 `VITE_USE_MOCK_AUTH` 控制是否启用

### 后端部分
- 后端在调试模式下会识别mock token
- 识别到mock token后，自动创建一个mock session
- Mock session包含：
  - user_id: `00000000-0000-0000-0000-000000000001`
  - tenant_id: `00000000-0000-0000-0000-000000000001`
  - email: `dev@example.com`
  - is_superuser: `true`
  - role: `admin`

## 🚀 启用方法

### 方法1：使用环境变量（默认启用）

前端的 `.env` 文件已经配置好：

```bash
# Frontend/.env
VITE_USE_MOCK_AUTH=true
```

这个配置在开发模式下默认启用mock authentication。

### 方法2：临时禁用

如果你想测试真实的登录流程，可以设置：

```bash
# Frontend/.env
VITE_USE_MOCK_AUTH=false
```

然后重启前端开发服务器：

```bash
cd Frontend
npm run dev
```

## 📋 使用步骤

### 1. 确认配置

检查前端环境配置：

```bash
# Frontend/.env
VITE_USE_MOCK_AUTH=true
VITE_API_BASE_URL=http://localhost:8000
```

### 2. 启动后端

```bash
cd Backend
python main.py
```

后端会在调试模式下自动支持mock token。

### 3. 启动前端

```bash
cd Frontend
npm run dev
```

前端会自动在所有API请求中注入mock token。

### 4. 访问应用

打开浏览器访问 `http://localhost:5173`

现在你可以直接访问任何页面，不会遇到401错误！

## 🔍 验证是否生效

### 方法1：查看浏览器控制台

打开浏览器开发者工具（F12），你应该能看到：

```
[Dev Mode] Using mock authentication token
```

### 方法2：检查网络请求

在浏览器Network标签中，查看任何API请求的Headers部分，应该能看到：

```
Authorization: Bearer mock-dev-token-for-testing
```

## ⚠️ 注意事项

### 安全性
- **仅在开发模式下使用**
- 生产环境会自动禁用mock authentication
- Mock token仅在后端调试模式（APP_DEBUG=true）下有效

### 限制
- Mock用户具有超级管理员权限
- 所有操作都会以mock用户身份执行
- 不会创建真实的用户记录

### 切换回真实鉴权

当你需要测试真实登录流程时：

1. 设置 `VITE_USE_MOCK_AUTH=false`
2. 重启前端服务器
3. 访问登录页面进行正常登录

## 🐛 故障排除

### 仍然出现401错误

1. **检查环境变量**：
   ```bash
   # 确认 .env 文件中的配置
   cat Frontend/.env | grep VITE_USE_MOCK_AUTH
   ```

2. **重启开发服务器**：
   ```bash
   # 停止前端服务器（Ctrl+C）
   # 重新启动
   npm run dev
   ```

3. **检查后端调试模式**：
   ```bash
   # Backend/.env
   APP_DEBUG=true
   ```

4. **清除浏览器缓存**：
   - 按 Ctrl+Shift+Delete
   - 清除cookie和缓存
   - 刷新页面

### Mock token不工作

检查后端日志，确认：
- 后端正在调试模式下运行
- Authorization header正确发送

### API_BASE_URL配置错误

如果前端无法连接后端：

```bash
# Frontend/.env
VITE_API_BASE_URL=http://localhost:8000  # 确保端口正确
```

后端默认端口是8000，可以在 `Backend/.env` 中修改。

## 📝 环境变量参考

### 前端环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `VITE_USE_MOCK_AUTH` | 启用mock鉴权 | `true` |
| `VITE_API_BASE_URL` | 后端API地址 | `http://localhost:8000` |
| `VITE_AUTH_API_MODE` | 鉴权模式 | `real` |

### 后端环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `APP_DEBUG` | 调试模式 | 是 |
| `API_HOST` | API监听地址 | 否 |
| `API_PORT` | API监听端口 | 否 |

## 🎯 下一步

现在你已经配置好mock authentication，可以：

1. 测试节点管理功能
2. 验证加速器类型显示
3. 测试分页功能
4. 进行集成测试

当你准备测试真实鉴权流程时，只需将 `VITE_USE_MOCK_AUTH` 设置为 `false` 即可。

# Frontend-Backend Type Mapping

**Feature**: 002-auth-integration
**Date**: 2026-01-16

## Overview

本文档定义了前端TypeScript类型与后端Python/Pydantic类型之间的映射关系,确保前后端数据契约一致。

---

## API Request Types

### 1. LoginRequest

**Backend (Python/Pydantic)**:
```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=255)
    remember_me: bool = False
```

**Frontend (TypeScript/Zod)**:
```typescript
const loginSchema = z.object({
  email: z.string().email('请输入有效的邮箱地址'),
  password: z.string().min(1, '请输入密码').max(255),
  remember_me: z.boolean().default(false),
})

type LoginRequest = z.infer<typeof loginSchema>
```

---

### 2. RegisterRequest

**Backend**:
```python
class RegisterRequest(BaseModel):
    email: EmailStr
    verification_code: str = Field(min_length=4, max_length=10)
    password: str = Field(min_length=8, max_length=128)
    name: Optional[str] = Field(None, max_length=100)
```

**Frontend**:
```typescript
const registerSchema = z.object({
  email: z.string().email('请输入有效的邮箱地址'),
  verification_code: z.string().length(6, '验证码必须为6位数字'),
  password: z.string()
    .min(8, '密码至少8个字符')
    .max(128, '密码最多128个字符')
    .regex(/[A-Z]/, '密码必须包含大写字母')
    .regex(/[a-z]/, '密码必须包含小写字母')
    .regex(/[0-9]/, '密码必须包含数字')
    .regex(/[!@#$%^&*]/, '密码必须包含特殊字符'),
  name: z.string().max(100).optional(),
})

type RegisterRequest = z.infer<typeof registerSchema>
```

---

### 3. ResetPasswordRequest

**Backend**:
```python
class ResetPasswordRequest(BaseModel):
    token: Optional[str] = None
    code: Optional[str] = None
    new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_token_or_code(self):
        if not self.token and not self.code:
            raise ValueError("Either 'token' or 'code' must be provided")
        return self
```

**Frontend**:
```typescript
const resetPasswordSchema = z.object({
  token: z.string().optional(),
  code: z.string().length(6).optional(),
  new_password: z.string()
    .min(8, '密码至少8个字符')
    .max(128, '密码最多128个字符')
    .regex(/[A-Z]/, '密码必须包含大写字母')
    .regex(/[a-z]/, '密码必须包含小写字母')
    .regex(/[0-9]/, '密码必须包含数字')
    .regex(/[!@#$%^&*]/, '密码必须包含特殊字符'),
}).refine(data => data.token || data.code, {
  message: '必须提供重置令牌或验证码',
})

type ResetPasswordRequest = z.infer<typeof resetPasswordSchema>
```

---

## API Response Types

### 1. UserResponse

**Backend**:
```python
class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    is_active: bool
    is_verified: bool
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None
```

**Frontend**:
```typescript
interface UserResponse {
  id: string
  email: string
  name: string
  is_active: boolean
  is_verified: boolean
  created_at: string | null
  last_login_at: string | null
}

// Zod schema for validation
const userResponseSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string(),
  is_active: z.boolean(),
  is_verified: z.boolean(),
  created_at: z.string().nullable(),
  last_login_at: z.string().nullable(),
})
```

---

### 2. LoginResponse

**Backend**:
```python
class LoginResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    user: Optional[UserResponse] = None
    redirect_to: Optional[str] = None
```

**Frontend**:
```typescript
interface LoginResponse {
  success: boolean
  message?: string
  user?: UserResponse
  redirect_to?: string
}

const loginResponseSchema = z.object({
  success: z.boolean(),
  message: z.string().optional(),
  user: userResponseSchema.optional(),
  redirect_to: z.string().optional(),
})
```

---

### 3. AuthResponse

**Backend**:
```python
class AuthResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[dict] = None
```

**Frontend**:
```typescript
interface AuthResponse {
  success: boolean
  message?: string
  data?: Record<string, unknown>
}

const authResponseSchema = z.object({
  success: z.boolean(),
  message: z.string().optional(),
  data: z.record(z.unknown()).optional(),
})
```

---

### 4. ErrorResponse

**Backend**:
```python
class ErrorResponse(BaseModel):
    success: bool = False
    error: Optional[ErrorDetail] = None
    message: Optional[str] = None

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[list[str]] = None
```

**Frontend**:
```typescript
interface ErrorDetail {
  code: string
  message: string
  details?: string[]
}

interface ErrorResponse {
  success: false
  detail?: string | ErrorDetail
  message?: string
}

const errorDetailSchema = z.object({
  code: z.string(),
  message: z.string(),
  details: z.array(z.string()).optional(),
})

const errorResponseSchema = z.object({
  success: z.literal(false),
  detail: z.union([z.string(), errorDetailSchema]).optional(),
  message: z.string().optional(),
})
```

---

## Type Conversion Guidelines

### 1. Python → TypeScript 基本类型映射

| Python Type | TypeScript Type | Notes |
|-------------|----------------|-------|
| `str` | `string` | |
| `int` | `number` | |
| `float` | `number` | |
| `bool` | `boolean` | |
| `None` | `null` | |
| `Optional[T]` | `T \| null` 或 `T?` | 使用`?`表示可选属性 |
| `list[T]` | `T[]` | |
| `dict` | `Record<string, unknown>` | 或具体的对象类型 |
| `UUID` | `string` | 前端作为字符串处理 |
| `datetime` | `string` | ISO8601格式字符串 |
| `EmailStr` | `string` | 需通过Zod的`.email()`验证 |

### 2. Pydantic → Zod 验证器映射

| Pydantic Validator | Zod Validator | Example |
|-------------------|---------------|---------|
| `Field(min_length=n)` | `.min(n)` | `z.string().min(8)` |
| `Field(max_length=n)` | `.max(n)` | `z.string().max(255)` |
| `EmailStr` | `.email()` | `z.string().email()` |
| `@field_validator` | `.refine()` | `z.string().refine(...)` |
| `@model_validator` | `.refine()` | `z.object({...}).refine(...)` |
| `Optional[T]` | `.optional()` | `z.string().optional()` |
| `Field(default=x)` | `.default(x)` | `z.boolean().default(false)` |

---

## Frontend Client Implementation

### RealAuthClient (真实鉴权客户端)

**位置**: `Frontend/src/features/auth/api/authReal.ts`

```typescript
import { BaseApiClient } from '@/shared/lib/apiClient'
import {
  LoginRequest,
  RegisterRequest,
  SendVerificationCodeRequest,
  ForgotPasswordRequest,
  ResetPasswordRequest,
  LoginResponse,
  AuthResponse,
  UserResponse,
} from './authTypes'

export class RealAuthClient extends BaseApiClient {
  constructor() {
    super('/auth')
  }

  async login(data: LoginRequest): Promise<LoginResponse> {
    return this.post<LoginResponse>('/login', data)
  }

  async logout(): Promise<AuthResponse> {
    return this.post<AuthResponse>('/logout')
  }

  async register(data: RegisterRequest): Promise<AuthResponse> {
    return this.post<AuthResponse>('/register', data)
  }

  async sendVerificationCode(data: SendVerificationCodeRequest): Promise<AuthResponse> {
    return this.post<AuthResponse>('/send-verification-code', data)
  }

  async forgotPassword(data: ForgotPasswordRequest): Promise<AuthResponse> {
    return this.post<AuthResponse>('/forgot-password', data)
  }

  async resetPassword(data: ResetPasswordRequest): Promise<AuthResponse> {
    return this.post<AuthResponse>('/reset-password', data)
  }

  async getCurrentUser(): Promise<UserResponse> {
    return this.get<UserResponse>('/me')
  }

  async changePassword(current_password: string, new_password: string): Promise<AuthResponse> {
    return this.post<AuthResponse>('/change-password', {
      current_password,
      new_password,
    })
  }
}
```

---

## Error Handling Pattern

### Backend Error Format

```python
# 方式1: 简单字符串错误
raise HTTPException(
    status_code=400,
    detail="验证码错误"
)

# 方式2: 结构化错误对象
raise HTTPException(
    status_code=400,
    detail={
        "code": "INVALID_CODE",
        "message": "验证码错误或已过期",
    }
)

# 方式3: 带详细信息的错误
raise HTTPException(
    status_code=400,
    detail={
        "code": "WEAK_PASSWORD",
        "message": "密码强度不足",
        "details": ["至少8个字符", "包含大写字母", "包含数字"]
    }
)
```

### Frontend Error Handling

```typescript
try {
  const response = await authClient.login(credentials)
  // 成功处理
} catch (error) {
  if (error instanceof ApiError) {
    // 后端返回的结构化错误
    const { status, detail } = error

    if (status === 401) {
      // 未授权错误
      showError('邮箱或密码错误')
    } else if (status === 429) {
      // 速率限制
      showError('请求过于频繁,请稍后再试')
    } else if (typeof detail === 'object' && detail.code) {
      // 结构化错误
      showError(detail.message)
      if (detail.details) {
        // 显示详细错误列表
        showDetailedErrors(detail.details)
      }
    } else {
      // 字符串错误
      showError(String(detail))
    }
  } else {
    // 网络错误或其他异常
    showError('网络错误,请稍后重试')
  }
}
```

---

## Validation Strategy

### Frontend Validation (前端验证)

**目的**: 提供即时反馈,改善用户体验

**时机**:
- 表单字段失焦时(onChange)
- 表单提交前(onSubmit)

**工具**: React Hook Form + Zod

**示例**:
```typescript
const { register, handleSubmit, formState: { errors } } = useForm({
  resolver: zodResolver(loginSchema),
})

const onSubmit = async (data: LoginRequest) => {
  // 提交前已经通过Zod验证
  await authClient.login(data)
}
```

---

### Backend Validation (后端验证)

**目的**: 安全防护,防止绕过前端验证

**时机**:
- 所有API请求入口

**工具**: Pydantic

**示例**:
```python
@router.post("/login")
async def login(credentials: LoginRequest):  # Pydantic自动验证
    # 如果验证失败,自动返回422错误
    ...
```

---

## Testing Type Safety

### Frontend Type Checking

```bash
# TypeScript类型检查
npm run type-check

# 或在构建时检查
npm run build
```

### API Contract Testing

```typescript
// 使用Zod验证API响应格式
const response = await authClient.login(credentials)
const validatedResponse = loginResponseSchema.parse(response)
// 如果格式不匹配,抛出ZodError
```

---

**文档版本**: 1.0.0
**最后更新**: 2026-01-16

# API 接口规范

## 目的
建立统一的API设计规范，确保接口的一致性、可维护性和良好的开发者体验，涵盖RESTful设计、版本控制、错误处理等关键方面。

## 适用范围
- **强制**: Backend (FastAPI) - 所有API接口
- **验证**: API文档生成时必须遵循，代码审查时检查

## 核心原则

### MUST - 强制规则
1. **RESTful设计**: 遵循RESTful API设计原则
2. **版本控制**: 使用URL路径版本控制 (/v1/)
3. **统一响应格式**: 所有接口使用统一的响应结构
4. **错误处理**: 使用标准化的错误响应格式
5. **认证授权**: 所有接口都需要适当的认证和授权
6. **幂等性**: 支持幂等操作的接口必须实现幂等性

### SHOULD - 建议规则
1. 使用OpenAPI规范编写API文档
2. 实施合理的限流策略
3. 添加请求/响应压缩
4. 使用缓存头优化性能

## URL设计规范

### 基础URL结构
```
/api/v1/{resource}/{resource_id}/{sub_resource}
```

### 资源命名
```http
# 正确示例
GET    /api/v1/users              # 获取用户列表
POST   /api/v1/users              # 创建用户
GET    /api/v1/users/{id}         # 获取单个用户
PUT    /api/v1/users/{id}         # 更新用户
DELETE /api/v1/users/{id}         # 删除用户

GET    /api/v1/users/{id}/posts   # 获取用户的文章
POST   /api/v1/users/{id}/posts   # 为用户创建文章

# 错误示例
GET    /api/v1/getUsers           # 动词不应出现在URL中
POST   /api/v1/createUser         # 动词不应出现在URL中
GET    /api/v1/userList           # 不符合RESTful命名
```

### 查询参数命名
```http
# 分页参数
GET /api/v1/posts?page=1&page_size=20

# 排序参数
GET /api/v1/posts?sort=created_at&order=desc

# 过滤参数
GET /api/v1/posts?status=published&category=tech

# 搜索参数
GET /api/v1/posts?search=python&search_fields=title,content
```

## 版本控制策略

### URL路径版本控制
```http
# 版本控制示例
/api/v1/users              # v1版本
/api/v2/users              # v2版本（向后兼容）

# 版本号规则
- 主版本号变更表示不兼容的API变更
- 次版本号用于向后兼容的功能增加
- 补丁版本用于向后兼容的缺陷修复
```

### 版本兼容性
```python
# FastAPI版本控制示例
from fastapi import FastAPI, APIRouter

app = FastAPI(title="Noveris AI API", version="1.0.0")

# v1 API路由
v1_router = APIRouter(prefix="/api/v1")
app.include_router(v1_router)

# v2 API路由（未来扩展）
v2_router = APIRouter(prefix="/api/v2")
app.include_router(v2_router)
```

## 统一响应格式

### 成功响应格式
```json
{
  "success": true,
  "data": {
    "id": 123,
    "name": "示例数据",
    "created_at": "2024-01-01T10:00:00Z"
  },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2024-01-01T10:00:00Z"
  }
}
```

### 列表响应格式
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "title": "文章1",
      "author": "作者1"
    },
    {
      "id": 2,
      "title": "文章2",
      "author": "作者2"
    }
  ],
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2024-01-01T10:00:00Z",
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 150,
      "total_pages": 8
    }
  }
}
```

### 分页规范
```python
from pydantic import BaseModel
from typing import List, Optional

class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int

class PaginatedResponse(BaseModel):
    success: bool = True
    data: List[dict]
    meta: dict
    pagination: Optional[PaginationMeta]
```

## 错误处理规范

### 错误响应格式
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数验证失败",
    "details": [
      {
        "field": "email",
        "message": "邮箱格式不正确"
      }
    ]
  },
  "meta": {
    "request_id": "req_abc123",
    "timestamp": "2024-01-01T10:00:00Z"
  }
}
```

### HTTP状态码使用
```http
# 成功状态码
200 OK           # 请求成功
201 Created      # 资源创建成功
204 No Content   # 删除成功，无返回内容

# 客户端错误
400 Bad Request       # 请求参数错误
401 Unauthorized      # 未认证
403 Forbidden         # 权限不足
404 Not Found         # 资源不存在
409 Conflict          # 资源冲突
422 Unprocessable Entity  # 验证错误
429 Too Many Requests     # 请求过于频繁

# 服务器错误
500 Internal Server Error  # 服务器内部错误
502 Bad Gateway           # 网关错误
503 Service Unavailable   # 服务不可用
```

### 错误码规范
```python
# 错误码常量定义
class ErrorCode:
    # 通用错误
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"

    # 业务错误
    USER_NOT_FOUND = "USER_NOT_FOUND"
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"

# 错误响应示例
def create_error_response(error_code: str, message: str, details: list = None) -> dict:
    return {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or []
        },
        "meta": {
            "request_id": get_request_id(),
            "timestamp": get_current_timestamp()
        }
    }
```

## 认证授权规范

### Session + Cookie 认证
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPBasicCredentials
import redis

# Session管理
class SessionManager:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def create_session(self, user_id: int, user_data: dict) -> str:
        session_id = generate_session_id()
        session_data = {
            "user_id": user_id,
            "user_data": user_data,
            "created_at": get_current_timestamp(),
            "expires_at": get_expiration_time()
        }
        self.redis.setex(f"session:{session_id}", SESSION_TTL, json.dumps(session_data))
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        session_data = self.redis.get(f"session:{session_id}")
        return json.loads(session_data) if session_data else None

# 依赖注入
async def get_current_user(session_id: str = Depends(get_session_from_cookie)) -> User:
    session_manager = get_session_manager()
    session_data = session_manager.get_session(session_id)

    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid"
        )

    user = await get_user_by_id(session_data["user_id"])
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    return user
```

### Cookie 设置
```python
from fastapi.responses import JSONResponse

def create_login_response(user: User, session_id: str) -> JSONResponse:
    response = JSONResponse({
        "success": True,
        "data": {
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name
            }
        }
    })

    # 设置安全Cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,      # 防止XSS攻击
        secure=True,         # 仅HTTPS传输
        samesite="strict",   # 防止CSRF攻击
        max_age=SESSION_TTL,
        path="/"
    )

    return response
```

## 幂等性设计

### Idempotency-Key 实现
```python
import hashlib
from fastapi import Request, HTTPException

class IdempotencyManager:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def check_idempotency(self, idempotency_key: str, ttl: int = 3600) -> bool:
        """检查幂等性key是否已存在"""
        key = f"idempotency:{hashlib.sha256(idempotency_key.encode()).hexdigest()}"
        return bool(self.redis.set(key, "1", ex=ttl, nx=True))

    def get_cached_result(self, idempotency_key: str) -> Optional[dict]:
        """获取缓存的执行结果"""
        key = f"idempotency:{hashlib.sha256(idempotency_key.encode()).hexdigest()}"
        result = self.redis.get(f"{key}:result")
        return json.loads(result) if result else None

    def cache_result(self, idempotency_key: str, result: dict, ttl: int = 3600):
        """缓存执行结果"""
        key = f"idempotency:{hashlib.sha256(idempotency_key.encode()).hexdigest()}"
        self.redis.setex(f"{key}:result", ttl, json.dumps(result))

# API端点示例
@app.post("/api/v1/payments")
async def create_payment(
    payment_data: PaymentCreate,
    request: Request,
    idempotency_key: str = Header(None, alias="Idempotency-Key")
):
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header is required for this operation"
        )

    idempotency_manager = get_idempotency_manager()

    # 检查是否已处理过
    cached_result = idempotency_manager.get_cached_result(idempotency_key)
    if cached_result:
        return cached_result

    # 检查是否正在处理
    if not idempotency_manager.check_idempotency(idempotency_key):
        raise HTTPException(
            status_code=409,
            detail="Request is being processed, please retry later"
        )

    try:
        # 执行支付逻辑
        payment = await process_payment(payment_data)

        result = {
            "success": True,
            "data": {
                "payment_id": payment.id,
                "status": payment.status,
                "amount": payment.amount
            }
        }

        # 缓存结果
        idempotency_manager.cache_result(idempotency_key, result)

        return result

    except Exception as e:
        # 处理失败时清除幂等性key
        # 允许重试
        raise HTTPException(status_code=500, detail="Payment processing failed")
```

## 分页和排序

### 标准分页实现
```python
from sqlalchemy import desc, asc
from typing import Literal

class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort: Optional[str] = None
    order: Literal["asc", "desc"] = "desc"

def apply_pagination_sorting(query, params: PaginationParams, model_class):
    # 应用排序
    if params.sort:
        column = getattr(model_class, params.sort, None)
        if column is not None:
            if params.order == "desc":
                query = query.order_by(desc(column))
            else:
                query = query.order_by(asc(column))

    # 应用分页
    offset = (params.page - 1) * params.page_size
    query = query.offset(offset).limit(params.page_size)

    return query

@app.get("/api/v1/posts")
async def get_posts(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user)
):
    query = select(Post).where(Post.tenant_id == current_user.tenant_id)

    # 应用分页和排序
    query = apply_pagination_sorting(query, pagination, Post)

    posts = await session.execute(query)
    posts_list = posts.scalars().all()

    # 计算总数
    total_query = select(func.count(Post.id)).where(Post.tenant_id == current_user.tenant_id)
    total_result = await session.execute(total_query)
    total = total_result.scalar()

    return {
        "success": True,
        "data": [post.to_dict() for post in posts_list],
        "pagination": {
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total": total,
            "total_pages": (total + pagination.page_size - 1) // pagination.page_size
        }
    }
```

## OpenAPI文档规范

### FastAPI OpenAPI配置
```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="Noveris AI API",
    version="1.0.0",
    description="企业级AI应用API",
    contact={
        "name": "Noveris AI Team",
        "email": "api@noveris.ai",
    },
    license_info={
        "name": "MIT",
    },
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # 添加安全方案
    openapi_schema["components"]["securitySchemes"] = {
        "sessionAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": "session_id"
        }
    }

    # 设置全局安全要求
    openapi_schema["security"] = [{"sessionAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

## 检查清单

### API设计检查
- [ ] 使用RESTful URL命名规范
- [ ] 实现了版本控制 (/api/v1/)
- [ ] 使用统一的响应格式
- [ ] 实现了标准化的错误处理
- [ ] 所有接口都有适当的认证授权

### 安全性检查
- [ ] 使用Session + Cookie认证
- [ ] Cookie设置了安全标志 (httponly, secure, samesite)
- [ ] 实现了适当的权限控制
- [ ] 敏感操作实现了幂等性

### 文档检查
- [ ] 提供了完整的OpenAPI文档
- [ ] 所有接口都有详细说明
- [ ] 包含请求/响应示例
- [ ] 错误码有清晰定义

### 性能检查
- [ ] 实现了合理的分页
- [ ] 支持排序功能
- [ ] 大数据量查询有优化
- [ ] 添加了适当的缓存头

## 示例代码

### 完整的API端点示例
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

router = APIRouter()

@router.get("/users", response_model=PaginatedResponse[UserResponse])
async def get_users(
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """获取用户列表"""
    try:
        # 检查权限
        if not current_user.has_permission("users.read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )

        # 构建查询
        query = select(User).where(User.tenant_id == current_user.tenant_id)

        # 应用分页和排序
        query = apply_pagination_sorting(query, pagination, User)

        # 执行查询
        result = await session.execute(query)
        users = result.scalars().all()

        # 计算总数
        total_query = select(func.count(User.id)).where(User.tenant_id == current_user.tenant_id)
        total_result = await session.execute(total_query)
        total = total_result.scalar()

        return {
            "success": True,
            "data": [user.to_dict() for user in users],
            "pagination": {
                "page": pagination.page,
                "page_size": pagination.page_size,
                "total": total,
                "total_pages": (total + pagination.page_size - 1) // pagination.page_size
            }
        }

    except Exception as e:
        logger.error(f"Failed to get users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )
```

## 相关文档
- [配置规范](10-Config-Standard.md) - API配置管理
- [数据库规范](20-Database-Standard.md) - 数据查询设计
- [安全规范](60-Security-Standard.md) - API安全保护
- [性能规范](70-Performance-Standard.md) - API性能优化

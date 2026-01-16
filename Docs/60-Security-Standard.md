# 安全规范

## 目的
建立全面的安全规范，确保应用系统在设计、开发、部署和运维各个阶段的安全性，保护用户数据和系统完整性。

## 适用范围
- **强制**: Backend (Python+FastAPI), Frontend (React) - 所有安全相关功能
- **验证**: 安全扫描工具自动检查，代码审查时重点审查

## 核心原则

### MUST - 强制规则
1. **Session + Cookie认证**: 使用Session管理认证状态，不使用JWT
2. **密码安全**: 实施强密码策略和安全的密码哈希
3. **输入验证**: 所有输入数据必须经过验证和清理
4. **HTTPS优先**: 生产环境必须使用HTTPS传输
5. **最小权限**: 遵循最小权限原则，限制访问范围
6. **日志安全**: 敏感信息脱敏，避免日志泄露

### SHOULD - 建议规则
1. 实施多因素认证
2. 使用安全头保护Web应用
3. 定期进行安全审计和渗透测试
4. 实施零信任架构

## 身份认证与会话管理

### Session + Cookie认证实现
```python
from fastapi import Depends, HTTPException, status, Response
from fastapi.security import HTTPBearer
import redis
import secrets
from datetime import datetime, timedelta
import json

class SessionManager:
    def __init__(self, redis_client: redis.Redis, session_ttl: int = 3600):
        self.redis = redis_client
        self.session_ttl = session_ttl

    def create_session(self, user_id: int, user_data: dict) -> str:
        """创建新会话"""
        session_id = secrets.token_urlsafe(32)

        session_data = {
            "user_id": user_id,
            "user_data": user_data,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(seconds=self.session_ttl)).isoformat(),
            "ip_address": None,  # 将在后续设置
            "user_agent": None   # 将在后续设置
        }

        # 存储会话数据
        self.redis.setex(
            f"session:{session_id}",
            self.session_ttl,
            json.dumps(session_data)
        )

        return session_id

    def get_session(self, session_id: str, client_ip: str = None, user_agent: str = None) -> dict:
        """获取会话数据"""
        session_data = self.redis.get(f"session:{session_id}")
        if not session_data:
            return None

        session = json.loads(session_data)

        # 检查会话是否过期
        if datetime.fromisoformat(session["expires_at"]) < datetime.utcnow():
            self.destroy_session(session_id)
            return None

        # 可选：检查IP地址和User-Agent是否一致（防止会话劫持）
        if client_ip and session.get("ip_address") and session["ip_address"] != client_ip:
            self.destroy_session(session_id)
            return None

        if user_agent and session.get("user_agent") and session["user_agent"] != user_agent:
            self.destroy_session(session_id)
            return None

        return session

    def update_session(self, session_id: str, updates: dict):
        """更新会话数据"""
        session_data = self.redis.get(f"session:{session_id}")
        if not session_data:
            return False

        session = json.loads(session_data)
        session.update(updates)

        self.redis.setex(
            f"session:{session_id}",
            self.session_ttl,
            json.dumps(session)
        )

        return True

    def destroy_session(self, session_id: str):
        """销毁会话"""
        self.redis.delete(f"session:{session_id}")

    def extend_session(self, session_id: str):
        """延长会话时间"""
        session_data = self.redis.get(f"session:{session_id}")
        if not session_data:
            return False

        session = json.loads(session_data)
        session["expires_at"] = (datetime.utcnow() + timedelta(seconds=self.session_ttl)).isoformat()

        self.redis.setex(
            f"session:{session_id}",
            self.session_ttl,
            json.dumps(session)
        )

        return True

# FastAPI依赖注入
async def get_current_user(
    request: Request,
    response: Response
) -> User:
    """获取当前登录用户"""
    session_id = request.cookies.get("session_id")

    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    session_manager = request.app.state.session_manager
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent")

    session = session_manager.get_session(session_id, client_ip, user_agent)

    if not session:
        # 清除无效的cookie
        response.delete_cookie("session_id")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid"
        )

    # 延长会话时间
    session_manager.extend_session(session_id)

    # 获取用户数据
    user = await get_user_by_id(session["user_id"])
    if not user or not user.is_active:
        session_manager.destroy_session(session_id)
        response.delete_cookie("session_id")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    return user

# 登录接口
@app.post("/api/v1/auth/login")
async def login(
    credentials: LoginRequest,
    request: Request,
    response: Response
):
    # 验证用户凭据
    user = await authenticate_user(credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # 创建会话
    session_manager = request.app.state.session_manager
    session_id = session_manager.create_session(
        user.id,
        {
            "email": user.email,
            "name": user.name,
            "role": user.role
        }
    )

    # 设置会话Cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,      # 防止XSS攻击
        secure=True,         # 仅HTTPS传输（生产环境）
        samesite="strict",   # 防止CSRF攻击
        max_age=3600,        # 1小时
        path="/"
    )

    # 更新会话中的IP和User-Agent
    session_manager.update_session(session_id, {
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent")
    })

    return {"message": "Login successful"}

# 登出接口
@app.post("/api/v1/auth/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user)
):
    session_id = request.cookies.get("session_id")
    if session_id:
        session_manager = request.app.state.session_manager
        session_manager.destroy_session(session_id)

    response.delete_cookie("session_id")
    return {"message": "Logout successful"}
```

### 密码安全策略
```python
import bcrypt
import secrets
import string
from pydantic import BaseModel, validator

class PasswordPolicy:
    MIN_LENGTH = 12
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL = True

    @staticmethod
    def validate_password(password: str) -> bool:
        """验证密码强度"""
        if len(password) < PasswordPolicy.MIN_LENGTH:
            return False
        if len(password) > PasswordPolicy.MAX_LENGTH:
            return False

        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)

        if PasswordPolicy.REQUIRE_UPPERCASE and not has_upper:
            return False
        if PasswordPolicy.REQUIRE_LOWERCASE and not has_lower:
            return False
        if PasswordPolicy.REQUIRE_DIGITS and not has_digit:
            return False
        if PasswordPolicy.REQUIRE_SPECIAL and not has_special:
            return False

        return True

    @staticmethod
    def hash_password(password: str) -> str:
        """哈希密码"""
        salt = bcrypt.gensalt(rounds=12)  # 使用12轮，增加计算成本
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    @staticmethod
    def generate_temp_password(length: int = 16) -> str:
        """生成临时密码"""
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(chars) for _ in range(length))

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

    @validator('new_password')
    def validate_new_password(cls, v):
        if not PasswordPolicy.validate_password(v):
            raise ValueError(
                "Password must be 12-128 characters long and contain "
                "at least one uppercase letter, one lowercase letter, "
                "one digit, and one special character"
            )
        return v

# 密码变更接口
@app.put("/api/v1/auth/password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user)
):
    # 验证当前密码
    if not PasswordPolicy.verify_password(
        request.current_password,
        current_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # 更新密码
    new_hash = PasswordPolicy.hash_password(request.new_password)
    await update_user_password(current_user.id, new_hash)

    # 记录密码变更日志
    await log_security_event(
        "password_changed",
        current_user.id,
        {"ip": get_client_ip(), "user_agent": get_user_agent()}
    )

    return {"message": "Password changed successfully"}
```

## 输入验证与防护

### 请求数据验证
```python
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
import re

class UserCreateRequest(BaseModel):
    email: EmailStr
    name: str
    password: str

    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Name cannot be empty')
        if len(v) > 100:
            raise ValueError('Name too long')
        # 只允许字母、数字、空格和基本标点
        if not re.match(r'^[a-zA-Z0-9\s\-_.]+$', v):
            raise ValueError('Name contains invalid characters')
        return v.strip()

    @validator('password')
    def validate_password(cls, v):
        if not PasswordPolicy.validate_password(v):
            raise ValueError('Password does not meet security requirements')
        return v

class PostCreateRequest(BaseModel):
    title: str
    content: str
    tags: Optional[list[str]] = []

    @validator('title')
    def validate_title(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Title cannot be empty')
        if len(v) > 200:
            raise ValueError('Title too long')
        return v.strip()

    @validator('content')
    def validate_content(cls, v):
        if len(v) > 50000:  # 限制内容长度
            raise ValueError('Content too long')
        return v

    @validator('tags')
    def validate_tags(cls, v):
        if len(v) > 10:
            raise ValueError('Too many tags')
        for tag in v:
            if len(tag) > 50:
                raise ValueError('Tag too long')
            if not re.match(r'^[a-zA-Z0-9\-_]+$', tag):
                raise ValueError('Tag contains invalid characters')
        return v

# 防止SQL注入 - 使用参数化查询
async def create_post(post_data: PostCreateRequest, user_id: int):
    query = """
        INSERT INTO posts (title, content, user_id, created_at)
        VALUES ($1, $2, $3, NOW())
        RETURNING id
    """
    # SQLAlchemy会自动处理参数化
    result = await session.execute(
        query,
        (post_data.title, post_data.content, user_id)
    )
    return result.fetchone()[0]
```

### XSS防护
```python
from fastapi import Request, Response
from fastapi.responses import HTMLResponse
import bleach

class XSSProtection:
    @staticmethod
    def sanitize_html(content: str) -> str:
        """清理HTML内容，防止XSS"""
        allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3',
            'ul', 'ol', 'li', 'blockquote', 'code', 'pre'
        ]
        allowed_attrs = {
            '*': ['class'],
            'a': ['href', 'rel'],
            'img': ['src', 'alt', 'width', 'height']
        }

        return bleach.clean(
            content,
            tags=allowed_tags,
            attributes=allowed_attrs,
            strip=True
        )

    @staticmethod
    def sanitize_text(text: str) -> str:
        """清理纯文本内容"""
        # 转义HTML特殊字符
        return bleach.clean(text, tags=[], strip=True)

# 前端XSS防护 - React组件
import DOMPurify from 'dompurify';

const SafeHtml = ({ html }) => {
  const sanitizedHtml = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'ul', 'ol', 'li'],
    ALLOWED_ATTRS: ['class']
  });

  return <div dangerouslySetInnerHTML={{ __html: sanitizedHtml }} />;
};
```

### CSRF防护
```python
import secrets
from fastapi import Request, HTTPException, status

class CSRFProtection:
    @staticmethod
    def generate_token() -> str:
        """生成CSRF token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    async def validate_csrf_token(
        request: Request,
        token: str = None
    ):
        """验证CSRF token"""
        # 从header或表单中获取token
        if not token:
            token = request.headers.get("X-CSRF-Token")

        if not token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing"
            )

        # 从session中获取预期的token
        session = request.session
        expected_token = session.get("csrf_token")

        if not expected_token or token != expected_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token invalid"
            )

# FastAPI中间件
from fastapi.middleware.base import BaseHTTPMiddleware

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 对于非GET请求，验证CSRF token
        if request.method not in ["GET", "HEAD", "OPTIONS"]:
            await CSRFProtection.validate_csrf_token(request)

        response = await call_next(request)
        return response

# 前端CSRF处理
const getCsrfToken = () => {
  return document.cookie
    .split('; ')
    .find(row => row.startsWith('csrf_token='))
    ?.split('=')[1];
};

const apiRequest = async (url, options = {}) => {
  const csrfToken = getCsrfToken();

  return fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'X-CSRF-Token': csrfToken,
      'Content-Type': 'application/json',
    },
  });
};
```

## 文件上传安全

### 文件上传验证
```python
from fastapi import UploadFile, HTTPException
import magic
import os

class FileUploadSecurity:
    ALLOWED_MIME_TYPES = {
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'image/gif': ['.gif'],
        'application/pdf': ['.pdf'],
        'text/plain': ['.txt'],
    }

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    @staticmethod
    def validate_file(file: UploadFile) -> bool:
        """验证上传文件"""
        # 检查文件大小
        if file.size > FileUploadSecurity.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail="File too large"
            )

        # 检查MIME类型
        mime_type = magic.from_buffer(file.file.read(1024), mime=True)
        file.file.seek(0)  # 重置文件指针

        if mime_type not in FileUploadSecurity.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail="File type not allowed"
            )

        # 检查文件扩展名
        filename = file.filename.lower()
        allowed_extensions = FileUploadSecurity.ALLOWED_MIME_TYPES[mime_type]

        if not any(filename.endswith(ext) for ext in allowed_extensions):
            raise HTTPException(
                status_code=400,
                detail="File extension not allowed"
            )

        return True

    @staticmethod
    def generate_safe_filename(original_filename: str) -> str:
        """生成安全的文件名"""
        import uuid
        import os

        # 获取文件扩展名
        _, ext = os.path.splitext(original_filename)

        # 生成随机文件名
        safe_name = f"{uuid.uuid4().hex}{ext.lower()}"

        return safe_name

# 文件上传接口
@app.post("/api/v1/upload")
async def upload_file(file: UploadFile):
    # 验证文件
    FileUploadSecurity.validate_file(file)

    # 生成安全文件名
    safe_filename = FileUploadSecurity.generate_safe_filename(file.filename)

    # 保存文件
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"filename": safe_filename, "url": f"/uploads/{safe_filename}"}
```

## HTTPS与传输安全

### HTTPS配置
```python
# FastAPI HTTPS配置
from fastapi import FastAPI
import uvicorn

app = FastAPI()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=443,
        ssl_keyfile="/path/to/private.key",
        ssl_certfile="/path/to/certificate.crt",
        ssl_version=ssl.PROTOCOL_TLSv1_2
    )

# Nginx HTTPS配置示例
server {
    listen 443 ssl http2;
    server_name api.noveris.ai;

    ssl_certificate /etc/ssl/certs/noveris.crt;
    ssl_certificate_key /etc/ssl/private/noveris.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 安全头配置
```python
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# HTTPS重定向中间件
app.add_middleware(HTTPSRedirectMiddleware)

# 受信任主机中间件
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["api.noveris.ai", "*.noveris.ai"]
)

# 自定义安全头中间件
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 防止点击劫持
        response.headers["X-Frame-Options"] = "DENY"

        # 防止MIME类型混淆
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 启用XSS过滤
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # 引用策略
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 内容安全策略
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'"
        )

        return response

app.add_middleware(SecurityHeadersMiddleware)
```

## 数据脱敏与隐私保护

### 日志脱敏
```python
import re
import logging
from typing import Dict, Any

class LogSanitizer:
    SENSITIVE_PATTERNS = [
        (re.compile(r'("password":\s*)"[^"]*"'), r'\1"[REDACTED]"'),
        (re.compile(r'("token":\s*)"[^"]*"'), r'\1"[REDACTED]"'),
        (re.compile(r'("session_id":\s*)"[^"]*"'), r'\1"[REDACTED]"'),
        (re.compile(r'("email":\s*)"[^"]*"'), r'\1"[REDACTED]"'),
        (re.compile(r'(\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b)'), r'[REDACTED_CARD]'),
    ]

    @staticmethod
    def sanitize_message(message: str) -> str:
        """清理日志消息中的敏感信息"""
        for pattern, replacement in LogSanitizer.SENSITIVE_PATTERNS:
            message = pattern.sub(replacement, message)
        return message

    @staticmethod
    def sanitize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """清理数据字典中的敏感信息"""
        sanitized = data.copy()

        sensitive_keys = ['password', 'token', 'session_id', 'credit_card', 'ssn']
        for key in sensitive_keys:
            if key in sanitized:
                sanitized[key] = '[REDACTED]'

        return sanitized

# 自定义日志处理器
class SanitizedLogger(logging.Logger):
    def _log(self, level, msg, args, exc_info=None, extra=None):
        if isinstance(msg, str):
            msg = LogSanitizer.sanitize_message(msg)
        super()._log(level, msg, args, exc_info, extra)

# 使用示例
logger = SanitizedLogger(__name__)

# 日志敏感信息会被自动清理
logger.info("User login attempt: email='user@example.com', password='secret123'")
# 输出: User login attempt: email='[REDACTED]', password='[REDACTED]'
```

## 安全监控与响应

### 安全事件日志
```python
from enum import Enum
from datetime import datetime
import json

class SecurityEventType(Enum):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    PASSWORD_CHANGE = "password_change"
    SESSION_HIJACKING = "session_hijacking"
    BRUTE_FORCE = "brute_force"
    SQL_INJECTION = "sql_injection"
    XSS_ATTACK = "xss_attack"
    CSRF_ATTACK = "csrf_attack"

class SecurityLogger:
    @staticmethod
    async def log_event(
        event_type: SecurityEventType,
        user_id: int = None,
        details: dict = None,
        ip_address: str = None,
        user_agent: str = None
    ):
        """记录安全事件"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "details": details or {}
        }

        # 写入专门的安全日志
        with open("/var/log/noveris/security.log", "a") as f:
            f.write(json.dumps(event) + "\n")

        # 如果是严重事件，发送告警
        if event_type in [SecurityEventType.SESSION_HIJACKING, SecurityEventType.SQL_INJECTION]:
            await send_security_alert(event)

# 安全监控中间件
class SecurityMonitoringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = datetime.utcnow()

        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # 记录异常
            await SecurityLogger.log_event(
                SecurityEventType.SQL_INJECTION if "sql" in str(e).lower() else SecurityEventType.XSS_ATTACK,
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent"),
                details={"error": str(e), "path": request.url.path}
            )
            raise
        finally:
            # 记录可疑活动
            duration = (datetime.utcnow() - start_time).total_seconds()
            if duration > 30:  # 异常长的请求
                await SecurityLogger.log_event(
                    SecurityEventType.BRUTE_FORCE,
                    ip_address=request.client.host,
                    details={"duration": duration, "path": request.url.path}
                )
```

## 检查清单

### 认证安全检查
- [ ] 使用Session + Cookie认证而非JWT
- [ ] Cookie设置了安全标志 (httponly, secure, samesite)
- [ ] 实施密码强度策略和安全哈希
- [ ] 会话有适当的超时和清理机制

### 输入验证检查
- [ ] 所有用户输入都经过验证
- [ ] 使用参数化查询防止SQL注入
- [ ] 实施XSS防护和内容清理
- [ ] 文件上传有类型和大小限制

### 传输安全检查
- [ ] 生产环境强制使用HTTPS
- [ ] 配置适当的安全头
- [ ] 实施CSRF防护
- [ ] 敏感数据在传输中加密

### 监控检查
- [ ] 记录安全相关事件
- [ ] 实施失败登录检测
- [ ] 敏感信息在日志中脱敏
- [ ] 建立安全事件告警机制

## 示例安全配置

### 密码策略配置
```python
# config/security.py
SECURITY_CONFIG = {
    "password_policy": {
        "min_length": 12,
        "require_uppercase": True,
        "require_lowercase": True,
        "require_digits": True,
        "require_special": True,
        "max_attempts": 5,
        "lockout_duration": 900,  # 15分钟
    },
    "session": {
        "ttl": 3600,  # 1小时
        "extend_on_activity": True,
        "check_ip": True,
        "check_user_agent": True,
    },
    "rate_limiting": {
        "login_attempts": {"max": 5, "window": 900},
        "api_calls": {"max": 1000, "window": 3600},
    }
}
```

## 相关文档
- [配置规范](10-Config-Standard.md) - 安全配置管理
- [API规范](30-API-Standard.md) - 接口安全要求
- [部署规范](50-Deployment-Standard.md) - 安全部署配置
- [可观测性规范](80-Observability-Standard.md) - 安全监控要求

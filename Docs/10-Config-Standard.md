# 配置与环境变量规范

## 目的
建立统一的配置管理规范，确保所有环境差异、敏感信息、第三方服务配置通过环境变量注入，避免硬编码，实现环境无关的代码部署。

## 适用范围
- **强制**: Backend (Python+FastAPI), Frontend (React), Deploy, Scripts
- **验证**: 代码审查时必须检查无硬编码配置

## 核心原则

### MUST - 强制规则
1. **禁止硬编码**: 任何配置项不得在代码中写死
2. **环境变量优先**: 所有配置通过环境变量注入
3. **敏感信息隔离**: 密码、密钥、令牌等必须通过环境变量提供
4. **配置分层**: 默认值 < 配置文件 < 环境变量 < 启动参数
5. **命名规范**: 使用大写字母和下划线，带前缀分组

### SHOULD - 建议规则
1. 使用 `.env` 文件进行本地开发配置
2. 提供配置验证和类型检查
3. 记录所有配置项的用途和约束

## 配置分层与优先级

### 优先级顺序（从低到高）
1. **代码默认值** - 安全合理的默认配置
2. **配置文件** - `config.yaml` 或 `settings.json`
3. **环境变量** - 操作系统环境变量（最高优先级）
4. **启动参数** - 命令行参数覆盖（如果适用）

### 示例优先级实现（Python）
```python
import os
from typing import Optional

class Config:
    # 1. 默认值（最低优先级）
    APP_ENV: str = "development"
    APP_PORT: int = 8000

    # 2. 环境变量覆盖
    def __init__(self):
        self.APP_ENV = os.getenv("APP_ENV", self.APP_ENV)
        self.APP_PORT = int(os.getenv("APP_PORT", str(self.APP_PORT)))

config = Config()
```

## 命名约定

### 前缀分组规范
```
APP_     # 应用基础配置
DB_      # 数据库配置
REDIS_   # Redis缓存配置
MINIO_   # 对象存储配置
ES_      # Elasticsearch配置
AUTH_    # 认证授权配置
OBS_     # 可观测性配置
SEC_     # 安全配置
RATE_    # 限流配置
```

### 示例命名
```bash
# 应用基础
APP_ENV=production
APP_PORT=8000
APP_NAME=noveris-ai
APP_VERSION=v1.0.0

# 数据库
DB_HOST=localhost
DB_PORT=5432
DB_NAME=noveris_db
DB_USER=noveris_user
DB_PASSWORD=your_password_here

# Redis缓存
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# MinIO对象存储
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=minio_access_key
MINIO_SECRET_KEY=minio_secret_key
MINIO_BUCKET=noveris-bucket
```

## env-example-template.txt 结构要求

### 文件组织结构
```
# 头部说明
# 版本信息和更新时间

# 分组注释
# === APP 应用基础配置 ===
APP_ENV=development
APP_PORT=8000
# 注释说明用途、是否敏感、默认值规则

# === DB 数据库配置 ===
DB_HOST=localhost
# ... 其他配置
```

### 每个变量必须包含
1. **用途说明**: 变量的作用和使用场景
2. **敏感标记**: 是否包含敏感信息
3. **默认值规则**: 生产环境的推荐值或约束
4. **验证规则**: 类型、范围、格式要求

### 示例格式
```bash
# === APP 应用基础配置 ===

# 运行环境 (development/staging/production)
# 敏感: 否 | 默认值: development | 验证: 枚举值
APP_ENV=development

# 服务端口
# 敏感: 否 | 默认值: 8000 | 验证: 1-65535整数
APP_PORT=8000

# 数据库密码
# 敏感: 是 | 默认值: 无（必须设置） | 验证: 非空字符串
DB_PASSWORD=your_db_password_here
```

## 禁止硬编码清单

### 绝对禁止硬编码的项目
- [ ] 数据库连接信息（主机、端口、用户名、密码）
- [ ] Redis连接配置
- [ ] MinIO/S3访问凭证
- [ ] Elasticsearch集群地址
- [ ] JWT密钥、Session密钥
- [ ] OAuth客户端ID/Secret
- [ ] API密钥、访问令牌
- [ ] 第三方服务地址和端口
- [ ] 邮件服务器配置
- [ ] 外部API端点
- [ ] 证书文件路径
- [ ] 上传文件大小限制
- [ ] 分页默认大小
- [ ] 缓存过期时间
- [ ] 限流阈值

### 代码审查要点
```python
# ❌ 错误示例
DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
JWT_SECRET = "hardcoded-secret-key"
API_BASE_URL = "https://api.example.com"

# ✅ 正确示例
DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-key")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
```

## 环境配置差异策略

### 开发环境配置
- 使用本地服务（localhost）
- 使用测试数据和凭证
- 启用调试模式和详细日志
- 允许不安全的默认值

### 测试环境配置
- 使用独立的服务实例
- 使用测试数据和模拟服务
- 禁用外部API调用
- 启用完整的日志记录

### 生产环境配置
- 使用生产服务地址
- 启用所有安全措施
- 配置监控和告警
- 优化性能参数

### 配置差异示例
```bash
# 开发环境
APP_ENV=development
APP_DEBUG=true
DB_HOST=localhost
LOG_LEVEL=DEBUG
CACHE_TTL=300

# 生产环境
APP_ENV=production
APP_DEBUG=false
DB_HOST=db.production.internal
LOG_LEVEL=INFO
CACHE_TTL=3600
```

## 配置验证与类型转换

### Python配置类示例
```python
from pydantic import BaseSettings, Field
from typing import Optional

class AppConfig(BaseSettings):
    # 应用配置
    app_env: str = Field(default="development", env="APP_ENV")
    app_port: int = Field(default=8000, env="APP_PORT", ge=1, le=65535)
    app_name: str = Field(default="noveris-ai", env="APP_NAME")

    # 数据库配置
    db_host: str = Field(default="localhost", env="DB_HOST")
    db_port: int = Field(default=5432, env="DB_PORT", ge=1, le=65535)
    db_name: str = Field(default="noveris_db", env="DB_NAME")
    db_user: str = Field(default="noveris_user", env="DB_USER")
    db_password: str = Field(..., env="DB_PASSWORD")  # 必需字段

    class Config:
        env_file = ".env"
        case_sensitive = False

config = AppConfig()
```

### 前端配置示例（TypeScript）
```typescript
interface Config {
  apiBaseUrl: string;
  environment: string;
  features: {
    analytics: boolean;
    notifications: boolean;
  };
}

const config: Config = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  environment: import.meta.env.VITE_APP_ENV || 'development',
  features: {
    analytics: import.meta.env.VITE_ENABLE_ANALYTICS === 'true',
    notifications: import.meta.env.VITE_ENABLE_NOTIFICATIONS === 'true',
  },
};

export default config;
```

## 检查清单

### 配置设计检查
- [ ] 所有配置项都有环境变量对应
- [ ] 敏感信息通过环境变量提供
- [ ] 提供合理的默认值
- [ ] 配置命名符合规范
- [ ] 有完整的注释说明

### 代码实现检查
- [ ] 无硬编码配置值
- [ ] 使用配置验证库（如Pydantic）
- [ ] 环境变量读取正确
- [ ] 配置加载顺序正确

### 部署检查
- [ ] 各环境配置差异明确
- [ ] 生产环境配置安全
- [ ] 配置文档同步更新
- [ ] CI/CD中配置正确注入

## 示例配置模板

参考根目录的 `env-example-template.txt` 文件，包含完整的配置示例和说明。

## 相关文档
- [API规范](30-API-Standard.md) - 接口配置要求
- [安全规范](60-Security-Standard.md) - 敏感信息处理
- [部署规范](50-Deployment-Standard.md) - 环境配置管理

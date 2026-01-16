# Implementation Plan: 后端登录鉴权系统重构

**Branch**: `003-auth-refactor` | **Date**: 2026-01-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-auth-refactor/spec.md`

## Summary

修复当前登录鉴权系统中session cookie未正确传递导致的401错误问题。重构认证机制，确保用户登录后能够可靠地访问受保护资源，包括：正确设置HttpOnly cookie、处理CORS预检请求、实现会话管理和续期、添加详细的调试日志。技术方案基于现有的FastAPI + Redis + Session架构，重点优化cookie配置、会话存储和跨请求状态传递。

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.109+, SQLAlchemy 2.0.25+, Redis 5.0+, Pydantic 2.5+, Passlib (bcrypt), Structlog
**Storage**: PostgreSQL (用户数据) + Redis (会话存储)
**Testing**: pytest 7.4+, pytest-asyncio, pytest-cov (目标80%+覆盖率)
**Target Platform**: Linux server (Uvicorn ASGI)
**Project Type**: Web (Backend + Frontend分离)
**Performance Goals**:
- 登录响应时间 <100ms (p95)
- 会话验证 <10ms (p95)
- 支持1000并发认证请求
- Redis连接池复用率 >95%

**Constraints**:
- 必须向后兼容现有User模型和数据库schema
- 不能破坏现有的注册/密码重置功能（002-auth-integration）
- 必须在开发环境支持热更新（DEV_AUTO_RELOAD=true）
- Session过期时间：30分钟（普通），30天（记住我）

**Scale/Scope**:
- 预期用户数：10k+
- 并发会话：1000+
- 会话数据大小：~500 bytes/session
- Redis内存使用：~50MB (10k active sessions)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify compliance with `.specify/memory/constitution.md` principles:

- [x] **Configuration First**: 所有配置通过环境变量（SESSION_*, REDIS_*, CORS_*），无硬编码凭据
- [x] **Security by Design**: Session + Cookie认证（HttpOnly, SameSite=Lax），bcrypt密码哈希，速率限制，审计日志
- [x] **API Standards**: RESTful设计（POST /auth/login, GET /auth/me, POST /auth/logout），标准JSON响应，/api/v1版本化
- [x] **Testing Discipline**: 单元测试（session管理，cookie设置），集成测试（登录流程E2E），目标80%+覆盖率
- [x] **Observability**: Structlog结构化日志，correlation ID，敏感数据脱敏（session_id仅显示前20字符）
- [x] **Database Discipline**: 使用现有User表，Alembic migrations，soft delete (deleted_at)，无schema变更需求

**Complexity Violations**: 无违规项。所有原则均符合。

## Project Structure

### Documentation (this feature)

```text
specs/003-auth-refactor/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output - 现有问题分析和解决方案
├── data-model.md        # Phase 1 output - Session数据模型
├── quickstart.md        # Phase 1 output - 开发者快速上手指南
├── contracts/           # Phase 1 output - API contracts (OpenAPI)
│   └── auth-api.yaml
└── checklists/          # Quality gates
    └── requirements.md  # ✅ Already created
```

### Source Code (repository root)

```text
Backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── auth.py              # 登录/登出端点（需重构）
│   ├── core/
│   │   ├── config.py                # Session/CORS配置
│   │   ├── database.py              # Database连接
│   │   ├── dependencies.py          # 认证依赖（需重构）
│   │   ├── security.py              # 密码哈希/验证
│   │   └── session.py               # Session管理（需重构）
│   ├── models/
│   │   └── user.py                  # User模型（已存在）
│   ├── schemas/
│   │   └── auth.py                  # 登录请求/响应schemas
│   ├── services/
│   │   └── auth_service.py          # 认证业务逻辑
│   └── main.py                      # FastAPI app + middleware配置
├── tests/
│   ├── unit/
│   │   ├── test_session.py          # Session管理单元测试
│   │   ├── test_dependencies.py     # 认证依赖单元测试
│   │   └── test_cookie_handling.py  # Cookie设置/解析测试
│   ├── integration/
│   │   ├── test_auth_flow.py        # 登录->访问受保护资源E2E
│   │   └── test_session_lifecycle.py # 会话创建/续期/过期测试
│   └── conftest.py                  # pytest fixtures (test client, Redis mock)
├── .env                             # 环境变量配置
└── pyproject.toml                   # 依赖管理

Frontend/
├── src/
│   ├── features/
│   │   └── auth/
│   │       ├── api/
│   │       │   └── authReal.ts      # HTTP client (credentials: include)
│   │       └── contexts/
│   │           └── AuthContext.tsx  # 前端认证状态管理
│   └── shared/
│       ├── config/
│       │   └── api.ts               # API_CONFIG (BASE_URL, timeout)
│       └── lib/
│           └── apiClient.ts         # BaseApiClient (全局401拦截)
└── .env                             # VITE_API_BASE_URL配置
```

**Structure Decision**: 项目使用Web应用结构（Backend + Frontend分离）。Backend是FastAPI应用，Frontend是React+TypeScript应用。重构重点在Backend的认证层（`app/core/session.py`, `app/core/dependencies.py`, `app/api/v1/auth.py`），前端仅需确认正确配置`credentials: 'include'`和401拦截器。

## Complexity Tracking

> 无复杂性违规。所有设计遵循Constitution原则，无需特殊豁免。

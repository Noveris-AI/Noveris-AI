# Implementation Plan: Node Management Frontend-Backend Integration

**Branch**: `001-node-management-integration` | **Date**: 2026-01-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-node-management-integration/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

This feature resolves frontend-backend integration gaps in Node Management, specifically addressing type misalignments in AcceleratorType (ascend_npu/huawei_npu, generic_accel/other), ConnectionType (missing WinRM support), and JobStatus (missing TIMEOUT state). The primary approach involves creating unified type mappings, updating frontend API client to handle all backend responses correctly, and ensuring pagination metadata completeness (has_next/has_prev fields).

## Technical Context

**Language/Version**: Backend: Python 3.11; Frontend: TypeScript 5.2.2 + React 18.2.0
**Primary Dependencies**: Backend: FastAPI 0.109.0+, SQLAlchemy 2.0.25+, Alembic 1.13.0; Frontend: React Router 6.20.1, TanStack React Query 5.17.15, Axios 1.13.2, Zod 3.22.4
**Storage**: PostgreSQL (主数据库), Redis 5.0.1+ (缓存/会话), Celery (任务队列)
**Testing**: Backend: pytest 7.4.4+ with pytest-asyncio, 80%+ coverage target; Frontend: Vitest 1.0.4 + React Testing Library
**Target Platform**: Backend: Linux server (Docker容器化); Frontend: 现代浏览器 (Chrome/Firefox/Safari latest)
**Project Type**: Web application (separated backend/frontend)
**Performance Goals**: API响应 <200ms p95, 前端首次渲染 <2s, 任务执行事件流延迟 <2s
**Constraints**: 必须支持大规模节点管理(100+节点), 无需修改后端API实现, 保持向后兼容性
**Scale/Scope**: 5个用户故事, 8个功能需求, 影响6个前端类型定义和2个API客户端方法, 无需新增后端端点

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Verify compliance with `.specify/memory/constitution.md` principles:

- [x] **Configuration First**: ✓ 无新增配置需求，前端类型映射为纯代码逻辑，无需环境变量
- [x] **Security by Design**: ✓ 本功能仅修复前端类型映射，不涉及认证机制变更，现有Session+Cookie认证保持不变
- [x] **API Standards**: ✓ 无新增API端点，现有端点已遵循RESTful设计和`/api/v1/`版本化，仅修正前端响应解析
- [x] **Testing Discipline**: ✓ 新增前端类型映射单元测试，现有测试框架已配置(pytest 80%+ 后端覆盖率，Vitest前端测试)
- [x] **Observability**: ✓ 无新增日志需求，现有structlog已配置JSON格式，API调用保持现有日志策略
- [x] **Database Discipline**: ✓ 无数据库schema变更，仅修正前端对现有枚举类型的解析和显示

**评估结果**: ✅ 全部合规。本功能为前端类型对齐修复，不引入新的架构组件或安全风险，不违反任何宪章原则。

**Complexity Violations**: None - 本功能无违规项

## Project Structure

### Documentation (this feature)

```text
specs/001-node-management-integration/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── type-mapping.yaml # 前后端类型映射规范
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
Backend/
├── app/
│   ├── models/
│   │   └── node.py                # 后端数据模型 (NodeStatus, JobStatus, AcceleratorType, ConnectionType枚举)
│   ├── schemas/
│   │   └── node_management.py     # Pydantic响应schemas (NodeResponse, PaginatedResponse等)
│   ├── api/
│   │   └── v1/
│   │       └── nodes.py           # Node Management REST API端点
│   └── services/
│       └── node_management/
│           └── node_service.py    # 节点管理业务逻辑
└── tests/
    ├── unit/
    │   └── test_node_schemas.py   # Schema验证单元测试
    └── integration/
        └── test_node_api.py       # API集成测试

Frontend/
├── src/
│   ├── features/
│   │   └── nodes/
│   │       ├── api/
│   │       │   ├── nodeManagementTypes.ts   # 前端类型定义 (需修正)
│   │       │   └── nodeManagementClient.ts  # API客户端 (需修正)
│   │       ├── components/
│   │       │   ├── AcceleratorIcon.tsx      # 加速器图标组件 (需修正颜色映射)
│   │       │   ├── StatusBadge.tsx          # 状态徽章组件
│   │       │   └── NodeCard.tsx             # 节点卡片组件
│   │       └── pages/
│   │           ├── NodeListPage.tsx         # 节点列表页
│   │           └── NodeDetailPage.tsx       # 节点详情页
│   ├── lib/
│   │   └── api/
│   │       └── BaseApiClient.ts            # 基础API客户端
│   └── i18n/
│       ├── locales/
│       │   ├── zh-CN/
│       │   │   └── node.json               # 中文翻译 (需补充新类型标签)
│       │   └── en/
│       │       └── node.json               # 英文翻译 (需补充新类型标签)
└── tests/
    └── unit/
        └── features/
            └── nodes/
                ├── api/
                │   └── typeMappings.test.ts # 类型映射单元测试 (新增)
                └── components/
                    └── AcceleratorIcon.test.tsx # 加速器图标测试 (扩展)
```

**Structure Decision**: Web application with separated backend/frontend. Backend使用FastAPI + SQLAlchemy提供RESTful API，Frontend使用React + TypeScript构建SPA。本功能仅修改前端类型定义和UI组件，无需后端API变更，符合既有项目结构。关键文件：
- Backend: `app/models/node.py` (枚举定义来源)
- Frontend: `src/features/nodes/api/nodeManagementTypes.ts` (主要修正目标)
- Frontend: `src/features/nodes/components/AcceleratorIcon.tsx` (视觉映射修正)

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |

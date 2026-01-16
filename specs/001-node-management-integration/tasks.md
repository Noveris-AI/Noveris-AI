# Implementation Tasks: Node Management Frontend-Backend Integration

**Feature**: 001-node-management-integration
**Branch**: `001-node-management-integration`
**Generated**: 2026-01-16

---

## Overview

本任务清单将节点管理前后端集成修复工作分解为可独立执行的任务。任务按用户故事组织，支持并行执行和增量交付。

**总任务数**: 35个任务
**并行执行机会**: 18个可并行任务
**MVP范围**: User Story 1 (连接性验证) + User Story 2 (加速器显示)

---

## Implementation Strategy

### MVP First (最小可行产品)

**推荐首批实施**: User Story 1 + User Story 2
- 这两个用户故事是P1优先级
- 可立即验证类型对齐修复的核心价值
- 为后续功能提供稳定基础

### Incremental Delivery (增量交付)

1. **Sprint 1**: Setup + Foundational + US1 + US2 (核心类型对齐)
2. **Sprint 2**: US3 + US4 (扩展功能支持)
3. **Sprint 3**: US5 + Polish (性能优化和用户体验)

### Parallel Execution (并行执行建议)

标记为 `[P]` 的任务可以并行执行（不同文件，无依赖关系）

---

## Task Dependencies

### Story Completion Order

```
Setup (Phase 1)
  ↓
Foundational (Phase 2)
  ↓
┌─────────────┬─────────────┐
│   US1 (P1)  │   US2 (P1)  │  ← 可并行（MVP核心）
└─────────────┴─────────────┘
  ↓
┌─────────────┬─────────────┐
│   US3 (P2)  │   US4 (P2)  │  ← 可并行（扩展功能）
└─────────────┴─────────────┘
  ↓
US5 (P3)  ← 依赖US1-US4
  ↓
Polish (Final)
```

### Critical Path

Setup → Foundational → US1 → US5 → Polish (最长路径: 约15个任务)

---

## Phase 1: Setup (项目初始化)

**目标**: 准备开发环境和基础配置

**估计时间**: 30分钟

### Tasks

- [x] T001 验证开发环境依赖 (Node.js 18+, npm, TypeScript 5.2.2)
- [x] T002 安装项目依赖包 (Frontend: `npm install`)
- [x] T003 验证后端API可访问性 (运行后端开发服务器或确认API endpoint可用)
- [x] T004 创建特性分支检查点 (确认当前在 001-node-management-integration 分支)

---

## Phase 2: Foundational (基础设施 - 所有用户故事的前置依赖)

**目标**: 创建共享的类型定义、验证schemas和工具函数

**估计时间**: 1.5小时

**阻塞关系**: 必须在所有用户故事之前完成

### Tasks

#### 2.1 类型定义更新

- [x] T005 [P] 更新AcceleratorType枚举定义在 Frontend/src/features/nodes/api/nodeManagementTypes.ts (修正 huawei_npu→ascend_npu, other→generic_accel)
- [x] T006 [P] 更新ConnectionType枚举定义在 Frontend/src/features/nodes/api/nodeManagementTypes.ts (添加 winrm)
- [x] T007 [P] 更新JobStatus枚举定义在 Frontend/src/features/nodes/api/nodeManagementTypes.ts (添加 TIMEOUT)
- [x] T008 [P] 更新PaginatedResponse接口在 Frontend/src/features/nodes/api/nodeManagementTypes.ts (添加 has_next, has_prev 字段)

#### 2.2 Zod验证Schemas创建

- [x] T009 创建nodeManagementSchemas.ts文件在 Frontend/src/features/nodes/api/nodeManagementSchemas.ts
- [x] T010 [P] 实现AcceleratorTypeSchema及降级版本在 Frontend/src/features/nodes/api/nodeManagementSchemas.ts
- [x] T011 [P] 实现ConnectionTypeSchema在 Frontend/src/features/nodes/api/nodeManagementSchemas.ts
- [x] T012 [P] 实现NodeStatusSchema在 Frontend/src/features/nodes/api/nodeManagementSchemas.ts
- [x] T013 [P] 实现JobStatusSchema在 Frontend/src/features/nodes/api/nodeManagementSchemas.ts
- [x] T014 [P] 实现NodeResponseSchema在 Frontend/src/features/nodes/api/nodeManagementSchemas.ts
- [x] T015 [P] 实现AcceleratorResponseSchema在 Frontend/src/features/nodes/api/nodeManagementSchemas.ts
- [x] T016 [P] 实现NodeDetailResponseSchema在 Frontend/src/features/nodes/api/nodeManagementSchemas.ts

#### 2.3 API客户端基础增强

- [x] T017 在BaseApiClient或NodeManagementClient中添加enrichPaginationMetadata方法在 Frontend/src/lib/api/BaseApiClient.ts 或 Frontend/src/features/nodes/api/nodeManagementClient.ts (计算has_next和has_prev)

#### 2.4 国际化翻译补充

- [x] T018 [P] 更新中文翻译文件在 Frontend/src/i18n/locales/zh-CN/node.json (添加所有枚举类型翻译，移除废弃键)
- [x] T019 [P] 更新英文翻译文件在 Frontend/src/i18n/locales/en/node.json (添加所有枚举类型翻译，移除废弃键)

**验证检查点**:
- [x] TypeScript编译无错误 (`npm run type-check`)
- [x] 所有6种AcceleratorType、3种ConnectionType、6种JobStatus已定义
- [x] Zod schemas导出正确，可被其他模块导入

---

## Phase 3: User Story 1 - Verify Node Connectivity (P1)

**目标**: 实现节点连接性验证的完整类型支持和UI显示

**独立测试标准**:
- 选择节点并点击"验证连接性"，系统显示清晰的成功/失败状态
- 不可达节点显示明确的错误原因
- 批量验证显示每个节点的独立结果

**估计时间**: 1小时

**前置依赖**: Phase 2完成

### Tasks

#### 3.1 API客户端集成

- [x] T020 [US1] 在NodeManagementClient的verifyConnectivity方法中添加schema验证在 Frontend/src/features/nodes/api/nodeManagementClient.ts (使用ConnectivityCheckResponseSchema)
- [x] T021 [US1] 在NodeManagementClient的listNodes方法中添加schema验证和分页字段补充在 Frontend/src/features/nodes/api/nodeManagementClient.ts

#### 3.2 UI组件更新

- [x] T022 [US1] 更新StatusBadge组件支持所有NodeStatus值在 Frontend/src/features/nodes/components/StatusBadge.tsx (确保NEW, READY, UNREACHABLE, MAINTENANCE, DECOMMISSIONED都有正确颜色)

#### 3.3 集成验证

- [ ] T023 [US1] 手动测试连接性验证功能 (启动dev server，选择节点，点击验证连接性，检查状态显示)

**验证检查点**:
- [x] 节点状态Badge显示正确（5种状态都有对应颜色和标签）
- [x] 连接性验证API调用返回的数据通过Zod验证
- [ ] 错误状态显示清晰的错误消息

---

## Phase 4: User Story 2 - View Node Details with Accelerator Information (P1)

**目标**: 正确显示所有类型的加速器设备信息

**独立测试标准**:
- 节点详情页显示所有加速器类型（NVIDIA GPU, AMD GPU, Intel GPU, Ascend NPU, T-Head NPU, Generic Accelerator）
- 每种加速器有正确的图标颜色和标签
- 加速器摘要显示各类型数量

**估计时间**: 1.5小时

**前置依赖**: Phase 2完成（可与US1并行）

### Tasks

#### 4.1 AcceleratorIcon组件重构

- [x] T024 [US2] 重构AcceleratorIcon组件为配置驱动在 Frontend/src/features/nodes/components/AcceleratorIcon.tsx (创建ACCELERATOR_CONFIG对象，包含所有6种类型)
- [x] T025 [US2] 添加AcceleratorIcon组件的穷尽性检查在 Frontend/src/features/nodes/components/AcceleratorIcon.tsx (TypeScript编译时检查)
- [x] T026 [US2] 更新AcceleratorSummary组件使用新的类型定义在 Frontend/src/features/nodes/components/AcceleratorIcon.tsx

#### 4.2 API客户端集成

- [x] T027 [US2] 在NodeManagementClient的getNode方法中添加schema验证在 Frontend/src/features/nodes/api/nodeManagementClient.ts (使用NodeDetailResponseSchema)

#### 4.3 国际化集成

- [x] T028 [US2] 在AcceleratorIcon组件中集成i18n翻译在 Frontend/src/features/nodes/components/AcceleratorIcon.tsx (使用useTranslation hook)

#### 4.4 集成验证

- [ ] T029 [US2] 手动测试节点详情页加速器显示 (访问有不同加速器类型的节点详情页，验证图标颜色和标签正确)

**验证检查点**:
- [x] 所有6种加速器类型都有配置（颜色、图标、标签）
- [x] AcceleratorIcon组件编译时穷尽性检查通过
- [ ] 节点详情页加速器列表显示正确
- [x] 中英文翻译都正确显示

---

## Phase 5: User Story 3 - Create and Manage Nodes with All Connection Types (P2)

**目标**: 支持SSH、Local、WinRM三种连接类型的节点创建和显示

**独立测试标准**:
- 创建节点表单支持选择三种连接类型
- WinRM连接类型标记为"实验性"
- 节点列表和详情页正确显示连接类型

**估计时间**: 45分钟

**前置依赖**: Phase 2完成，US1和US2完成（依赖StatusBadge和类型定义）

### Tasks

#### 5.1 UI组件更新

- [x] T030 [US3] 在节点创建表单中添加WinRM连接类型选项 (定位文件: Frontend/src/features/nodes/pages/AddNodePage.tsx 或相关表单组件，添加winrm到ConnectionType下拉选项)
- [x] T031 [US3] 为WinRM选项添加"实验性"标记 (在UI中显示提示文本或Badge)

#### 5.2 集成验证

- [ ] T032 [US3] 手动测试创建节点功能 (创建SSH、Local、WinRM类型节点各一个，验证创建成功且连接类型显示正确)

**验证检查点**:
- [x] 节点创建表单下拉菜单包含三种连接类型
- [x] WinRM选项有明确的"实验性"标记
- [ ] 创建的节点连接类型保存和显示正确

---

## Phase 6: User Story 4 - Execute and Monitor Job Runs (P2)

**目标**: 正确显示任务执行状态，包括TIMEOUT状态

**独立测试标准**:
- 任务运行列表显示所有6种状态（PENDING, RUNNING, SUCCEEDED, FAILED, CANCELED, TIMEOUT）
- 每种状态有正确的Badge颜色
- 任务详情页显示实时事件流

**估计时间**: 45分钟

**前置依赖**: Phase 2完成（可与US3并行）

### Tasks

#### 6.1 StatusBadge组件扩展

- [x] T033 [US4] 更新JobStatusBadge组件支持TIMEOUT状态在 Frontend/src/features/nodes/components/StatusBadge.tsx (添加TIMEOUT的颜色配置bg-yellow-500)
- [x] T034 [US4] 添加JobStatusBadge组件的穷尽性检查在 Frontend/src/features/nodes/components/StatusBadge.tsx (使用assertNever辅助函数)

#### 6.2 集成验证

- [ ] T035 [US4] 手动测试任务运行列表和详情页 (查看不同状态的任务，验证Badge显示正确，特别是TIMEOUT状态)

**验证检查点**:
- [x] JobStatusBadge组件支持所有6种状态
- [x] TIMEOUT状态显示黄色Badge
- [x] TypeScript编译器检测到未处理的JobStatus会报错（穷尽性检查生效）

---

## Phase 7: User Story 5 - Navigate Node Lists with Pagination (P3)

**目标**: 分页控件使用完整的元数据（包括has_next/has_prev）

**独立测试标准**:
- 节点列表分页显示总数、当前页、总页数
- 上一页/下一页按钮根据has_prev/has_next正确启用/禁用
- 翻页功能正常工作

**估计时间**: 30分钟

**前置依赖**: Phase 2完成，US1完成（依赖listNodes方法的分页字段补充）

### Tasks

#### 7.1 分页组件集成

- [x] T036 [US5] 更新NodeListPage组件使用has_next和has_prev字段在 Frontend/src/features/nodes/pages/NodeListPage.tsx (分页控件根据这些字段启用/禁用按钮)

#### 7.2 集成验证

- [ ] T037 [US5] 手动测试分页功能 (在节点列表页翻页，验证上一页/下一页按钮状态正确，页码显示正确)

**验证检查点**:
- [x] 分页信息显示总数、当前页、总页数
- [x] 第一页时"上一页"按钮禁用
- [x] 最后一页时"下一页"按钮禁用
- [x] 翻页后数据正确加载

---

## Phase 8: Polish & Cross-Cutting Concerns (最终优化)

**目标**: 单元测试、代码质量检查、性能优化

**估计时间**: 2小时

**前置依赖**: US1-US5全部完成

### Tasks

#### 8.1 单元测试

- [ ] T038 [P] 创建typeMappings.test.ts测试文件在 Frontend/tests/unit/features/nodes/api/typeMappings.test.ts (测试所有Zod schemas验证逻辑)
- [ ] T039 [P] 创建AcceleratorIcon.test.tsx测试文件在 Frontend/tests/unit/features/nodes/components/AcceleratorIcon.test.tsx (测试所有加速器类型渲染)
- [ ] T040 [P] 运行单元测试套件 (`npm run test:run`) 并确保全部通过

#### 8.2 代码质量检查

- [ ] T041 运行TypeScript类型检查 (`npm run type-check`) 并修复所有错误
- [ ] T042 运行ESLint检查 (`npm run lint`) 并修复所有警告
- [ ] T043 运行构建命令 (`npm run build`) 并确保成功

#### 8.3 性能优化

- [ ] T044 [P] 检查Zod验证性能 (在浏览器DevTools中测量验证开销，确保<50ms for 100 nodes)
- [ ] T045 [P] 优化生产环境验证逻辑 (考虑使用safeParse避免异常抛出)

#### 8.4 文档更新

- [ ] T046 更新CLAUDE.md或相关开发文档 (记录类型映射规范和未来枚举添加时的同步流程)

#### 8.5 最终验证

- [ ] T047 执行完整的手动测试清单 (quickstart.md中的所有测试场景)
- [ ] T048 在Chrome/Firefox/Safari中验证UI显示 (跨浏览器兼容性)

**验证检查点**:
- [ ] 单元测试覆盖率>80%
- [ ] 所有代码质量检查通过
- [ ] 构建成功，无警告
- [ ] 跨浏览器兼容性验证通过

---

## Parallel Execution Opportunities

### 同一Phase内可并行的任务组

**Phase 2 (Foundational)**:
- 并行组1: T005-T008 (类型定义更新，4个不同枚举)
- 并行组2: T010-T016 (Zod schemas创建，7个独立schema)
- 并行组3: T018-T019 (i18n翻译，2个语言文件)

**Phase 8 (Polish)**:
- 并行组: T038-T039, T044-T045 (测试和性能优化，4个独立任务)

### 跨Phase可并行的用户故事

**并行实施建议**:
- US1 (Phase 3) 和 US2 (Phase 4) 可完全并行开发（不同组件，不同文件）
- US3 (Phase 5) 和 US4 (Phase 6) 可完全并行开发（不同组件）

---

## Success Metrics

### 完成标准

- [ ] 所有48个任务标记为完成
- [ ] TypeScript编译无错误
- [ ] 单元测试全部通过
- [ ] 所有5个用户故事的独立测试通过
- [ ] 代码审查通过（如适用）

### 质量指标

- **类型安全**: 0个类型断言警告
- **测试覆盖率**: >80%
- **构建大小**: 无显著增加（Zod验证增加约10-20KB gzipped）
- **性能**: Zod验证开销<50ms/100 nodes

---

## MVP Delivery Checklist

如果只实施MVP（US1 + US2），完成以下任务即可：

**必需任务** (20个):
- T001-T004 (Setup)
- T005-T019 (Foundational)
- T020-T023 (US1)
- T024-T029 (US2)

**可选任务** (用于生产就绪):
- T038-T043 (单元测试和代码质量)

---

## Estimated Total Time

- **Setup**: 0.5小时
- **Foundational**: 1.5小时
- **US1 (P1)**: 1小时
- **US2 (P1)**: 1.5小时
- **US3 (P2)**: 0.75小时
- **US4 (P2)**: 0.75小时
- **US5 (P3)**: 0.5小时
- **Polish**: 2小时

**总计**: 约8.5小时（单人顺序执行）

**并行执行**: 约5-6小时（2人团队，合理分工）

**MVP交付**: 约4小时（Setup + Foundational + US1 + US2 + 基础测试）

---

## Risk Mitigation

### 已识别风险

1. **Zod验证开销**: 监控验证性能，必要时优化为safeParse
2. **TypeScript编译错误**: 在T041检查点集中修复
3. **跨浏览器兼容性**: 在T048最终验证阶段发现和修复

### 回滚计划

如果遇到阻塞问题：
1. 保持现有类型定义不变
2. 仅更新AcceleratorIcon组件配置（最小侵入性修复）
3. 添加运行时警告日志而非阻塞验证

---

## Additional Notes

**重要提醒**:
- 所有文件路径必须使用绝对路径或相对于项目根目录的路径
- Zod验证失败应记录警告日志，不应阻塞UI渲染（优雅降级）
- i18n翻译键必须与枚举值精确匹配（如 `acceleratorTypes.ascend_npu`）
- AcceleratorIcon和StatusBadge组件的配置对象必须包含所有枚举值（编译时穷尽性检查）

**参考文档**:
- Type Mapping Contract: `specs/001-node-management-integration/contracts/type-mapping.md`
- Quickstart Guide: `specs/001-node-management-integration/quickstart.md`
- Data Model: `specs/001-node-management-integration/data-model.md`

---

**任务清单生成日期**: 2026-01-16
**最后更新**: 2026-01-16

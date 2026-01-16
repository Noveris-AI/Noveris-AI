# Type Mapping Contract

**Feature**: 001-node-management-integration
**Version**: 1.0.0
**Date**: 2026-01-16

---

## Overview

本合约文档定义了节点管理功能中前后端类型映射的权威规范。所有前端TypeScript类型定义必须严格遵循此合约，以确保与后端API的完全兼容性。

---

## Enumeration Type Mappings (枚举类型映射)

### 1. AcceleratorType (加速器类型)

**权威来源**: `Backend/app/models/node.py::AcceleratorType`

| 后端Python枚举 | API返回值 | 前端TypeScript类型 | UI显示标签 (中文) | UI显示标签 (英文) | 图标颜色类 |
|---------------|----------|-------------------|-----------------|-----------------|-----------|
| `NVIDIA_GPU` | `"nvidia_gpu"` | `'nvidia_gpu'` | NVIDIA GPU | NVIDIA GPU | `text-green-600 dark:text-green-400` |
| `AMD_GPU` | `"amd_gpu"` | `'amd_gpu'` | AMD GPU | AMD GPU | `text-red-600 dark:text-red-400` |
| `INTEL_GPU` | `"intel_gpu"` | `'intel_gpu'` | Intel GPU | Intel GPU | `text-blue-600 dark:text-blue-400` |
| `ASCEND_NPU` | `"ascend_npu"` | `'ascend_npu'` | 华为昇腾 NPU | Ascend NPU | `text-rose-600 dark:text-rose-400` |
| `T_HEAD_NPU` | `"t_head_npu"` | `'t_head_npu'` | 平头哥 NPU | T-Head NPU | `text-violet-600 dark:text-violet-400` |
| `GENERIC_ACCEL` | `"generic_accel"` | `'generic_accel'` | 通用加速器 | Generic Accelerator | `text-stone-600 dark:text-stone-400` |

**前端类型定义**:
```typescript
export type AcceleratorType =
  | 'nvidia_gpu'
  | 'amd_gpu'
  | 'intel_gpu'
  | 'ascend_npu'
  | 't_head_npu'
  | 'generic_accel'
```

**Zod验证Schema**:
```typescript
export const AcceleratorTypeSchema = z.enum([
  'nvidia_gpu',
  'amd_gpu',
  'intel_gpu',
  'ascend_npu',
  't_head_npu',
  'generic_accel'
]);
```

**i18n翻译键映射**:
```typescript
// zh-CN/node.json
{
  "acceleratorTypes": {
    "nvidia_gpu": "NVIDIA GPU",
    "amd_gpu": "AMD GPU",
    "intel_gpu": "Intel GPU",
    "ascend_npu": "华为昇腾 NPU",
    "t_head_npu": "平头哥 NPU",
    "generic_accel": "通用加速器"
  }
}
```

**已废弃的映射** (必须移除):
- ❌ `huawei_npu` → 替换为 `ascend_npu`
- ❌ `other` → 替换为 `generic_accel`

---

### 2. ConnectionType (连接类型)

**权威来源**: `Backend/app/models/node.py::ConnectionType`

| 后端Python枚举 | API返回值 | 前端TypeScript类型 | UI显示标签 (中文) | UI显示标签 (英文) | 状态 |
|---------------|----------|-------------------|-----------------|-----------------|------|
| `SSH` | `"ssh"` | `'ssh'` | SSH 连接 | SSH Connection | 生产可用 |
| `LOCAL` | `"local"` | `'local'` | 本地连接 | Local Connection | 生产可用 |
| `WINRM` | `"winrm"` | `'winrm'` | WinRM 连接 | WinRM Connection | 预留 (实验性) |

**前端类型定义**:
```typescript
export type ConnectionType = 'ssh' | 'local' | 'winrm'
```

**Zod验证Schema**:
```typescript
export const ConnectionTypeSchema = z.enum(['ssh', 'local', 'winrm']);
```

**i18n翻译键映射**:
```typescript
// zh-CN/node.json
{
  "connectionTypes": {
    "ssh": "SSH 连接",
    "local": "本地连接",
    "winrm": "WinRM 连接"
  }
}
```

**实现注意事项**:
- `winrm`类型当前为预留值，UI可显示但创建表单中应标记为"实验性功能"

---

### 3. NodeStatus (节点状态)

**权威来源**: `Backend/app/models/node.py::NodeStatus`

| 后端Python枚举 | API返回值 | 前端TypeScript类型 | UI显示标签 (中文) | UI显示标签 (英文) | Badge颜色 |
|---------------|----------|-------------------|-----------------|-----------------|----------|
| `NEW` | `"NEW"` | `'NEW'` | 新建 | New | `bg-gray-500` |
| `READY` | `"READY"` | `'READY'` | 就绪 | Ready | `bg-green-500` |
| `UNREACHABLE` | `"UNREACHABLE"` | `'UNREACHABLE'` | 不可达 | Unreachable | `bg-red-500` |
| `MAINTENANCE` | `"MAINTENANCE"` | `'MAINTENANCE'` | 维护中 | Maintenance | `bg-orange-500` |
| `DECOMMISSIONED` | `"DECOMMISSIONED"` | `'DECOMMISSIONED'` | 已停用 | Decommissioned | `bg-gray-700` |

**前端类型定义**:
```typescript
export type NodeStatus =
  | 'NEW'
  | 'READY'
  | 'UNREACHABLE'
  | 'MAINTENANCE'
  | 'DECOMMISSIONED'
```

**Zod验证Schema**:
```typescript
export const NodeStatusSchema = z.enum([
  'NEW',
  'READY',
  'UNREACHABLE',
  'MAINTENANCE',
  'DECOMMISSIONED'
]);
```

**i18n翻译键映射**:
```typescript
// zh-CN/node.json
{
  "nodeStatus": {
    "NEW": "新建",
    "READY": "就绪",
    "UNREACHABLE": "不可达",
    "MAINTENANCE": "维护中",
    "DECOMMISSIONED": "已停用"
  }
}
```

---

### 4. JobStatus (任务状态)

**权威来源**: `Backend/app/models/node.py::JobStatus`

| 后端Python枚举 | API返回值 | 前端TypeScript类型 | UI显示标签 (中文) | UI显示标签 (英文) | Badge颜色 |
|---------------|----------|-------------------|-----------------|-----------------|----------|
| `PENDING` | `"PENDING"` | `'PENDING'` | 等待中 | Pending | `bg-gray-500` |
| `RUNNING` | `"RUNNING"` | `'RUNNING'` | 运行中 | Running | `bg-blue-500` |
| `SUCCEEDED` | `"SUCCEEDED"` | `'SUCCEEDED'` | 成功 | Succeeded | `bg-green-500` |
| `FAILED` | `"FAILED"` | `'FAILED'` | 失败 | Failed | `bg-red-500` |
| `CANCELED` | `"CANCELED"` | `'CANCELED'` | 已取消 | Canceled | `bg-orange-500` |
| `TIMEOUT` | `"TIMEOUT"` | `'TIMEOUT'` | 超时 | Timeout | `bg-yellow-500` |

**前端类型定义**:
```typescript
export type JobStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELED'
  | 'TIMEOUT'
```

**Zod验证Schema**:
```typescript
export const JobStatusSchema = z.enum([
  'PENDING',
  'RUNNING',
  'SUCCEEDED',
  'FAILED',
  'CANCELED',
  'TIMEOUT'
]);
```

**i18n翻译键映射**:
```typescript
// zh-CN/node.json
{
  "jobStatus": {
    "PENDING": "等待中",
    "RUNNING": "运行中",
    "SUCCEEDED": "成功",
    "FAILED": "失败",
    "CANCELED": "已取消",
    "TIMEOUT": "超时"
  }
}
```

**已废弃的映射** (必须补充):
- ⚠️ 前端之前缺少 `'TIMEOUT'` 类型，必须添加

---

## API Response Structure Contracts (API响应结构合约)

### PaginatedResponse

**后端Schema**: `Backend/app/schemas/node_management.py::PaginatedResponse`

**后端返回字段**:
```json
{
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

**前端增强字段** (在API客户端计算):
```json
{
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5,
  "has_next": true,   // 计算: page < total_pages
  "has_prev": false   // 计算: page > 1
}
```

**前端类型定义**:
```typescript
export interface PaginatedResponse {
  total: number
  page: number
  page_size: number
  total_pages: number
  has_next: boolean    // 前端补充字段
  has_prev: boolean    // 前端补充字段
}
```

**计算逻辑实现**:
```typescript
function enrichPaginationMetadata(apiResponse: any): PaginatedResponse {
  const { total, page, page_size, total_pages } = apiResponse.pagination;
  return {
    total,
    page,
    page_size,
    total_pages,
    has_next: page < total_pages,
    has_prev: page > 1
  };
}
```

---

### NodeListResponse

**后端Schema**: `Backend/app/schemas/node_management.py::NodeListResponse`

**API端点**: `GET /api/v1/nodes`

**响应结构**:
```json
{
  "nodes": [
    {
      "id": "uuid",
      "name": "node-01",
      "status": "READY",
      "accelerator_summary": {
        "nvidia_gpu": 2,
        "ascend_npu": 1
      },
      ...
    }
  ],
  "pagination": {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5
  }
}
```

**前端类型定义**:
```typescript
export interface NodeListResponse {
  nodes: Node[]
  pagination: PaginatedResponse  // 使用增强版
}
```

---

### NodeDetailResponse

**后端Schema**: `Backend/app/schemas/node_management.py::NodeDetailResponse`

**API端点**: `GET /api/v1/nodes/{node_id}`

**响应结构**:
```json
{
  "id": "uuid",
  "name": "node-01",
  "status": "READY",
  "connection_type": "ssh",
  "accelerators": [
    {
      "id": "uuid",
      "type": "nvidia_gpu",
      "model": "A100",
      "memory_mb": 81920
    },
    {
      "id": "uuid",
      "type": "ascend_npu",
      "model": "Ascend 910",
      "memory_mb": 32768
    }
  ],
  "credentials_exist": true,
  "bmc_configured": false,
  ...
}
```

**前端类型定义**:
```typescript
export interface NodeDetail extends Node {
  credentials_exist: boolean
  bmc_configured: boolean
  accelerators: Accelerator[]
  last_facts?: Record<string, any>
}
```

---

### JobRunListResponse

**后端Schema**: `Backend/app/schemas/node_management.py::JobRunListResponse`

**API端点**: `GET /api/v1/job-runs`

**响应结构**:
```json
{
  "runs": [
    {
      "id": "uuid",
      "template_name": "Install Driver",
      "status": "RUNNING",
      "node_count": 5,
      "created_at": "2026-01-16T10:00:00Z"
    }
  ],
  "pagination": {
    "total": 50,
    "page": 1,
    "page_size": 20,
    "total_pages": 3
  }
}
```

**前端类型定义**:
```typescript
export interface JobRunListResponse {
  runs: JobRun[]
  pagination: PaginatedResponse
}
```

---

## Runtime Validation Strategy (运行时验证策略)

### 优雅降级规则

**AcceleratorType未知值处理**:
```typescript
const AcceleratorTypeSchemaWithFallback = z.string().transform((val) => {
  const validTypes: AcceleratorType[] = [
    'nvidia_gpu', 'amd_gpu', 'intel_gpu',
    'ascend_npu', 't_head_npu', 'generic_accel'
  ];

  if (validTypes.includes(val as AcceleratorType)) {
    return val as AcceleratorType;
  }

  console.warn(`Unknown accelerator type "${val}" received from API, falling back to "generic_accel"`);
  return 'generic_accel' as AcceleratorType;
});
```

**JobStatus未知值处理**:
```typescript
const JobStatusSchemaWithFallback = z.string().transform((val) => {
  const validStatuses: JobStatus[] = [
    'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED', 'TIMEOUT'
  ];

  if (validStatuses.includes(val as JobStatus)) {
    return val as JobStatus;
  }

  console.error(`Unknown job status "${val}" received from API, treating as FAILED`);
  return 'FAILED' as JobStatus;
});
```

---

## UI Component Configuration Contracts (UI组件配置合约)

### AcceleratorIcon Configuration

**配置对象结构**:
```typescript
interface AcceleratorIconConfig {
  icon: LucideIcon
  colorClass: string
  label: string
}

const ACCELERATOR_CONFIG: Record<AcceleratorType, AcceleratorIconConfig> = {
  nvidia_gpu: {
    icon: Cpu,
    colorClass: 'text-green-600 dark:text-green-400',
    label: 'NVIDIA GPU'
  },
  amd_gpu: {
    icon: Cpu,
    colorClass: 'text-red-600 dark:text-red-400',
    label: 'AMD GPU'
  },
  intel_gpu: {
    icon: Cpu,
    colorClass: 'text-blue-600 dark:text-blue-400',
    label: 'Intel GPU'
  },
  ascend_npu: {
    icon: Cpu,
    colorClass: 'text-rose-600 dark:text-rose-400',
    label: 'Ascend NPU'
  },
  t_head_npu: {
    icon: Cpu,
    colorClass: 'text-violet-600 dark:text-violet-400',
    label: 'T-Head NPU'
  },
  generic_accel: {
    icon: Cpu,
    colorClass: 'text-stone-600 dark:text-stone-400',
    label: 'Generic Accelerator'
  }
};
```

**穷尽性检查**:
```typescript
// 编译时确保所有AcceleratorType都有配置
type ConfigKeys = keyof typeof ACCELERATOR_CONFIG;
type AllTypesHandled = AcceleratorType extends ConfigKeys ? true : false;
const _typeCheck: AllTypesHandled = true;
```

---

### StatusBadge Configuration

**NodeStatus Badge配置**:
```typescript
const NODE_STATUS_CONFIG: Record<NodeStatus, { colorClass: string; label: string }> = {
  NEW: { colorClass: 'bg-gray-500', label: 'New' },
  READY: { colorClass: 'bg-green-500', label: 'Ready' },
  UNREACHABLE: { colorClass: 'bg-red-500', label: 'Unreachable' },
  MAINTENANCE: { colorClass: 'bg-orange-500', label: 'Maintenance' },
  DECOMMISSIONED: { colorClass: 'bg-gray-700', label: 'Decommissioned' }
};
```

**JobStatus Badge配置**:
```typescript
const JOB_STATUS_CONFIG: Record<JobStatus, { colorClass: string; label: string }> = {
  PENDING: { colorClass: 'bg-gray-500', label: 'Pending' },
  RUNNING: { colorClass: 'bg-blue-500', label: 'Running' },
  SUCCEEDED: { colorClass: 'bg-green-500', label: 'Succeeded' },
  FAILED: { colorClass: 'bg-red-500', label: 'Failed' },
  CANCELED: { colorClass: 'bg-orange-500', label: 'Canceled' },
  TIMEOUT: { colorClass: 'bg-yellow-500', label: 'Timeout' }
};
```

---

## Contract Version History (合约版本历史)

| 版本 | 日期 | 变更内容 | 影响范围 |
|------|------|---------|---------|
| 1.0.0 | 2026-01-16 | 初始版本，定义所有枚举类型映射规范 | 所有前端代码 |

---

## Compliance Checklist (合规性检查清单)

- [ ] `Frontend/src/features/nodes/api/nodeManagementTypes.ts` 中所有枚举类型与本合约一致
- [ ] `Frontend/src/features/nodes/components/AcceleratorIcon.tsx` 配置对象包含所有6种加速器类型
- [ ] `Frontend/src/features/nodes/components/StatusBadge.tsx` 处理所有6种JobStatus（包括TIMEOUT）
- [ ] `Frontend/src/i18n/locales/zh-CN/node.json` 包含所有枚举值的中文翻译
- [ ] `Frontend/src/i18n/locales/en/node.json` 包含所有枚举值的英文翻译
- [ ] 移除所有已废弃的映射值 (`huawei_npu`, `other`)
- [ ] `BaseApiClient.ts` 实现分页字段补充逻辑
- [ ] 单元测试覆盖所有类型映射和降级逻辑

---

**合约所有者**: Backend Team (真实来源维护者)
**合约消费者**: Frontend Team (必须遵循此规范)
**审查周期**: 每次后端枚举变更时同步更新

---

**文档完成日期**: 2026-01-16
**下一步**: Phase 1 - 生成快速入门文档 (quickstart.md)

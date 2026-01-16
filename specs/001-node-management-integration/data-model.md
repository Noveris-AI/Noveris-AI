# Data Model: Node Management Frontend-Backend Integration

**Feature**: 001-node-management-integration
**Date**: 2026-01-16
**Status**: Design Phase

---

## Overview

本文档定义了节点管理功能的前端数据模型，基于后端API响应结构和功能需求进行设计。主要实体包括：枚举类型（AcceleratorType, ConnectionType, NodeStatus, JobStatus）、核心实体（Node, Accelerator, NodeGroup, JobRun）和响应包装类型（PaginatedResponse）。

---

## Enumerations (枚举类型)

### AcceleratorType (加速器类型)

**定义**: GPU或NPU加速器的设备类型

**值**:
| 枚举值 | 显示标签 (中文) | 显示标签 (英文) | 说明 |
|--------|----------------|----------------|------|
| `nvidia_gpu` | NVIDIA GPU | NVIDIA GPU | NVIDIA图形处理器 |
| `amd_gpu` | AMD GPU | AMD GPU | AMD图形处理器 |
| `intel_gpu` | Intel GPU | Intel GPU | Intel图形处理器 |
| `ascend_npu` | 华为昇腾 NPU | Ascend NPU | 华为昇腾神经网络处理器 |
| `t_head_npu` | 平头哥 NPU | T-Head NPU | 阿里平头哥神经网络处理器 |
| `generic_accel` | 通用加速器 | Generic Accelerator | 其他未分类加速器 |

**TypeScript定义**:
```typescript
export type AcceleratorType =
  | 'nvidia_gpu'
  | 'amd_gpu'
  | 'intel_gpu'
  | 'ascend_npu'
  | 't_head_npu'
  | 'generic_accel'
```

**验证规则**:
- 必须是上述6个值之一
- API响应中的未知值应降级为`generic_accel`并记录警告日志

---

### ConnectionType (连接类型)

**定义**: 节点连接方式

**值**:
| 枚举值 | 显示标签 (中文) | 显示标签 (英文) | 说明 |
|--------|----------------|----------------|------|
| `ssh` | SSH 连接 | SSH Connection | 通过SSH协议连接Linux节点 |
| `local` | 本地连接 | Local Connection | 本地执行（控制平面所在节点） |
| `winrm` | WinRM 连接 | WinRM Connection | 通过WinRM协议连接Windows节点 |

**TypeScript定义**:
```typescript
export type ConnectionType = 'ssh' | 'local' | 'winrm'
```

**验证规则**:
- 必须是上述3个值之一
- WinRM当前为预留值，UI可显示但创建表单中可标记为"实验性"

---

### NodeStatus (节点状态)

**定义**: 节点的运行状态

**值**:
| 枚举值 | 显示标签 (中文) | 显示标签 (英文) | 颜色 | 说明 |
|--------|----------------|----------------|------|------|
| `NEW` | 新建 | New | 灰色 | 新添加的节点，未进行连接验证 |
| `READY` | 就绪 | Ready | 绿色 | 已验证连接，可运行任务 |
| `UNREACHABLE` | 不可达 | Unreachable | 红色 | 无法连接到节点 |
| `MAINTENANCE` | 维护中 | Maintenance | 橙色 | 维护模式，不接受新任务 |
| `DECOMMISSIONED` | 已停用 | Decommissioned | 深灰色 | 已从集群移除，仅保留历史记录 |

**TypeScript定义**:
```typescript
export type NodeStatus =
  | 'NEW'
  | 'READY'
  | 'UNREACHABLE'
  | 'MAINTENANCE'
  | 'DECOMMISSIONED'
```

**状态转换规则**:
```
NEW → READY (验证成功)
NEW → UNREACHABLE (验证失败)
READY ↔ UNREACHABLE (连接状态变化)
READY → MAINTENANCE (手动设置)
MAINTENANCE → READY (手动恢复)
* → DECOMMISSIONED (软删除)
```

---

### JobStatus (任务状态)

**定义**: 任务运行的状态

**值**:
| 枚举值 | 显示标签 (中文) | 显示标签 (英文) | 颜色 | 说明 |
|--------|----------------|----------------|------|------|
| `PENDING` | 等待中 | Pending | 灰色 | 任务已创建，等待调度 |
| `RUNNING` | 运行中 | Running | 蓝色 | 任务正在执行 |
| `SUCCEEDED` | 成功 | Succeeded | 绿色 | 任务成功完成 |
| `FAILED` | 失败 | Failed | 红色 | 任务执行失败 |
| `CANCELED` | 已取消 | Canceled | 橙色 | 用户手动取消 |
| `TIMEOUT` | 超时 | Timeout | 黄色 | 任务执行超时 |

**TypeScript定义**:
```typescript
export type JobStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELED'
  | 'TIMEOUT'
```

**状态转换规则**:
```
PENDING → RUNNING (开始执行)
RUNNING → SUCCEEDED (成功完成)
RUNNING → FAILED (执行失败)
RUNNING → CANCELED (用户取消)
RUNNING → TIMEOUT (超时触发)
```

---

## Core Entities (核心实体)

### Node (节点)

**描述**: 受管计算节点，可以是物理服务器、虚拟机或容器主机

**字段**:
| 字段名 | 类型 | 必填 | 说明 | 验证规则 |
|--------|------|------|------|----------|
| `id` | `string` (UUID) | 是 | 节点唯一标识符 | UUID格式 |
| `tenant_id` | `string` (UUID) | 是 | 租户ID (多租户隔离) | UUID格式 |
| `name` | `string` | 是 | 节点名称 (内部标识符) | 1-64字符，字母数字下划线 |
| `display_name` | `string` | 是 | 显示名称 (用户友好) | 1-128字符 |
| `host` | `string` | 是 | 主机名或IP地址 | 有效主机名或IP |
| `port` | `number` | 是 | SSH/WinRM端口 | 1-65535 |
| `connection_type` | `ConnectionType` | 是 | 连接类型 | 枚举值 |
| `ssh_user` | `string` | 是 | SSH用户名 | 1-64字符 |
| `node_type` | `string` | 否 | 节点类型标签 | 自由文本 |
| `labels` | `Record<string, string>` | 否 | 键值对标签 | 键名限制32字符 |
| `tags` | `string[]` | 否 | 标签数组 | 每个标签限制32字符 |
| `status` | `NodeStatus` | 是 | 节点状态 | 枚举值 |
| `os_release` | `string` | 否 | 操作系统发行版 | 如 "Ubuntu 22.04" |
| `kernel_version` | `string` | 否 | 内核版本 | 如 "5.15.0-76-generic" |
| `cpu_cores` | `number` | 否 | CPU核心数 | 正整数 |
| `cpu_model` | `string` | 否 | CPU型号 | 自由文本 |
| `mem_mb` | `number` | 否 | 内存大小 (MB) | 正整数 |
| `disk_mb` | `number` | 否 | 磁盘大小 (MB) | 正整数 |
| `architecture` | `string` | 否 | CPU架构 | 如 "x86_64", "aarch64" |
| `last_seen_at` | `string` (ISO8601) | 否 | 最后连接时间 | ISO8601格式 |
| `last_job_run_at` | `string` (ISO8601) | 否 | 最后任务执行时间 | ISO8601格式 |
| `created_at` | `string` (ISO8601) | 是 | 创建时间 | ISO8601格式 |
| `updated_at` | `string` (ISO8601) | 是 | 更新时间 | ISO8601格式 |
| `group_ids` | `string[]` (UUID) | 是 | 所属节点组ID列表 | UUID数组 |
| `group_names` | `string[]` | 是 | 所属节点组名称列表 | 显示用 |
| `accelerator_summary` | `Record<AcceleratorType, number>` | 否 | 加速器摘要 (类型→数量) | 数量为正整数 |

**TypeScript定义**:
```typescript
export interface Node {
  id: string
  tenant_id: string
  name: string
  display_name: string
  host: string
  port: number
  connection_type: ConnectionType
  ssh_user: string
  node_type: string
  labels: Record<string, string>
  tags: string[]
  status: NodeStatus
  os_release?: string
  kernel_version?: string
  cpu_cores?: number
  cpu_model?: string
  mem_mb?: number
  disk_mb?: number
  architecture?: string
  last_seen_at?: string
  last_job_run_at?: string
  created_at: string
  updated_at: string
  group_ids: string[]
  group_names: string[]
  accelerator_summary: Record<AcceleratorType, number>
}
```

**关系**:
- 一对多: Node → Accelerator (一个节点有多个加速器)
- 多对多: Node ↔ NodeGroup (一个节点属于多个组)
- 一对多: Node → JobRun (一个节点有多个任务执行历史)

---

### NodeDetail (节点详情)

**描述**: 扩展Node实体，包含敏感信息标志和完整硬件清单

**继承**: 继承所有`Node`字段，并添加以下字段

**额外字段**:
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `credentials_exist` | `boolean` | 是 | 是否已配置SSH凭证 |
| `bmc_configured` | `boolean` | 是 | 是否已配置BMC（带外管理）凭证 |
| `accelerators` | `Accelerator[]` | 是 | 加速器设备详细列表 |
| `last_facts` | `Record<string, any>` | 否 | 最后收集的Ansible Facts |

**TypeScript定义**:
```typescript
export interface NodeDetail extends Node {
  credentials_exist: boolean
  bmc_configured: boolean
  accelerators: Accelerator[]
  last_facts?: Record<string, any>
}
```

---

### Accelerator (加速器设备)

**描述**: GPU或NPU设备的详细硬件信息

**字段**:
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `id` | `string` (UUID) | 是 | 加速器唯一标识符 |
| `node_id` | `string` (UUID) | 是 | 所属节点ID |
| `type` | `AcceleratorType` | 是 | 加速器类型 |
| `vendor` | `string` | 是 | 厂商 (如 "NVIDIA", "AMD") |
| `model` | `string` | 是 | 型号 (如 "A100", "MI250") |
| `device_id` | `string` | 是 | 设备ID (如 PCI设备ID) |
| `slot` | `string` | 否 | 插槽位置 |
| `bus_id` | `string` | 否 | PCI总线ID |
| `numa_node` | `number` | 否 | NUMA节点 |
| `memory_mb` | `number` | 否 | 显存大小 (MB) |
| `cores` | `number` | 否 | CUDA核心数/计算单元数 |
| `mig_capable` | `boolean` | 否 | 是否支持MIG (NVIDIA多实例GPU) |
| `mig_mode` | `boolean` | 否 | MIG模式是否启用 |
| `compute_capability` | `string` | 否 | 计算能力 (NVIDIA) |
| `driver_version` | `string` | 否 | 驱动版本 |
| `firmware_version` | `string` | 否 | 固件版本 |
| `health_status` | `string` | 否 | 健康状态 (如 "healthy", "degraded") |
| `temperature_celsius` | `number` | 否 | 当前温度 |
| `power_usage_watts` | `number` | 否 | 当前功耗 (瓦特) |
| `utilization_percent` | `number` | 否 | 当前利用率 (0-100) |
| `discovered_at` | `string` (ISO8601) | 是 | 发现时间 |

**TypeScript定义**:
```typescript
export interface Accelerator {
  id: string
  node_id: string
  type: AcceleratorType
  vendor: string
  model: string
  device_id: string
  slot?: string
  bus_id?: string
  numa_node?: number
  memory_mb?: number
  cores?: number
  mig_capable?: boolean
  mig_mode?: boolean
  compute_capability?: string
  driver_version?: string
  firmware_version?: string
  health_status?: string
  temperature_celsius?: number
  power_usage_watts?: number
  utilization_percent?: number
  discovered_at: string
}
```

---

### NodeGroup (节点组)

**描述**: 节点的逻辑分组，用于批量操作和变量继承

**字段**:
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `id` | `string` (UUID) | 是 | 节点组ID |
| `tenant_id` | `string` (UUID) | 是 | 租户ID |
| `name` | `string` | 是 | 组名 (内部标识符) |
| `display_name` | `string` | 是 | 显示名称 |
| `description` | `string` | 否 | 组描述 |
| `parent_id` | `string` (UUID) | 否 | 父组ID (支持层级结构) |
| `priority` | `number` | 是 | 优先级 (变量合并时使用) |
| `is_system` | `boolean` | 是 | 是否为系统组 (系统组不可删除) |
| `node_count` | `number` | 是 | 节点数量 |
| `created_at` | `string` (ISO8601) | 是 | 创建时间 |
| `updated_at` | `string` (ISO8601) | 是 | 更新时间 |
| `parent_name` | `string` | 否 | 父组名称 |
| `children_names` | `string[]` | 是 | 子组名称列表 |
| `has_vars` | `boolean` | 是 | 是否有组变量 |

**TypeScript定义**:
```typescript
export interface NodeGroup {
  id: string
  tenant_id: string
  name: string
  display_name: string
  description?: string
  parent_id?: string
  priority: number
  is_system: boolean
  node_count: number
  created_at: string
  updated_at: string
  parent_name?: string
  children_names: string[]
  has_vars: boolean
}
```

---

### JobTemplate (任务模板)

**描述**: 可复用的Ansible Playbook模板定义

**字段**:
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `id` | `string` (UUID) | 是 | 模板ID |
| `tenant_id` | `string` (UUID) | 是 | 租户ID |
| `name` | `string` | 是 | 模板名称 |
| `display_name` | `string` | 是 | 显示名称 |
| `description` | `string` | 否 | 模板描述 |
| `category` | `string` | 是 | 类别 (如 "system", "driver", "monitoring") |
| `playbook_path` | `string` | 是 | Playbook文件路径 |
| `become` | `boolean` | 是 | 是否需要sudo权限 |
| `become_method` | `string` | 否 | sudo方法 (默认 "sudo") |
| `timeout_seconds` | `number` | 是 | 超时时间 (秒) |
| `supports_serial` | `boolean` | 是 | 是否支持滚动更新 |
| `input_schema` | `Record<string, any>` | 否 | 输入参数JSON Schema |
| `is_enabled` | `boolean` | 是 | 是否启用 |
| `created_at` | `string` (ISO8601) | 是 | 创建时间 |

**TypeScript定义**:
```typescript
export interface JobTemplate {
  id: string
  tenant_id: string
  name: string
  display_name: string
  description?: string
  category: string
  playbook_path: string
  become: boolean
  become_method?: string
  timeout_seconds: number
  supports_serial: boolean
  input_schema?: Record<string, any>
  is_enabled: boolean
  created_at: string
}
```

---

### JobRun (任务运行记录)

**描述**: 任务模板的执行实例

**字段**:
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `id` | `string` (UUID) | 是 | 任务运行ID |
| `tenant_id` | `string` (UUID) | 是 | 租户ID |
| `template_id` | `string` (UUID) | 是 | 任务模板ID |
| `template_name` | `string` | 是 | 任务模板名称 (快照) |
| `status` | `JobStatus` | 是 | 任务状态 |
| `target_type` | `'node' \| 'group' \| 'all'` | 是 | 目标类型 |
| `target_node_ids` | `string[]` (UUID) | 否 | 目标节点ID列表 |
| `target_group_ids` | `string[]` (UUID) | 否 | 目标节点组ID列表 |
| `node_count` | `number` | 是 | 节点数量 |
| `extra_vars` | `Record<string, any>` | 否 | 用户提供的额外变量 |
| `runtime_vars` | `Record<string, any>` | 否 | 运行时生成的变量 |
| `serial` | `string` | 否 | 滚动更新配置 (如 "3", "10%") |
| `current_batch` | `number` | 否 | 当前批次 |
| `total_batches` | `number` | 否 | 总批次数 |
| `summary` | `JobRunSummary` | 否 | 执行摘要 |
| `created_at` | `string` (ISO8601) | 是 | 创建时间 |
| `started_at` | `string` (ISO8601) | 否 | 开始时间 |
| `finished_at` | `string` (ISO8601) | 否 | 结束时间 |
| `duration_seconds` | `number` | 否 | 执行时长 (秒) |
| `created_by` | `string` (UUID) | 是 | 创建用户ID |

**TypeScript定义**:
```typescript
export interface JobRun {
  id: string
  tenant_id: string
  template_id: string
  template_name: string
  status: JobStatus
  target_type: 'node' | 'group' | 'all'
  target_node_ids?: string[]
  target_group_ids?: string[]
  node_count: number
  extra_vars?: Record<string, any>
  runtime_vars?: Record<string, any>
  serial?: string
  current_batch?: number
  total_batches?: number
  summary?: JobRunSummary
  created_at: string
  started_at?: string
  finished_at?: string
  duration_seconds?: number
  created_by: string
}

export interface JobRunSummary {
  ok: number
  changed: number
  unreachable: number
  failed: number
  skipped: number
}
```

---

### JobRunEvent (任务运行事件)

**描述**: 任务执行过程中的实时事件流

**字段**:
| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `id` | `string` (UUID) | 是 | 事件ID |
| `job_run_id` | `string` (UUID) | 是 | 所属任务运行ID |
| `node_id` | `string` (UUID) | 否 | 相关节点ID |
| `node_name` | `string` | 否 | 节点名称 |
| `event_type` | `string` | 是 | 事件类型 (如 "playbook_start", "task_start", "task_result") |
| `event_data` | `Record<string, any>` | 是 | 事件数据 (Ansible事件原始JSON) |
| `task_name` | `string` | 否 | 任务名称 |
| `task_action` | `string` | 否 | 任务动作 (Ansible模块名) |
| `result_status` | `'ok' \| 'changed' \| 'failed' \| 'skipped'` | 否 | 结果状态 |
| `stdout` | `string` | 否 | 标准输出 |
| `stderr` | `string` | 否 | 标准错误 |
| `created_at` | `string` (ISO8601) | 是 | 事件时间 |

**TypeScript定义**:
```typescript
export interface JobRunEvent {
  id: string
  job_run_id: string
  node_id?: string
  node_name?: string
  event_type: string
  event_data: Record<string, any>
  task_name?: string
  task_action?: string
  result_status?: 'ok' | 'changed' | 'failed' | 'skipped'
  stdout?: string
  stderr?: string
  created_at: string
}
```

---

## Response Wrappers (响应包装类型)

### PaginatedResponse (分页响应)

**描述**: 包含分页元数据的响应包装器

**字段**:
| 字段名 | 类型 | 必填 | 说明 | 计算逻辑 |
|--------|------|------|------|----------|
| `total` | `number` | 是 | 总记录数 | 后端提供 |
| `page` | `number` | 是 | 当前页码 (从1开始) | 后端提供 |
| `page_size` | `number` | 是 | 每页记录数 | 后端提供 |
| `total_pages` | `number` | 是 | 总页数 | 后端提供 |
| `has_next` | `boolean` | 是 | 是否有下一页 | 前端计算: `page < total_pages` |
| `has_prev` | `boolean` | 是 | 是否有上一页 | 前端计算: `page > 1` |

**TypeScript定义**:
```typescript
export interface PaginatedResponse {
  total: number
  page: number
  page_size: number
  total_pages: number
  has_next: boolean  // 前端补充字段
  has_prev: boolean  // 前端补充字段
}
```

**实现逻辑**:
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

### NodeListResponse (节点列表响应)

**字段**:
```typescript
export interface NodeListResponse {
  nodes: Node[]
  pagination: PaginatedResponse
}
```

---

### NodeGroupListResponse (节点组列表响应)

**字段**:
```typescript
export interface NodeGroupListResponse {
  groups: NodeGroup[]
  pagination: PaginatedResponse
}
```

---

### JobTemplateListResponse (任务模板列表响应)

**字段**:
```typescript
export interface JobTemplateListResponse {
  templates: JobTemplate[]
  pagination: PaginatedResponse
}
```

---

### JobRunListResponse (任务运行列表响应)

**字段**:
```typescript
export interface JobRunListResponse {
  runs: JobRun[]
  pagination: PaginatedResponse
}
```

---

## Validation Schemas (Zod验证模式)

**AcceleratorTypeSchema**:
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

**ConnectionTypeSchema**:
```typescript
export const ConnectionTypeSchema = z.enum(['ssh', 'local', 'winrm']);
```

**NodeStatusSchema**:
```typescript
export const NodeStatusSchema = z.enum([
  'NEW',
  'READY',
  'UNREACHABLE',
  'MAINTENANCE',
  'DECOMMISSIONED'
]);
```

**JobStatusSchema**:
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

**NodeResponseSchema**:
```typescript
export const NodeResponseSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  name: z.string(),
  display_name: z.string(),
  host: z.string(),
  port: z.number().int().min(1).max(65535),
  connection_type: ConnectionTypeSchema,
  ssh_user: z.string(),
  node_type: z.string(),
  labels: z.record(z.string()).optional(),
  tags: z.array(z.string()).optional(),
  status: NodeStatusSchema,
  os_release: z.string().optional(),
  kernel_version: z.string().optional(),
  cpu_cores: z.number().int().positive().optional(),
  cpu_model: z.string().optional(),
  mem_mb: z.number().int().positive().optional(),
  disk_mb: z.number().int().positive().optional(),
  architecture: z.string().optional(),
  last_seen_at: z.string().datetime().optional(),
  last_job_run_at: z.string().datetime().optional(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
  group_ids: z.array(z.string().uuid()),
  group_names: z.array(z.string()),
  accelerator_summary: z.record(AcceleratorTypeSchema, z.number().int().positive()).optional()
});
```

---

## Entity Relationships (实体关系图)

```
┌─────────────────┐
│     Tenant      │
└────────┬────────┘
         │ 1
         │
         │ N
┌────────▼────────┐         ┌─────────────────┐
│      Node       │◄────────┤   Accelerator   │
└────────┬────────┘ 1     N └─────────────────┘
         │
         │ N
         │
         │ N
┌────────▼────────┐
│   NodeGroup     │
└────────┬────────┘
         │ 1
         │
         │ N
┌────────▼────────┐
│    GroupVar     │
└─────────────────┘

┌─────────────────┐
│  JobTemplate    │
└────────┬────────┘
         │ 1
         │
         │ N
┌────────▼────────┐         ┌─────────────────┐
│     JobRun      │◄────────┤  JobRunEvent    │
└────────┬────────┘ 1     N └─────────────────┘
         │
         │ N
         │
         │ 1
┌────────▼────────┐
│      Node       │
└─────────────────┘
```

---

**文档完成日期**: 2026-01-16
**下一步**: Phase 1 - 生成API合约 (contracts/)

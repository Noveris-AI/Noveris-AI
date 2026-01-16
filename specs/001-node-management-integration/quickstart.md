# Quickstart Guide: Node Management Frontend-Backend Integration

**Feature**: 001-node-management-integration
**Last Updated**: 2026-01-16
**Estimated Implementation Time**: 4-6 hours

---

## Overview

本快速入门指南将帮助开发者快速理解并实施节点管理前后端集成的类型对齐修复。修复内容包括：
1. 统一前端枚举类型定义（AcceleratorType, ConnectionType, JobStatus）
2. 添加运行时类型验证（Zod schemas）
3. 重构UI组件配置（AcceleratorIcon, StatusBadge）
4. 补充国际化翻译标签
5. 增强分页响应元数据

---

## Prerequisites (前置条件)

**开发环境**:
- Node.js 18+ (前端开发)
- Python 3.11+ (后端验证，可选)
- Git (版本控制)

**技术栈熟悉度**:
- TypeScript基础
- React组件开发
- Zod验证库基本使用
- i18next国际化

**必读文档**:
- [Feature Specification](spec.md) - 功能需求
- [Research Document](research.md) - 技术决策
- [Data Model](data-model.md) - 数据模型
- [Type Mapping Contract](contracts/type-mapping.md) - 类型映射合约

---

## Implementation Steps (实施步骤)

### Step 1: 更新枚举类型定义 (15分钟)

**文件**: `Frontend/src/features/nodes/api/nodeManagementTypes.ts`

**当前问题**:
```typescript
// ❌ 错误的类型定义
export type AcceleratorType = 'nvidia_gpu' | 'amd_gpu' | 'intel_gpu' | 'huawei_npu' | 'thead_npu' | 'other'
export type ConnectionType = 'ssh' | 'local'  // 缺少winrm
export type JobStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELED'  // 缺少TIMEOUT
```

**修复方案**:
```typescript
// ✅ 正确的类型定义
export type AcceleratorType =
  | 'nvidia_gpu'
  | 'amd_gpu'
  | 'intel_gpu'
  | 'ascend_npu'      // 修正: huawei_npu → ascend_npu
  | 't_head_npu'
  | 'generic_accel'   // 修正: other → generic_accel

export type ConnectionType = 'ssh' | 'local' | 'winrm'  // 添加winrm

export type JobStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELED'
  | 'TIMEOUT'  // 添加TIMEOUT
```

**验证**:
```bash
cd Frontend
npm run type-check  # 应无类型错误
```

---

### Step 2: 创建Zod验证Schemas (20分钟)

**新建文件**: `Frontend/src/features/nodes/api/nodeManagementSchemas.ts`

**实现内容**:
```typescript
import { z } from 'zod';

// 枚举类型Schemas
export const AcceleratorTypeSchema = z.enum([
  'nvidia_gpu',
  'amd_gpu',
  'intel_gpu',
  'ascend_npu',
  't_head_npu',
  'generic_accel'
]);

export const ConnectionTypeSchema = z.enum(['ssh', 'local', 'winrm']);

export const NodeStatusSchema = z.enum([
  'NEW',
  'READY',
  'UNREACHABLE',
  'MAINTENANCE',
  'DECOMMISSIONED'
]);

export const JobStatusSchema = z.enum([
  'PENDING',
  'RUNNING',
  'SUCCEEDED',
  'FAILED',
  'CANCELED',
  'TIMEOUT'
]);

// 优雅降级Schema: 未知加速器类型降级为generic_accel
export const AcceleratorTypeSchemaWithFallback = z.string().transform((val) => {
  const validTypes = AcceleratorTypeSchema.options;
  if (validTypes.includes(val as any)) {
    return val as z.infer<typeof AcceleratorTypeSchema>;
  }
  console.warn(`Unknown accelerator type: ${val}, falling back to generic_accel`);
  return 'generic_accel';
});

// Node响应Schema
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
  accelerator_summary: z.record(AcceleratorTypeSchemaWithFallback, z.number().int().positive()).optional()
});

// Accelerator响应Schema
export const AcceleratorResponseSchema = z.object({
  id: z.string().uuid(),
  node_id: z.string().uuid(),
  type: AcceleratorTypeSchema,
  vendor: z.string(),
  model: z.string(),
  device_id: z.string(),
  slot: z.string().optional(),
  bus_id: z.string().optional(),
  numa_node: z.number().int().optional(),
  memory_mb: z.number().int().positive().optional(),
  cores: z.number().int().positive().optional(),
  mig_capable: z.boolean().optional(),
  mig_mode: z.boolean().optional(),
  compute_capability: z.string().optional(),
  driver_version: z.string().optional(),
  firmware_version: z.string().optional(),
  health_status: z.string().optional(),
  temperature_celsius: z.number().optional(),
  power_usage_watts: z.number().optional(),
  utilization_percent: z.number().min(0).max(100).optional(),
  discovered_at: z.string().datetime()
});

// NodeDetail响应Schema
export const NodeDetailResponseSchema = NodeResponseSchema.extend({
  credentials_exist: z.boolean(),
  bmc_configured: z.boolean(),
  accelerators: z.array(AcceleratorResponseSchema),
  last_facts: z.record(z.any()).optional()
});

// 类型推导
export type NodeResponse = z.infer<typeof NodeResponseSchema>;
export type AcceleratorResponse = z.infer<typeof AcceleratorResponseSchema>;
export type NodeDetailResponse = z.infer<typeof NodeDetailResponseSchema>;
```

**验证**:
```bash
npm run type-check  # 确保无TypeScript错误
```

---

### Step 3: 更新API客户端使用Schemas (25分钟)

**文件**: `Frontend/src/features/nodes/api/nodeManagementClient.ts`

**修改点**:

**3.1 导入Schemas**:
```typescript
import {
  NodeResponseSchema,
  NodeDetailResponseSchema,
  AcceleratorResponseSchema
} from './nodeManagementSchemas';
```

**3.2 在API方法中添加验证** (示例):
```typescript
async getNode(nodeId: string): Promise<NodeDetail> {
  const response = await this.get(`/nodes/${nodeId}`);

  // 运行时验证
  const validatedData = NodeDetailResponseSchema.parse(response.data);
  return validatedData;
}

async listNodes(params: NodeSearchParams): Promise<NodeListResponse> {
  const response = await this.get('/nodes', { params: this.formatParams(params) });

  // 验证每个节点
  const validatedNodes = response.data.nodes.map((node: any) =>
    NodeResponseSchema.parse(node)
  );

  return {
    nodes: validatedNodes,
    pagination: this.enrichPaginationMetadata(response.data)
  };
}
```

**3.3 添加分页字段补充方法**:
```typescript
private enrichPaginationMetadata(apiResponse: any): PaginatedResponse {
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

**验证**:
```bash
# 启动前端开发服务器
npm run dev

# 在浏览器中访问节点列表页，检查控制台无验证错误
```

---

### Step 4: 重构AcceleratorIcon组件 (30分钟)

**文件**: `Frontend/src/features/nodes/components/AcceleratorIcon.tsx`

**当前问题**:
- 使用硬编码的switch语句
- 包含错误的类型值 (`huawei_npu`, `other`)

**修复方案**:

```typescript
import React from 'react';
import { Cpu } from 'lucide-react';
import { AcceleratorType } from '../api/nodeManagementTypes';

// 配置驱动的映射表
interface AcceleratorIconConfig {
  icon: typeof Cpu;
  colorClass: string;
  label: string;
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

// 编译时穷尽性检查
type ConfigKeys = keyof typeof ACCELERATOR_CONFIG;
type AllTypesHandled = AcceleratorType extends ConfigKeys ? true : false;
const _typeCheck: AllTypesHandled = true;

interface AcceleratorIconProps {
  type: AcceleratorType;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

export function AcceleratorIcon({ type, size = 'md', showLabel = false }: AcceleratorIconProps) {
  const config = ACCELERATOR_CONFIG[type];

  if (!config) {
    console.error(`Unknown accelerator type: ${type}`);
    return <Cpu className="text-gray-500" />;
  }

  const Icon = config.icon;
  const sizeClass = size === 'sm' ? 'h-4 w-4' : size === 'md' ? 'h-5 w-5' : 'h-6 w-6';

  return (
    <div className="flex items-center gap-2">
      <Icon className={`${config.colorClass} ${sizeClass}`} />
      {showLabel && <span className="text-sm">{config.label}</span>}
    </div>
  );
}

interface AcceleratorSummaryProps {
  summary: Record<AcceleratorType, number>;
  size?: 'sm' | 'md' | 'lg';
}

export function AcceleratorSummary({ summary, size = 'sm' }: AcceleratorSummaryProps) {
  const entries = Object.entries(summary) as [AcceleratorType, number][];

  if (entries.length === 0) {
    return <span className="text-gray-500 text-sm">No accelerators</span>;
  }

  return (
    <div className="flex items-center gap-3">
      {entries.map(([type, count]) => (
        <div key={type} className="flex items-center gap-1">
          <AcceleratorIcon type={type} size={size} />
          <span className="text-sm font-medium">{count}x</span>
        </div>
      ))}
    </div>
  );
}
```

**验证**:
```bash
npm run test -- AcceleratorIcon.test.tsx  # 运行组件测试
```

---

### Step 5: 更新StatusBadge组件 (15分钟)

**文件**: `Frontend/src/features/nodes/components/StatusBadge.tsx`

**添加TIMEOUT状态处理**:

```typescript
import React from 'react';
import { JobStatus } from '../api/nodeManagementTypes';

const JOB_STATUS_CONFIG: Record<JobStatus, { colorClass: string; label: string }> = {
  PENDING: { colorClass: 'bg-gray-500', label: 'Pending' },
  RUNNING: { colorClass: 'bg-blue-500', label: 'Running' },
  SUCCEEDED: { colorClass: 'bg-green-500', label: 'Succeeded' },
  FAILED: { colorClass: 'bg-red-500', label: 'Failed' },
  CANCELED: { colorClass: 'bg-orange-500', label: 'Canceled' },
  TIMEOUT: { colorClass: 'bg-yellow-500', label: 'Timeout' }  // 新增
};

function assertNever(x: never): never {
  throw new Error(`Unexpected job status: ${x}`);
}

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const config = JOB_STATUS_CONFIG[status];

  if (!config) {
    assertNever(status);  // 穷尽性检查
  }

  return (
    <span className={`px-2 py-1 rounded text-white text-xs font-medium ${config.colorClass}`}>
      {config.label}
    </span>
  );
}
```

---

### Step 6: 补充国际化翻译 (20分钟)

**文件**: `Frontend/src/i18n/locales/zh-CN/node.json`

**修改内容**:
```json
{
  "acceleratorTypes": {
    "nvidia_gpu": "NVIDIA GPU",
    "amd_gpu": "AMD GPU",
    "intel_gpu": "Intel GPU",
    "ascend_npu": "华为昇腾 NPU",
    "t_head_npu": "平头哥 NPU",
    "generic_accel": "通用加速器"
  },
  "connectionTypes": {
    "ssh": "SSH 连接",
    "local": "本地连接",
    "winrm": "WinRM 连接"
  },
  "nodeStatus": {
    "NEW": "新建",
    "READY": "就绪",
    "UNREACHABLE": "不可达",
    "MAINTENANCE": "维护中",
    "DECOMMISSIONED": "已停用"
  },
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

**文件**: `Frontend/src/i18n/locales/en/node.json`

```json
{
  "acceleratorTypes": {
    "nvidia_gpu": "NVIDIA GPU",
    "amd_gpu": "AMD GPU",
    "intel_gpu": "Intel GPU",
    "ascend_npu": "Ascend NPU",
    "t_head_npu": "T-Head NPU",
    "generic_accel": "Generic Accelerator"
  },
  "connectionTypes": {
    "ssh": "SSH Connection",
    "local": "Local Connection",
    "winrm": "WinRM Connection"
  },
  "nodeStatus": {
    "NEW": "New",
    "READY": "Ready",
    "UNREACHABLE": "Unreachable",
    "MAINTENANCE": "Maintenance",
    "DECOMMISSIONED": "Decommissioned"
  },
  "jobStatus": {
    "PENDING": "Pending",
    "RUNNING": "Running",
    "SUCCEEDED": "Succeeded",
    "FAILED": "Failed",
    "CANCELED": "Canceled",
    "TIMEOUT": "Timeout"
  }
}
```

**在组件中使用**:
```typescript
import { useTranslation } from 'react-i18next';

function AcceleratorLabel({ type }: { type: AcceleratorType }) {
  const { t } = useTranslation('node');
  return <span>{t(`acceleratorTypes.${type}`)}</span>;
}
```

---

### Step 7: 编写单元测试 (40分钟)

**新建文件**: `Frontend/tests/unit/features/nodes/api/typeMappings.test.ts`

```typescript
import { describe, it, expect } from 'vitest';
import {
  AcceleratorTypeSchema,
  ConnectionTypeSchema,
  JobStatusSchema,
  AcceleratorTypeSchemaWithFallback
} from '@/features/nodes/api/nodeManagementSchemas';

describe('Type Mappings', () => {
  describe('AcceleratorTypeSchema', () => {
    it('should accept all valid accelerator types', () => {
      const validTypes = [
        'nvidia_gpu',
        'amd_gpu',
        'intel_gpu',
        'ascend_npu',
        't_head_npu',
        'generic_accel'
      ];

      validTypes.forEach((type) => {
        expect(() => AcceleratorTypeSchema.parse(type)).not.toThrow();
      });
    });

    it('should reject invalid accelerator types', () => {
      const invalidTypes = ['huawei_npu', 'other', 'unknown', ''];

      invalidTypes.forEach((type) => {
        expect(() => AcceleratorTypeSchema.parse(type)).toThrow();
      });
    });
  });

  describe('AcceleratorTypeSchemaWithFallback', () => {
    it('should fallback unknown types to generic_accel', () => {
      const result = AcceleratorTypeSchemaWithFallback.parse('unknown_type');
      expect(result).toBe('generic_accel');
    });

    it('should preserve valid types', () => {
      const result = AcceleratorTypeSchemaWithFallback.parse('nvidia_gpu');
      expect(result).toBe('nvidia_gpu');
    });
  });

  describe('ConnectionTypeSchema', () => {
    it('should accept ssh, local, and winrm', () => {
      expect(() => ConnectionTypeSchema.parse('ssh')).not.toThrow();
      expect(() => ConnectionTypeSchema.parse('local')).not.toThrow();
      expect(() => ConnectionTypeSchema.parse('winrm')).not.toThrow();
    });
  });

  describe('JobStatusSchema', () => {
    it('should accept all 6 job statuses including TIMEOUT', () => {
      const validStatuses = [
        'PENDING',
        'RUNNING',
        'SUCCEEDED',
        'FAILED',
        'CANCELED',
        'TIMEOUT'
      ];

      validStatuses.forEach((status) => {
        expect(() => JobStatusSchema.parse(status)).not.toThrow();
      });
    });
  });
});
```

**扩展文件**: `Frontend/tests/unit/features/nodes/components/AcceleratorIcon.test.tsx`

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AcceleratorIcon, AcceleratorSummary } from '@/features/nodes/components/AcceleratorIcon';
import { AcceleratorType } from '@/features/nodes/api/nodeManagementTypes';

describe('AcceleratorIcon', () => {
  const allTypes: AcceleratorType[] = [
    'nvidia_gpu',
    'amd_gpu',
    'intel_gpu',
    'ascend_npu',
    't_head_npu',
    'generic_accel'
  ];

  it('should render all accelerator types without errors', () => {
    allTypes.forEach((type) => {
      const { container } = render(<AcceleratorIcon type={type} />);
      expect(container.querySelector('svg')).toBeInTheDocument();
    });
  });

  it('should show label when showLabel is true', () => {
    render(<AcceleratorIcon type="nvidia_gpu" showLabel={true} />);
    expect(screen.getByText('NVIDIA GPU')).toBeInTheDocument();
  });

  it('should apply correct color classes', () => {
    const { container } = render(<AcceleratorIcon type="ascend_npu" />);
    const icon = container.querySelector('svg');
    expect(icon?.className).toContain('text-rose-600');
  });
});

describe('AcceleratorSummary', () => {
  it('should display multiple accelerator types with counts', () => {
    const summary: Record<AcceleratorType, number> = {
      nvidia_gpu: 2,
      ascend_npu: 1
    };

    render(<AcceleratorSummary summary={summary} />);
    expect(screen.getByText('2x')).toBeInTheDocument();
    expect(screen.getByText('1x')).toBeInTheDocument();
  });

  it('should show "No accelerators" when summary is empty', () => {
    render(<AcceleratorSummary summary={{} as any} />);
    expect(screen.getByText('No accelerators')).toBeInTheDocument();
  });
});
```

**运行测试**:
```bash
npm run test:run  # 运行所有测试
npm run test:ui   # 使用Vitest UI查看测试结果
```

---

## Validation Checklist (验证清单)

在提交代码前，请确保完成以下检查：

- [ ] **类型检查通过**: `npm run type-check` 无错误
- [ ] **所有枚举值已更新**: AcceleratorType, ConnectionType, JobStatus
- [ ] **Zod schemas已创建**: nodeManagementSchemas.ts 文件存在
- [ ] **API客户端已更新**: 使用schemas验证响应
- [ ] **AcceleratorIcon组件已重构**: 使用配置对象，包含所有6种类型
- [ ] **StatusBadge组件已更新**: 支持TIMEOUT状态
- [ ] **i18n翻译已补充**: zh-CN和en两个语言文件
- [ ] **单元测试已编写**: typeMappings.test.ts 和 AcceleratorIcon.test.tsx
- [ ] **测试全部通过**: `npm run test:run` 成功
- [ ] **Lint检查通过**: `npm run lint` 无错误
- [ ] **构建成功**: `npm run build` 无错误
- [ ] **手动测试**: 在浏览器中访问节点列表和详情页，验证显示正确

---

## Troubleshooting (故障排查)

### 问题1: TypeScript编译错误 "Type 'huawei_npu' is not assignable to type AcceleratorType"

**原因**: 代码中仍在使用已废弃的枚举值

**解决**: 全局搜索 `huawei_npu` 和 `other`，替换为 `ascend_npu` 和 `generic_accel`

```bash
# 在Frontend目录执行
grep -r "huawei_npu" src/
grep -r '"other"' src/features/nodes/  # 仅搜索nodes功能目录
```

---

### 问题2: Zod验证错误 "Invalid enum value"

**原因**: API返回了未知的枚举值

**解决**:
1. 检查后端API版本是否最新
2. 使用 `AcceleratorTypeSchemaWithFallback` 代替 `AcceleratorTypeSchema` 实现优雅降级
3. 检查浏览器控制台的警告日志，确认降级逻辑是否触发

---

### 问题3: i18n翻译键找不到

**原因**: 翻译文件路径不正确或键名拼写错误

**解决**:
```typescript
// 确保使用正确的命名空间和键名
const { t } = useTranslation('node');  // 命名空间是 'node'
t('acceleratorTypes.nvidia_gpu')  // 键名是 acceleratorTypes.{type}
```

---

### 问题4: AcceleratorIcon组件显示灰色图标

**原因**: 传入了未知的加速器类型或配置对象缺少该类型

**解决**:
1. 检查 `ACCELERATOR_CONFIG` 对象是否包含所有6种类型
2. 检查传入的 `type` 值是否有效
3. 查看浏览器控制台错误日志

---

## Testing Strategy (测试策略)

**单元测试** (80%覆盖率目标):
- 枚举类型验证 (typeMappings.test.ts)
- Zod schema验证逻辑
- AcceleratorIcon组件渲染
- StatusBadge组件渲染
- 分页字段补充函数

**集成测试** (可选):
- API客户端完整调用流程
- 节点列表页数据加载和显示

**手动测试**:
1. 访问节点列表页 (`/dashboard/nodes`)
2. 验证加速器图标颜色正确
3. 验证节点状态Badge显示正确
4. 切换语言（中文/英文），验证翻译正确
5. 访问节点详情页，验证加速器列表显示
6. 查看任务运行列表，验证TIMEOUT状态显示

---

## Performance Considerations (性能考虑)

**Zod验证性能**:
- Zod验证开销约 0.1-0.5ms per object
- 对于100个节点的列表，总验证时间约 10-50ms，可接受

**优化建议**:
- 仅在开发环境启用详细验证错误日志
- 生产环境使用 `.safeParse()` 避免抛出异常

```typescript
// 生产环境优化示例
const result = NodeResponseSchema.safeParse(data);
if (!result.success) {
  console.error('Validation failed:', result.error);
  // 使用默认值或降级逻辑
}
```

---

## Next Steps (后续步骤)

完成本功能后，建议进行以下后续工作：

1. **监控告警**: 配置Sentry捕获Zod验证失败事件
2. **文档更新**: 更新团队wiki中的类型映射文档
3. **后端对齐**: 向后端团队同步前端类型定义，确保未来枚举添加时同步通知
4. **自动化测试**: 集成到CI/CD流程，确保类型映射始终一致

---

## Resources (参考资源)

- [Zod Official Documentation](https://zod.dev/)
- [React Testing Library](https://testing-library.com/react)
- [i18next Documentation](https://www.i18next.com/)
- [TypeScript Exhaustiveness Checking](https://www.typescriptlang.org/docs/handbook/2/narrowing.html#exhaustiveness-checking)

---

**文档作者**: AI Planning Agent
**最后更新**: 2026-01-16
**预计阅读时间**: 15分钟

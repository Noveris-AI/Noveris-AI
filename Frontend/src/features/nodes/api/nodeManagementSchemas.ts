/**
 * Node Management API Validation Schemas
 *
 * Runtime validation schemas using Zod for type-safe API response parsing
 */

import { z } from 'zod';

// ============================================================================
// Enum Schemas
// ============================================================================

/**
 * Accelerator type schema with all 6 supported types
 */
export const AcceleratorTypeSchema = z.enum([
  'nvidia_gpu',
  'amd_gpu',
  'intel_gpu',
  'ascend_npu',
  't_head_npu',
  'generic_accel'
]);

/**
 * Accelerator type schema with graceful fallback for unknown types
 * Unknown types will be converted to 'generic_accel' with a warning
 */
export const AcceleratorTypeSchemaWithFallback = z.string().transform((val) => {
  const validTypes: Array<z.infer<typeof AcceleratorTypeSchema>> = [
    'nvidia_gpu',
    'amd_gpu',
    'intel_gpu',
    'ascend_npu',
    't_head_npu',
    'generic_accel'
  ];

  if (validTypes.includes(val as any)) {
    return val as z.infer<typeof AcceleratorTypeSchema>;
  }

  console.warn(`Unknown accelerator type: "${val}", falling back to "generic_accel"`);
  return 'generic_accel' as const;
});

/**
 * Connection type schema with SSH, Local, and WinRM support
 */
export const ConnectionTypeSchema = z.enum(['ssh', 'local', 'winrm']);

/**
 * Node status schema with all 5 states
 */
export const NodeStatusSchema = z.enum([
  'NEW',
  'READY',
  'UNREACHABLE',
  'MAINTENANCE',
  'DECOMMISSIONED'
]);

/**
 * Job status schema with all 6 states including TIMEOUT
 */
export const JobStatusSchema = z.enum([
  'PENDING',
  'RUNNING',
  'SUCCEEDED',
  'FAILED',
  'CANCELED',
  'TIMEOUT'
]);

// ============================================================================
// Entity Schemas
// ============================================================================

/**
 * Node response schema
 */
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
  labels: z.record(z.string()).optional().default({}),
  tags: z.array(z.string()).optional().default([]),
  status: NodeStatusSchema,
  os_release: z.string().optional(),
  kernel_version: z.string().optional(),
  cpu_cores: z.number().int().positive().optional(),
  cpu_model: z.string().optional(),
  mem_mb: z.number().int().positive().optional(),
  disk_mb: z.number().int().positive().optional(),
  architecture: z.string().optional(),
  last_seen_at: z.string().optional(),
  last_job_run_at: z.string().optional(),
  created_at: z.string(),
  updated_at: z.string(),
  group_ids: z.array(z.string().uuid()).default([]),
  group_names: z.array(z.string()).default([]),
  accelerator_summary: z.record(
    AcceleratorTypeSchemaWithFallback,
    z.number().int().positive()
  ).optional().default({})
});

/**
 * Accelerator response schema
 */
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
  discovered_at: z.string()
});

/**
 * Node detail response schema (extends NodeResponse)
 */
export const NodeDetailResponseSchema = NodeResponseSchema.extend({
  credentials_exist: z.boolean(),
  bmc_configured: z.boolean(),
  accelerators: z.array(AcceleratorResponseSchema).default([]),
  last_facts: z.record(z.any()).optional()
});

/**
 * Node group response schema
 */
export const NodeGroupResponseSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  name: z.string(),
  display_name: z.string(),
  description: z.string().optional(),
  parent_id: z.string().uuid().optional(),
  priority: z.number().int(),
  is_system: z.boolean(),
  node_count: z.number().int().nonnegative(),
  created_at: z.string(),
  updated_at: z.string(),
  parent_name: z.string().optional(),
  children_names: z.array(z.string()).default([]),
  has_vars: z.boolean()
});

/**
 * Job template response schema
 */
export const JobTemplateResponseSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  name: z.string(),
  display_name: z.string(),
  description: z.string().optional(),
  category: z.string(),
  playbook_path: z.string(),
  become: z.boolean(),
  become_method: z.string().optional(),
  become_user: z.string().optional(),
  timeout_seconds: z.number().int().positive(),
  max_retries: z.number().int().nonnegative(),
  supports_serial: z.boolean(),
  default_serial: z.number().int().positive(),
  default_vars: z.record(z.any()).default({}),
  tags: z.array(z.string()).default([]),
  enabled: z.boolean(),
  is_system: z.boolean(),
  required_roles: z.array(z.string()).default([]),
  version: z.string(),
  author: z.string().optional(),
  documentation_url: z.string().url().optional(),
  created_at: z.string(),
  updated_at: z.string()
});

/**
 * Job run response schema
 */
export const JobRunResponseSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  template_id: z.string().uuid(),
  template_name: z.string().optional(),
  created_by: z.string().uuid(),
  created_by_email: z.string().email().optional(),
  target_type: z.string(),
  status: JobStatusSchema,
  created_at: z.string(),
  started_at: z.string().optional(),
  finished_at: z.string().optional(),
  duration_seconds: z.number().nonnegative().optional(),
  summary: z.record(z.number()).optional(),
  error_message: z.string().optional(),
  artifacts_bucket: z.string().optional(),
  artifacts_prefix: z.string().optional(),
  serial: z.number().int().positive(),
  current_batch: z.number().int().positive().optional(),
  total_batches: z.number().int().positive().optional(),
  worker_id: z.string().optional(),
  node_count: z.number().int().nonnegative()
});

/**
 * Job run detail response schema (extends JobRunResponse)
 */
export const JobRunDetailResponseSchema = JobRunResponseSchema.extend({
  template: JobTemplateResponseSchema.optional(),
  nodes: z.array(NodeResponseSchema).default([]),
  events_count: z.number().int().nonnegative()
});

/**
 * Job run event response schema
 */
export const JobRunEventResponseSchema = z.object({
  id: z.string().uuid(),
  job_run_id: z.string().uuid(),
  seq: z.number().int().nonnegative(),
  ts: z.string(),
  event_type: z.string(),
  hostname: z.string().optional(),
  category: z.string().optional(),
  is_ok: z.boolean().optional(),
  payload: z.record(z.any())
});

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Type guard to check if a value is a valid AcceleratorType
 */
export function isValidAcceleratorType(value: string): value is z.infer<typeof AcceleratorTypeSchema> {
  const validTypes: Array<z.infer<typeof AcceleratorTypeSchema>> = [
    'nvidia_gpu',
    'amd_gpu',
    'intel_gpu',
    'ascend_npu',
    't_head_npu',
    'generic_accel'
  ];
  return validTypes.includes(value as any);
}

/**
 * Type guard to check if a value is a valid ConnectionType
 */
export function isValidConnectionType(value: string): value is z.infer<typeof ConnectionTypeSchema> {
  const validTypes: Array<z.infer<typeof ConnectionTypeSchema>> = ['ssh', 'local', 'winrm'];
  return validTypes.includes(value as any);
}

/**
 * Type guard to check if a value is a valid NodeStatus
 */
export function isValidNodeStatus(value: string): value is z.infer<typeof NodeStatusSchema> {
  const validStatuses: Array<z.infer<typeof NodeStatusSchema>> = [
    'NEW',
    'READY',
    'UNREACHABLE',
    'MAINTENANCE',
    'DECOMMISSIONED'
  ];
  return validStatuses.includes(value as any);
}

/**
 * Type guard to check if a value is a valid JobStatus
 */
export function isValidJobStatus(value: string): value is z.infer<typeof JobStatusSchema> {
  const validStatuses: Array<z.infer<typeof JobStatusSchema>> = [
    'PENDING',
    'RUNNING',
    'SUCCEEDED',
    'FAILED',
    'CANCELED',
    'TIMEOUT'
  ];
  return validStatuses.includes(value as any);
}

// ============================================================================
// Type Exports (for consistency with nodeManagementTypes.ts)
// ============================================================================

export type NodeResponse = z.infer<typeof NodeResponseSchema>;
export type AcceleratorResponse = z.infer<typeof AcceleratorResponseSchema>;
export type NodeDetailResponse = z.infer<typeof NodeDetailResponseSchema>;
export type NodeGroupResponse = z.infer<typeof NodeGroupResponseSchema>;
export type JobTemplateResponse = z.infer<typeof JobTemplateResponseSchema>;
export type JobRunResponse = z.infer<typeof JobRunResponseSchema>;
export type JobRunDetailResponse = z.infer<typeof JobRunDetailResponseSchema>;
export type JobRunEventResponse = z.infer<typeof JobRunEventResponseSchema>;

export type AcceleratorType = z.infer<typeof AcceleratorTypeSchema>;
export type ConnectionType = z.infer<typeof ConnectionTypeSchema>;
export type NodeStatus = z.infer<typeof NodeStatusSchema>;
export type JobStatus = z.infer<typeof JobStatusSchema>;

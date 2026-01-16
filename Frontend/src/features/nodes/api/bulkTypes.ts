/**
 * Bulk Operations API Types
 *
 * TypeScript interfaces for bulk operations and inventory export.
 */

import type { Node } from './nodeManagementTypes'

// Bulk Import Types
export interface BulkNodeImportItem {
  name: string
  host: string
  port?: number
  ssh_user?: string
  connection_type?: 'ssh' | 'local' | 'winrm'
  credential_type?: 'ssh_key' | 'password' | 'winrm'
  ssh_private_key?: string
  password?: string
  group_names?: string[]
  tags?: string[]
  labels?: Record<string, string>
}

export interface BulkNodeImportRequest {
  nodes: BulkNodeImportItem[]
  default_ssh_key?: string
  default_password?: string
  auto_verify?: boolean
  skip_on_error?: boolean
}

export interface BulkNodeImportResponse {
  total_count: number
  imported_count: number
  failed_count: number
  skipped_count: number
  imported_nodes: Node[]
  failed_imports: Array<{
    name: string
    host: string
    error: string
    error_type: string
  }>
  imported_at: string
}

// Bulk Status Update
export interface BulkStatusUpdateRequest {
  node_ids: string[]
  status: 'NEW' | 'READY' | 'UNREACHABLE' | 'MAINTENANCE' | 'DECOMMISSIONED'
  reason?: string
}

// Bulk Group Assignment
export interface BulkGroupAssignRequest {
  node_ids: string[]
  add_group_ids?: string[]
  remove_group_ids?: string[]
  replace_groups?: boolean
}

// Bulk Tag Update
export interface BulkTagUpdateRequest {
  node_ids: string[]
  add_tags?: string[]
  remove_tags?: string[]
}

// Bulk Delete
export interface BulkDeleteRequest {
  node_ids: string[]
  force?: boolean
}

// Generic Bulk Action Response
export interface BulkActionResponse {
  total_count: number
  success_count: number
  failed_count: number
  results: Array<{
    node_id: string
    status: 'success' | 'failed'
    error?: string
    [key: string]: unknown
  }>
  completed_at: string
}

// Inventory Export
export type InventoryFormat = 'yaml' | 'ini' | 'json'

export interface InventoryExportParams {
  format?: InventoryFormat
  node_ids?: string[]
  group_ids?: string[]
  include_vars?: boolean
}

// CSV Import Template
export interface CsvImportParams {
  default_ssh_key?: string
  default_password?: string
  auto_verify?: boolean
}

/**
 * Node Management API Client
 *
 * API client for node management operations.
 * Uses shared BaseApiClient for consistent error handling and configuration.
 */

import { BaseApiClient } from '@shared/lib/apiClient'
import type {
  Node,
  NodeDetail,
  NodeListResponse,
  NodeCreateRequest,
  NodeUpdateRequest,
  NodeSearchParams,
  NodeGroup,
  NodeGroupListResponse,
  NodeGroupCreateRequest,
  GroupVar,
  GroupVarUpdateRequest,
  JobTemplate,
  JobTemplateListResponse,
  JobRun,
  JobRunDetail,
  JobRunListResponse,
  JobRunCreateRequest,
  JobRunSearchParams,
  JobRunEvent,
  DashboardStats,
} from './nodeManagementTypes'

class NodeManagementClient extends BaseApiClient {
  constructor() {
    super('')  // Base path is /api/v1
  }

  // ==========================================================================
  // Nodes
  // ==========================================================================

  async listNodes(params: NodeSearchParams = {}): Promise<NodeListResponse> {
    const queryParams: Record<string, string | number | undefined> = {}

    if (params.page) queryParams.page = params.page
    if (params.page_size) queryParams.page_size = params.page_size
    if (params.search) queryParams.search = params.search
    if (params.status) queryParams.status = params.status
    if (params.accel_type) queryParams.accel_type = params.accel_type
    if (params.group_id) queryParams.group_id = params.group_id
    // Note: tags array handling - join as comma-separated
    if (params.tags?.length) queryParams.tags = params.tags.join(',')

    return this.get<NodeListResponse>('/nodes', queryParams)
  }

  async getNode(nodeId: string): Promise<NodeDetail> {
    return this.get<NodeDetail>(`/nodes/${nodeId}`)
  }

  async createNode(data: NodeCreateRequest): Promise<Node> {
    return this.post<Node>('/nodes', data)
  }

  async updateNode(nodeId: string, data: NodeUpdateRequest): Promise<Node> {
    return this.patch<Node>(`/nodes/${nodeId}`, data)
  }

  async deleteNode(nodeId: string): Promise<void> {
    await this.delete<void>(`/nodes/${nodeId}`)
  }

  async verifyConnectivity(nodeId: string): Promise<{ status: string; message: string }> {
    return this.post<{ status: string; message: string }>(`/nodes/${nodeId}:verify`, {})
  }

  async collectNodeFacts(nodeId: string): Promise<JobRun> {
    return this.post<JobRun>(`/nodes/${nodeId}:collect_facts`, {})
  }

  async runJobOnNode(nodeId: string, data: JobRunCreateRequest): Promise<JobRun> {
    return this.post<JobRun>(`/nodes/${nodeId}:run`, data)
  }

  // ==========================================================================
  // Node Groups
  // ==========================================================================

  async listNodeGroups(page: number = 1, pageSize: number = 20): Promise<NodeGroupListResponse> {
    return this.get<NodeGroupListResponse>('/node-groups', { page, page_size: pageSize })
  }

  async getNodeGroup(groupId: string): Promise<NodeGroup> {
    return this.get<NodeGroup>(`/node-groups/${groupId}`)
  }

  async createNodeGroup(data: NodeGroupCreateRequest): Promise<NodeGroup> {
    return this.post<NodeGroup>('/node-groups', data)
  }

  async updateNodeGroup(groupId: string, data: Partial<NodeGroupCreateRequest>): Promise<NodeGroup> {
    return this.patch<NodeGroup>(`/node-groups/${groupId}`, data)
  }

  async deleteNodeGroup(groupId: string): Promise<void> {
    await this.delete<void>(`/node-groups/${groupId}`)
  }

  async getGroupVars(groupId: string): Promise<GroupVar> {
    return this.get<GroupVar>(`/node-groups/${groupId}/vars`)
  }

  async updateGroupVars(groupId: string, data: GroupVarUpdateRequest): Promise<GroupVar> {
    return this.put<GroupVar>(`/node-groups/${groupId}/vars`, data)
  }

  // ==========================================================================
  // Global Variables
  // ==========================================================================

  async getGlobalVars(): Promise<GroupVar> {
    return this.get<GroupVar>('/group-vars/all')
  }

  async updateGlobalVars(data: GroupVarUpdateRequest): Promise<GroupVar> {
    return this.put<GroupVar>('/group-vars/all', data)
  }

  // ==========================================================================
  // Job Templates
  // ==========================================================================

  async listJobTemplates(
    category?: string,
    enabledOnly: boolean = true
  ): Promise<JobTemplateListResponse> {
    const params: Record<string, string | boolean | undefined> = {
      enabled_only: enabledOnly,
    }
    if (category) params.category = category

    return this.get<JobTemplateListResponse>('/job-templates', params)
  }

  async getJobTemplate(templateId: string): Promise<JobTemplate> {
    return this.get<JobTemplate>(`/job-templates/${templateId}`)
  }

  // ==========================================================================
  // Job Runs
  // ==========================================================================

  async createJobRun(data: JobRunCreateRequest): Promise<JobRun> {
    return this.post<JobRun>('/job-runs', data)
  }

  async listJobRuns(params: JobRunSearchParams = {}): Promise<JobRunListResponse> {
    const queryParams: Record<string, string | number | undefined> = {}

    if (params.page) queryParams.page = params.page
    if (params.page_size) queryParams.page_size = params.page_size
    if (params.status) queryParams.status = params.status
    if (params.template_id) queryParams.template_id = params.template_id
    if (params.node_id) queryParams.node_id = params.node_id

    return this.get<JobRunListResponse>('/job-runs', queryParams)
  }

  async getJobRun(jobRunId: string): Promise<JobRunDetail> {
    return this.get<JobRunDetail>(`/job-runs/${jobRunId}`)
  }

  async cancelJobRun(jobRunId: string, reason?: string): Promise<JobRun> {
    return this.post<JobRun>(`/job-runs/${jobRunId}:cancel`, { reason })
  }

  async getJobRunEvents(jobRunId: string): Promise<{ events: JobRunEvent[]; count: number }> {
    return this.get<{ events: JobRunEvent[]; count: number }>(`/job-runs/${jobRunId}/events`)
  }

  async getJobRunOutput(jobRunId: string): Promise<{ output: string }> {
    return this.get<{ output: string }>(`/job-runs/${jobRunId}/output`)
  }

  // ==========================================================================
  // Statistics
  // ==========================================================================

  async getDashboardStats(): Promise<DashboardStats> {
    return this.get<DashboardStats>('/stats/dashboard')
  }
}

export const nodeManagementClient = new NodeManagementClient()
export default nodeManagementClient

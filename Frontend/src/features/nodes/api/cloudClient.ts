/**
 * Cloud Discovery API Client
 *
 * API client for cloud platform node discovery (AWS, Azure, GCP).
 */

import { BaseApiClient } from '@shared/lib/apiClient'
import type {
  CloudProvider,
  CloudCredentials,
  CloudDiscoveryRequest,
  CloudDiscoveryResponse,
  ValidateCredentialsRequest,
  ValidateCredentialsResponse,
  CloudImportRequest,
  CloudImportResponse,
  ImportDiscoveredRequest,
  ImportDiscoveredResponse,
} from './cloudTypes'

class CloudDiscoveryClient extends BaseApiClient {
  constructor() {
    super('/cloud')
  }

  // ==========================================================================
  // Discovery
  // ==========================================================================

  /**
   * Discover instances from a cloud provider
   */
  async discoverInstances(data: CloudDiscoveryRequest): Promise<CloudDiscoveryResponse> {
    return this.post<CloudDiscoveryResponse>('/discover', data)
  }

  /**
   * Discover instances from AWS
   */
  async discoverAws(
    credentials: {
      access_key_id: string
      secret_access_key: string
      session_token?: string
      region: string
    },
    options: {
      regions?: string[]
      filters?: Record<string, string[]>
      include_stopped?: boolean
    } = {}
  ): Promise<CloudDiscoveryResponse> {
    return this.discoverInstances({
      provider: 'aws',
      credentials,
      ...options,
    })
  }

  /**
   * Discover instances from Azure
   */
  async discoverAzure(
    credentials: {
      subscription_id: string
      client_id: string
      client_secret: string
      tenant_id: string
    },
    options: {
      regions?: string[]
      filters?: Record<string, string[]>
      include_stopped?: boolean
    } = {}
  ): Promise<CloudDiscoveryResponse> {
    return this.discoverInstances({
      provider: 'azure',
      credentials,
      ...options,
    })
  }

  /**
   * Discover instances from GCP
   */
  async discoverGcp(
    credentials: {
      project_id: string
      service_account_json?: string
      credentials_file?: string
    },
    options: {
      regions?: string[]
      filters?: Record<string, string[]>
      include_stopped?: boolean
    } = {}
  ): Promise<CloudDiscoveryResponse> {
    return this.discoverInstances({
      provider: 'gcp',
      credentials,
      ...options,
    })
  }

  // ==========================================================================
  // Credential Validation
  // ==========================================================================

  /**
   * Validate cloud provider credentials
   */
  async validateCredentials(data: ValidateCredentialsRequest): Promise<ValidateCredentialsResponse> {
    return this.post<ValidateCredentialsResponse>('/validate-credentials', data)
  }

  /**
   * Validate AWS credentials
   */
  async validateAwsCredentials(credentials: {
    access_key_id: string
    secret_access_key: string
    session_token?: string
    region: string
  }): Promise<ValidateCredentialsResponse> {
    return this.validateCredentials({
      provider: 'aws',
      credentials,
    })
  }

  /**
   * Validate Azure credentials
   */
  async validateAzureCredentials(credentials: {
    subscription_id: string
    client_id: string
    client_secret: string
    tenant_id: string
  }): Promise<ValidateCredentialsResponse> {
    return this.validateCredentials({
      provider: 'azure',
      credentials,
    })
  }

  /**
   * Validate GCP credentials
   */
  async validateGcpCredentials(credentials: {
    project_id: string
    service_account_json?: string
    credentials_file?: string
  }): Promise<ValidateCredentialsResponse> {
    return this.validateCredentials({
      provider: 'gcp',
      credentials,
    })
  }

  // ==========================================================================
  // Import
  // ==========================================================================

  /**
   * Discover and import nodes in one operation
   */
  async importFromCloud(data: CloudImportRequest): Promise<CloudImportResponse> {
    return this.post<CloudImportResponse>('/import', data)
  }

  /**
   * Import previously discovered instances
   */
  async importDiscoveredInstances(data: ImportDiscoveredRequest): Promise<ImportDiscoveredResponse> {
    return this.post<ImportDiscoveredResponse>('/import-discovered', data)
  }

  // ==========================================================================
  // Helpers
  // ==========================================================================

  /**
   * Get available regions for a cloud provider
   */
  getAvailableRegions(provider: CloudProvider): string[] {
    switch (provider) {
      case 'aws':
        return [
          'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
          'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1', 'eu-north-1',
          'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
          'ap-southeast-1', 'ap-southeast-2',
          'ap-south-1', 'sa-east-1', 'ca-central-1',
          'cn-north-1', 'cn-northwest-1',
        ]
      case 'azure':
        return [
          'eastus', 'eastus2', 'westus', 'westus2', 'westus3',
          'centralus', 'northcentralus', 'southcentralus',
          'westeurope', 'northeurope', 'uksouth', 'ukwest',
          'germanywestcentral', 'francecentral', 'switzerlandnorth',
          'eastasia', 'southeastasia', 'japaneast', 'japanwest',
          'australiaeast', 'australiasoutheast',
          'centralindia', 'southindia', 'brazilsouth',
          'chinanorth', 'chinaeast',
        ]
      case 'gcp':
        return [
          'us-central1', 'us-east1', 'us-east4', 'us-west1', 'us-west2', 'us-west3', 'us-west4',
          'europe-west1', 'europe-west2', 'europe-west3', 'europe-west4', 'europe-west6',
          'europe-north1', 'europe-central2',
          'asia-east1', 'asia-east2', 'asia-northeast1', 'asia-northeast2', 'asia-northeast3',
          'asia-south1', 'asia-south2', 'asia-southeast1', 'asia-southeast2',
          'australia-southeast1', 'australia-southeast2',
          'southamerica-east1', 'southamerica-west1',
        ]
      default:
        return []
    }
  }
}

export const cloudDiscoveryClient = new CloudDiscoveryClient()
export default cloudDiscoveryClient

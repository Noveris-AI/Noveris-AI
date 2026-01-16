"""
Cloud Discovery API Endpoints.

REST API for discovering and importing nodes from cloud providers:
- AWS EC2
- Azure Virtual Machines
- Google Cloud Compute Engine
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.authz.dependencies import RequirePermission
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_tenant_id, get_redis
from app.schemas.node_management import (
    CloudDiscoveryRequest, CloudDiscoveryResponse, CloudDiscoveredNodeResponse,
    CloudNodeImportRequest, CloudNodeImportResponse,
    AWSCredentials, AzureCredentials, GCPCredentials,
    NodeCreate, NodeResponse, PaginatedResponse
)
from app.services.node_management.cloud_inventory_service import (
    CloudInventoryService,
    AWSInventoryProvider,
    AzureInventoryProvider,
    GCPInventoryProvider,
    CloudProviderError,
    CloudCredentialError,
    CloudDiscoveredNode
)
from app.services.node_management.node_service import (
    NodeService, CredentialError
)

from redis.asyncio import Redis

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/cloud", tags=["Cloud Discovery"])


# =============================================================================
# Dependencies
# =============================================================================

async def get_node_service(
    db: AsyncSession = Depends(get_db),
    tenant_id: uuid.UUID = Depends(get_tenant_id),
    redis: Redis = Depends(get_redis)
) -> NodeService:
    """Get NodeService instance with current tenant context."""
    return NodeService(db, tenant_id, redis_client=redis)


def create_cloud_provider(credentials: Dict[str, Any]):
    """Create appropriate cloud provider based on credentials."""
    provider_type = credentials.get("provider")

    if provider_type == "aws":
        return AWSInventoryProvider(
            access_key_id=credentials.get("access_key_id"),
            secret_access_key=credentials.get("secret_access_key"),
            session_token=credentials.get("session_token"),
            region=credentials.get("region", "us-east-1"),
            assume_role_arn=credentials.get("assume_role_arn"),
            profile_name=credentials.get("profile_name"),
        )
    elif provider_type == "azure":
        return AzureInventoryProvider(
            subscription_id=credentials.get("subscription_id"),
            tenant_id=credentials.get("tenant_id"),
            client_id=credentials.get("client_id"),
            client_secret=credentials.get("client_secret"),
            use_managed_identity=credentials.get("use_managed_identity", False),
        )
    elif provider_type == "gcp":
        return GCPInventoryProvider(
            project_id=credentials.get("project_id"),
            credentials_json=credentials.get("credentials_json"),
            service_account_file=credentials.get("service_account_file"),
        )
    else:
        raise ValueError(f"Unknown cloud provider: {provider_type}")


# =============================================================================
# Cloud Discovery Endpoints
# =============================================================================

@router.post(
    "/discover",
    response_model=CloudDiscoveryResponse,
    dependencies=[Depends(RequirePermission("node.cloud.discover"))],
)
async def discover_cloud_instances(
    data: CloudDiscoveryRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Discover instances from a cloud provider.

    Scans the specified cloud provider for running instances and returns
    a list of discovered nodes that can be imported into the system.

    Supported providers:
    - **aws**: Amazon Web Services EC2 instances
    - **azure**: Microsoft Azure Virtual Machines
    - **gcp**: Google Cloud Platform Compute Engine instances

    Filters can be applied to narrow down the discovery:
    - **tags**: Filter by instance tags/labels
    - **vpc_id**: Filter by VPC/VNet (AWS/Azure)
    - **instance_types**: Filter by instance types
    """
    try:
        # Create provider from credentials
        creds_dict = data.credentials.model_dump()
        provider = create_cloud_provider(creds_dict)

        # Validate credentials first
        await provider.validate_credentials()

        # Discover instances
        discovered = await provider.discover_instances(
            filters=data.filters,
            regions=data.regions
        )

        # Convert to response
        nodes = [
            CloudDiscoveredNodeResponse(
                instance_id=node.instance_id,
                name=node.name,
                private_ip=node.private_ip,
                public_ip=node.public_ip,
                platform=node.platform,
                instance_type=node.instance_type,
                region=node.region,
                zone=node.zone,
                state=node.state,
                tags=node.tags,
                labels=node.labels,
                cloud_provider=node.cloud_provider,
                vpc_id=node.vpc_id,
                subnet_id=node.subnet_id,
                security_groups=node.security_groups,
                launch_time=node.launch_time,
                metadata=node.metadata
            )
            for node in discovered
        ]

        # Get unique regions
        regions_scanned = list(set(n.region for n in discovered))

        logger.info(
            "Cloud discovery completed",
            provider=data.provider,
            discovered_count=len(nodes),
            regions=regions_scanned,
            user_id=current_user.user_id
        )

        return CloudDiscoveryResponse(
            provider=data.provider,
            discovered_count=len(nodes),
            regions_scanned=regions_scanned,
            nodes=nodes,
            errors=[],
            discovered_at=datetime.utcnow()
        )

    except CloudCredentialError as e:
        logger.error("Cloud credential error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Cloud credential validation failed: {str(e)}"
        )
    except CloudProviderError as e:
        logger.error("Cloud provider error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Cloud discovery failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Discovery failed: {str(e)}"
        )


@router.post(
    "/validate-credentials",
    dependencies=[Depends(RequirePermission("node.cloud.discover"))],
)
async def validate_cloud_credentials(
    data: CloudDiscoveryRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Validate cloud provider credentials without discovering instances.

    Useful for testing credentials before running a full discovery.
    """
    try:
        creds_dict = data.credentials.model_dump()
        provider = create_cloud_provider(creds_dict)

        await provider.validate_credentials()

        return {
            "valid": True,
            "provider": data.provider,
            "validated_at": datetime.utcnow().isoformat()
        }

    except CloudCredentialError as e:
        return {
            "valid": False,
            "provider": data.provider,
            "error": str(e),
            "validated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/import",
    response_model=CloudNodeImportResponse,
    dependencies=[Depends(RequirePermission("node.cloud.import"))],
)
async def import_cloud_nodes(
    data: CloudNodeImportRequest,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Import discovered cloud instances as managed nodes.

    Takes a list of instance IDs from a previous discovery and creates
    managed nodes for them. Requires SSH/WinRM credentials to be provided
    for the imported nodes.

    Options:
    - **use_public_ip**: Use public IP for connectivity (default: private)
    - **default_ssh_user**: Override default SSH user detection
    - **group_ids**: Add imported nodes to specified groups
    - **auto_verify**: Verify connectivity after import
    """
    # This requires stored discovery results or re-discovery
    # For now, we need to re-discover to get the node details

    imported_nodes = []
    failed_imports = []

    # Note: In production, you'd cache discovery results
    # For now, we create nodes based on provided instance_ids
    # The frontend should pass the discovered node data

    for instance_id in data.instance_ids:
        try:
            # Create node from instance
            # Note: This is simplified - real implementation would
            # use cached discovery data or re-discover
            node_data = NodeCreate(
                name=f"cloud-{instance_id[:8]}",
                display_name=f"Cloud Instance {instance_id}",
                host=instance_id,  # Would be IP from discovery
                port=data.default_port,
                connection_type="winrm" if data.credential_type == "winrm" else "ssh",
                ssh_user=data.default_ssh_user,
                credential_type=data.credential_type,
                ssh_private_key=data.ssh_private_key,
                password=data.password,
                group_ids=data.group_ids,
                labels={
                    "cloud_provider": data.provider,
                    "cloud_instance_id": instance_id,
                    "imported": "true"
                },
                tags=[f"cloud:{data.provider}", "imported"]
            )

            node = await service.create_node(
                node_data,
                uuid.UUID(current_user.user_id)
            )

            # Auto-verify if requested
            if data.auto_verify:
                try:
                    await service.verify_connectivity(
                        node.id,
                        uuid.UUID(current_user.user_id),
                        update_status=True
                    )
                except Exception as verify_err:
                    logger.warning(
                        "Auto-verify failed for imported node",
                        node_id=str(node.id),
                        error=str(verify_err)
                    )

            imported_nodes.append(NodeResponse(
                id=node.id,
                tenant_id=node.tenant_id,
                name=node.name,
                display_name=node.display_name,
                host=node.host,
                port=node.port,
                connection_type=node.connection_type,
                ssh_user=node.ssh_user,
                node_type=node.node_type if node.node_type else "generic",
                labels=node.labels or {},
                tags=node.tags or [],
                status=node.status,
                created_at=node.created_at,
                updated_at=node.updated_at,
                group_ids=[g.id for g in node.groups],
                group_names=[g.name for g in node.groups],
                accelerator_summary={}
            ))

        except CredentialError as e:
            failed_imports.append({
                "instance_id": instance_id,
                "error": str(e),
                "error_type": "credential_error"
            })
        except Exception as e:
            failed_imports.append({
                "instance_id": instance_id,
                "error": str(e),
                "error_type": "import_error"
            })

    logger.info(
        "Cloud import completed",
        imported=len(imported_nodes),
        failed=len(failed_imports),
        user_id=current_user.user_id
    )

    return CloudNodeImportResponse(
        imported_count=len(imported_nodes),
        failed_count=len(failed_imports),
        imported_nodes=imported_nodes,
        failed_imports=failed_imports,
        imported_at=datetime.utcnow()
    )


@router.post(
    "/import-discovered",
    response_model=CloudNodeImportResponse,
    dependencies=[Depends(RequirePermission("node.cloud.import"))],
)
async def import_discovered_nodes(
    discovered_nodes: List[CloudDiscoveredNodeResponse],
    use_public_ip: bool = Query(False),
    default_ssh_user: Optional[str] = Query(None),
    default_port: int = Query(22),
    group_ids: Optional[List[uuid.UUID]] = Query(None),
    credential_type: str = Query("ssh_key"),
    ssh_private_key: Optional[str] = None,
    password: Optional[str] = None,
    auto_verify: bool = Query(True),
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Import nodes from discovery results.

    This endpoint accepts the full discovered node data, avoiding the need
    to re-discover. Use this after the /discover endpoint returns results.
    """
    imported_nodes = []
    failed_imports = []

    for discovered in discovered_nodes:
        try:
            # Determine host IP
            host = discovered.public_ip if use_public_ip else discovered.private_ip
            if not host:
                host = discovered.private_ip or discovered.public_ip

            if not host:
                raise ValueError(f"No IP address for instance {discovered.instance_id}")

            # Determine connection type and defaults
            if discovered.platform.lower() == "windows":
                conn_type = "winrm"
                ssh_user = default_ssh_user or "Administrator"
                port = default_port if default_port != 22 else 5986
                cred_type = "winrm"
            else:
                conn_type = "ssh"
                ssh_user = default_ssh_user or _guess_ssh_user(discovered)
                port = default_port
                cred_type = credential_type

            # Build labels
            labels = {
                "cloud_provider": discovered.cloud_provider,
                "cloud_region": discovered.region,
                "cloud_instance_id": discovered.instance_id,
                "cloud_instance_type": discovered.instance_type,
            }
            if discovered.zone:
                labels["cloud_zone"] = discovered.zone
            if discovered.vpc_id:
                labels["cloud_vpc_id"] = discovered.vpc_id

            # Build tags
            tags = [f"cloud:{discovered.cloud_provider}", f"region:{discovered.region}"]
            tags.extend(list(discovered.tags.keys())[:10])  # Add up to 10 tags

            # Create node
            node_data = NodeCreate(
                name=_sanitize_name(discovered.name or discovered.instance_id),
                display_name=discovered.name or discovered.instance_id,
                host=host,
                port=port,
                connection_type=conn_type,
                ssh_user=ssh_user,
                credential_type=cred_type,
                ssh_private_key=ssh_private_key if cred_type == "ssh_key" else None,
                password=password,
                group_ids=group_ids or [],
                labels=labels,
                tags=tags
            )

            node = await service.create_node(
                node_data,
                uuid.UUID(current_user.user_id)
            )

            # Auto-verify if requested
            if auto_verify:
                try:
                    await service.verify_connectivity(
                        node.id,
                        uuid.UUID(current_user.user_id),
                        update_status=True
                    )
                except Exception as verify_err:
                    logger.warning(
                        "Auto-verify failed",
                        node_id=str(node.id),
                        error=str(verify_err)
                    )

            imported_nodes.append(NodeResponse(
                id=node.id,
                tenant_id=node.tenant_id,
                name=node.name,
                display_name=node.display_name,
                host=node.host,
                port=node.port,
                connection_type=node.connection_type,
                ssh_user=node.ssh_user,
                node_type=node.node_type if node.node_type else "generic",
                labels=node.labels or {},
                tags=node.tags or [],
                status=node.status,
                created_at=node.created_at,
                updated_at=node.updated_at,
                group_ids=[g.id for g in node.groups],
                group_names=[g.name for g in node.groups],
                accelerator_summary={}
            ))

        except Exception as e:
            failed_imports.append({
                "instance_id": discovered.instance_id,
                "name": discovered.name,
                "error": str(e)
            })

    return CloudNodeImportResponse(
        imported_count=len(imported_nodes),
        failed_count=len(failed_imports),
        imported_nodes=imported_nodes,
        failed_imports=failed_imports,
        imported_at=datetime.utcnow()
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _guess_ssh_user(discovered: CloudDiscoveredNodeResponse) -> str:
    """Guess the default SSH user based on platform/name."""
    name_lower = (discovered.name or "").lower()
    tags_str = str(discovered.tags).lower()

    if "ubuntu" in name_lower or "ubuntu" in tags_str:
        return "ubuntu"
    elif "amazon" in name_lower or "amzn" in name_lower:
        return "ec2-user"
    elif "centos" in name_lower or "centos" in tags_str:
        return "centos"
    elif "debian" in name_lower or "debian" in tags_str:
        return "admin"
    elif "rhel" in name_lower or "redhat" in name_lower:
        return "ec2-user"
    elif "suse" in name_lower:
        return "ec2-user"
    else:
        return "root"


def _sanitize_name(name: str) -> str:
    """Sanitize name for use as node name."""
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    if sanitized and not sanitized[0].isalpha():
        sanitized = "node_" + sanitized
    return sanitized[:255]

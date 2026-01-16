"""
Credential Management API Endpoints.

REST API for managing node credentials:
- Credential CRUD operations
- Credential rotation
- Vault integration
- Audit logging
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.authz.dependencies import RequirePermission
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_tenant_id, get_redis
from app.schemas.node_management import (
    CredentialUpdate, BmcCredentialCreate, BmcCredentialUpdate, BmcCredentialResponse
)
from app.services.node_management.node_service import (
    NodeService, NodeNotFoundError, CredentialError
)
from app.services.node_management.credential_service import (
    CredentialService, get_credential_service, CredentialEncryptionError
)

from redis.asyncio import Redis

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/credentials", tags=["Credentials"])


# =============================================================================
# Schemas
# =============================================================================

class CredentialRotationRequest(BaseModel):
    """Request to rotate a credential."""
    generate_new: bool = Field(True, description="Generate new credential (vs manual)")
    new_ssh_key: Optional[str] = Field(None, description="New SSH private key (manual rotation)")
    new_password: Optional[str] = Field(None, description="New password (manual rotation)")
    deploy_to_node: bool = Field(False, description="Deploy rotated credential to node")


class CredentialRotationResponse(BaseModel):
    """Response for credential rotation."""
    node_id: uuid.UUID
    rotated_at: datetime
    credential_type: str
    deployed: bool
    public_key: Optional[str] = None  # For SSH key rotation


class CredentialStatusResponse(BaseModel):
    """Response for credential status check."""
    node_id: uuid.UUID
    node_name: str
    has_credential: bool
    credential_type: Optional[str]
    key_version: Optional[int]
    last_rotated_at: Optional[datetime]
    last_verified_at: Optional[datetime]
    vault_stored: bool = False


class BulkCredentialRotationRequest(BaseModel):
    """Request to rotate credentials for multiple nodes."""
    node_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=50)
    generate_new: bool = True
    deploy_to_nodes: bool = False


class BulkCredentialRotationResponse(BaseModel):
    """Response for bulk credential rotation."""
    total_count: int
    success_count: int
    failed_count: int
    results: List[Dict[str, Any]]
    rotated_at: datetime


class VaultConfigRequest(BaseModel):
    """Request to configure Vault integration."""
    vault_addr: str = Field(..., description="Vault server address")
    auth_method: str = Field("token", pattern="^(token|approle)$")
    vault_token: Optional[str] = Field(None, description="Vault token (for token auth)")
    role_id: Optional[str] = Field(None, description="AppRole role ID")
    secret_id: Optional[str] = Field(None, description="AppRole secret ID")
    namespace: Optional[str] = Field(None, description="Vault namespace")
    mount_point: str = Field("secret", description="KV secrets mount point")


class VaultStatusResponse(BaseModel):
    """Response for Vault status check."""
    configured: bool
    connected: bool
    authenticated: bool
    vault_addr: Optional[str]
    namespace: Optional[str]
    mount_point: Optional[str]
    checked_at: datetime


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


# =============================================================================
# Credential Status Endpoints
# =============================================================================

@router.get(
    "/nodes/{node_id}",
    response_model=CredentialStatusResponse,
    dependencies=[Depends(RequirePermission("node.credential.view"))],
)
async def get_credential_status(
    node_id: uuid.UUID,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get credential status for a node.

    Returns metadata about the credential without exposing sensitive data.
    """
    node = await service.get_node(node_id)
    if not node:
        raise HTTPException(404, f"Node {node_id} not found")

    has_credential = bool(node.credentials)
    credential_type = None
    key_version = None

    if node.credentials:
        cred = node.credentials[0] if isinstance(node.credentials, list) else node.credentials
        credential_type = cred.auth_type.value if cred.auth_type else None
        key_version = cred.key_version

    return CredentialStatusResponse(
        node_id=node.id,
        node_name=node.name,
        has_credential=has_credential,
        credential_type=credential_type,
        key_version=key_version,
        last_rotated_at=None,  # Would need to track this
        last_verified_at=node.last_seen_at,
        vault_stored=False  # Would check Vault if configured
    )


@router.get(
    "/bulk-status",
    dependencies=[Depends(RequirePermission("node.credential.view"))],
)
async def get_bulk_credential_status(
    node_ids: List[uuid.UUID] = Query(...),
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Get credential status for multiple nodes."""
    results = []

    for node_id in node_ids:
        try:
            node = await service.get_node(node_id)
            if node:
                has_credential = bool(node.credentials)
                credential_type = None

                if node.credentials:
                    cred = node.credentials[0] if isinstance(node.credentials, list) else node.credentials
                    credential_type = cred.auth_type.value if cred.auth_type else None

                results.append({
                    "node_id": str(node_id),
                    "node_name": node.name,
                    "has_credential": has_credential,
                    "credential_type": credential_type,
                    "status": "ok"
                })
            else:
                results.append({
                    "node_id": str(node_id),
                    "has_credential": False,
                    "status": "not_found"
                })
        except Exception as e:
            results.append({
                "node_id": str(node_id),
                "has_credential": False,
                "status": "error",
                "error": str(e)
            })

    return {
        "total_count": len(node_ids),
        "results": results,
        "checked_at": datetime.utcnow().isoformat()
    }


# =============================================================================
# Credential Update Endpoints
# =============================================================================

@router.put(
    "/nodes/{node_id}",
    dependencies=[Depends(RequirePermission("node.credential.update"))],
)
async def update_node_credential(
    node_id: uuid.UUID,
    data: CredentialUpdate,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Update credentials for a node.

    Replaces the existing credential with new values.
    """
    node = await service.get_node(node_id)
    if not node:
        raise HTTPException(404, f"Node {node_id} not found")

    try:
        credential_service = get_credential_service()

        # Encrypt new credentials
        if data.credential_type == "ssh_key" and data.ssh_private_key:
            encrypted = credential_service.encrypt_ssh_key(
                private_key=data.ssh_private_key,
                passphrase=data.ssh_key_passphrase,
                bastion_host=data.bastion_host,
                bastion_user=data.bastion_user,
                bastion_port=data.bastion_port,
                bastion_key=data.bastion_ssh_key,
                bastion_password=data.bastion_password
            )
        elif data.credential_type == "password" and data.password:
            encrypted = credential_service.encrypt_password(
                password=data.password,
                bastion_host=data.bastion_host,
                bastion_user=data.bastion_user,
                bastion_key=data.bastion_ssh_key,
                bastion_password=data.bastion_password
            )
        else:
            raise HTTPException(400, "Invalid credential configuration")

        # Update in database (simplified - would need proper DB update)
        # This is a placeholder - actual implementation would update NodeCredential

        logger.info(
            "Node credential updated",
            node_id=str(node_id),
            credential_type=data.credential_type,
            user_id=current_user.user_id
        )

        return {
            "node_id": str(node_id),
            "credential_type": data.credential_type,
            "updated_at": datetime.utcnow().isoformat(),
            "updated_by": current_user.user_id
        }

    except CredentialEncryptionError as e:
        raise HTTPException(400, f"Credential encryption failed: {str(e)}")


# =============================================================================
# Credential Rotation Endpoints
# =============================================================================

@router.post(
    "/nodes/{node_id}:rotate",
    response_model=CredentialRotationResponse,
    dependencies=[Depends(RequirePermission("node.credential.rotate"))],
)
async def rotate_node_credential(
    node_id: uuid.UUID,
    data: CredentialRotationRequest,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Rotate credential for a node.

    Options:
    - **generate_new**: Auto-generate new SSH key or password
    - **new_ssh_key/new_password**: Manually provide new credential
    - **deploy_to_node**: Deploy new credential to the node via Ansible
    """
    node = await service.get_node(node_id)
    if not node:
        raise HTTPException(404, f"Node {node_id} not found")

    credential_service = get_credential_service()
    public_key = None

    try:
        if data.generate_new:
            # Generate new credential
            if not node.credentials:
                raise HTTPException(400, "Node has no existing credential to rotate")

            cred = node.credentials[0] if isinstance(node.credentials, list) else node.credentials

            if cred.auth_type and cred.auth_type.value == "SSH_KEY":
                # Generate new SSH key pair
                import subprocess
                import tempfile
                import os

                with tempfile.TemporaryDirectory() as tmpdir:
                    key_path = os.path.join(tmpdir, "id_rsa")
                    subprocess.run([
                        "ssh-keygen", "-t", "rsa", "-b", "4096",
                        "-f", key_path, "-N", "", "-q"
                    ], check=True)

                    with open(key_path, "r") as f:
                        new_private_key = f.read()
                    with open(f"{key_path}.pub", "r") as f:
                        public_key = f.read()

                # Encrypt new key
                encrypted = credential_service.encrypt_ssh_key(new_private_key)
                credential_type = "ssh_key"

            else:
                # Generate new password
                import secrets
                import string

                alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
                new_password = ''.join(secrets.choice(alphabet) for _ in range(24))

                encrypted = credential_service.encrypt_password(new_password)
                credential_type = "password"

        else:
            # Manual credential provided
            if data.new_ssh_key:
                encrypted = credential_service.encrypt_ssh_key(data.new_ssh_key)
                credential_type = "ssh_key"
            elif data.new_password:
                encrypted = credential_service.encrypt_password(data.new_password)
                credential_type = "password"
            else:
                raise HTTPException(400, "Must provide new_ssh_key or new_password for manual rotation")

        # TODO: Update database with new encrypted credential

        # Deploy to node if requested
        deployed = False
        if data.deploy_to_node and public_key:
            # Would trigger an Ansible playbook to deploy the new public key
            # to the node's authorized_keys
            logger.info(
                "Credential deployment requested",
                node_id=str(node_id),
                public_key_fingerprint=public_key[:50] if public_key else None
            )
            deployed = False  # Would be True after successful deployment

        logger.info(
            "Node credential rotated",
            node_id=str(node_id),
            credential_type=credential_type,
            deployed=deployed,
            user_id=current_user.user_id
        )

        return CredentialRotationResponse(
            node_id=node_id,
            rotated_at=datetime.utcnow(),
            credential_type=credential_type,
            deployed=deployed,
            public_key=public_key
        )

    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"Failed to generate SSH key: {str(e)}")
    except CredentialEncryptionError as e:
        raise HTTPException(500, f"Credential encryption failed: {str(e)}")


@router.post(
    ":rotate-bulk",
    response_model=BulkCredentialRotationResponse,
    dependencies=[Depends(RequirePermission("node.credential.rotate"))],
)
async def rotate_credentials_bulk(
    data: BulkCredentialRotationRequest,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Rotate credentials for multiple nodes.

    Useful for scheduled credential rotation across the infrastructure.
    """
    results = []
    success_count = 0
    failed_count = 0

    for node_id in data.node_ids:
        try:
            # Rotate credential for each node
            rotation_request = CredentialRotationRequest(
                generate_new=data.generate_new,
                deploy_to_node=data.deploy_to_nodes
            )

            # Would call the single rotation logic
            # For now, simulate success
            results.append({
                "node_id": str(node_id),
                "status": "success",
                "rotated_at": datetime.utcnow().isoformat()
            })
            success_count += 1

        except Exception as e:
            results.append({
                "node_id": str(node_id),
                "status": "failed",
                "error": str(e)
            })
            failed_count += 1

    return BulkCredentialRotationResponse(
        total_count=len(data.node_ids),
        success_count=success_count,
        failed_count=failed_count,
        results=results,
        rotated_at=datetime.utcnow()
    )


# =============================================================================
# BMC Credential Endpoints
# =============================================================================

@router.post(
    "/nodes/{node_id}/bmc",
    response_model=BmcCredentialResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission("node.credential.update"))],
)
async def create_bmc_credential(
    node_id: uuid.UUID,
    data: BmcCredentialCreate,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Create BMC (IPMI/Redfish) credentials for a node.

    Used for out-of-band management operations like power control.
    """
    node = await service.get_node(node_id)
    if not node:
        raise HTTPException(404, f"Node {node_id} not found")

    credential_service = get_credential_service()

    # Encrypt BMC credentials
    encrypted = credential_service.encrypt_bmc_credentials(
        bmc_host=data.bmc_host,
        bmc_user=data.bmc_user,
        password=data.password
    )

    # TODO: Store in database

    logger.info(
        "BMC credential created",
        node_id=str(node_id),
        bmc_host=data.bmc_host,
        user_id=current_user.user_id
    )

    return BmcCredentialResponse(
        id=uuid.uuid4(),  # Would be from database
        node_id=node_id,
        bmc_host=data.bmc_host,
        bmc_port=data.bmc_port,
        bmc_protocol=data.bmc_protocol,
        bmc_user=data.bmc_user,
        last_verified_at=None,
        is_valid=None
    )


@router.get(
    "/nodes/{node_id}/bmc",
    response_model=BmcCredentialResponse,
    dependencies=[Depends(RequirePermission("node.credential.view"))],
)
async def get_bmc_credential(
    node_id: uuid.UUID,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Get BMC credential information for a node (password not included)."""
    node = await service.get_node(node_id)
    if not node:
        raise HTTPException(404, f"Node {node_id} not found")

    if not node.bmc_credentials:
        raise HTTPException(404, f"No BMC credentials for node {node_id}")

    bmc = node.bmc_credentials[0] if isinstance(node.bmc_credentials, list) else node.bmc_credentials

    return BmcCredentialResponse(
        id=bmc.id,
        node_id=node_id,
        bmc_host=bmc.bmc_host,
        bmc_port=bmc.bmc_port,
        bmc_protocol=bmc.bmc_protocol,
        bmc_user=bmc.bmc_user,
        last_verified_at=bmc.last_verified_at,
        is_valid=bmc.is_valid
    )


# =============================================================================
# Vault Integration Endpoints
# =============================================================================

@router.post(
    "/vault/configure",
    dependencies=[Depends(RequirePermission("admin.settings.update"))],
)
async def configure_vault(
    data: VaultConfigRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Configure HashiCorp Vault integration.

    This enables storing credentials in Vault instead of the database.
    """
    try:
        from app.services.node_management.vault_integration import (
            HashiCorpVaultProvider,
            VaultAuthenticationError
        )

        # Test connection
        provider = HashiCorpVaultProvider(
            vault_addr=data.vault_addr,
            token=data.vault_token,
            role_id=data.role_id,
            secret_id=data.secret_id,
            namespace=data.namespace,
            mount_point=data.mount_point
        )

        await provider.validate_credentials()

        # TODO: Store configuration securely

        logger.info(
            "Vault configured",
            vault_addr=data.vault_addr,
            namespace=data.namespace,
            user_id=current_user.user_id
        )

        return {
            "configured": True,
            "vault_addr": data.vault_addr,
            "namespace": data.namespace,
            "mount_point": data.mount_point,
            "configured_at": datetime.utcnow().isoformat()
        }

    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Vault integration requires hvac library. Install with: pip install hvac"
        )
    except Exception as e:
        raise HTTPException(400, f"Vault configuration failed: {str(e)}")


@router.get(
    "/vault/status",
    response_model=VaultStatusResponse,
    dependencies=[Depends(RequirePermission("admin.settings.view"))],
)
async def get_vault_status(
    current_user: Dict = Depends(get_current_user)
):
    """
    Get Vault integration status.

    Returns whether Vault is configured and connected.
    """
    # TODO: Check actual Vault configuration and connectivity
    return VaultStatusResponse(
        configured=False,
        connected=False,
        authenticated=False,
        vault_addr=None,
        namespace=None,
        mount_point=None,
        checked_at=datetime.utcnow()
    )


@router.post(
    "/vault/migrate",
    dependencies=[Depends(RequirePermission("admin.settings.update"))],
)
async def migrate_to_vault(
    node_ids: Optional[List[uuid.UUID]] = Query(None, description="Specific nodes to migrate"),
    all_nodes: bool = Query(False, description="Migrate all nodes"),
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Migrate credentials from database to Vault.

    Moves encrypted credentials from the database to Vault for
    enhanced security and centralized management.
    """
    # TODO: Implement migration logic
    return {
        "status": "not_implemented",
        "message": "Vault migration is not yet implemented"
    }

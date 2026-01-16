"""
Bulk Operations and Inventory Export API Endpoints.

REST API for bulk node management and inventory export:
- Bulk node import from CSV/JSON
- Bulk actions (status update, group assignment)
- Inventory export in various formats (YAML, INI, JSON)
"""

import csv
import io
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import yaml

from app.authz.dependencies import RequirePermission
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_tenant_id, get_redis
from app.schemas.node_management import (
    NodeCreate, NodeResponse, NodeStatus, PaginationParams
)
from app.services.node_management.node_service import (
    NodeService, NodeNotFoundError, CredentialError
)

from redis.asyncio import Redis

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/bulk", tags=["Bulk Operations"])


# =============================================================================
# Schemas
# =============================================================================

class BulkNodeImportItem(BaseModel):
    """Single node for bulk import."""
    name: str
    host: str
    port: int = 22
    ssh_user: Optional[str] = "root"
    connection_type: str = "ssh"
    credential_type: str = "ssh_key"
    ssh_private_key: Optional[str] = None
    password: Optional[str] = None
    group_names: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    labels: Optional[Dict[str, str]] = None


class BulkNodeImportRequest(BaseModel):
    """Request for bulk node import."""
    nodes: List[BulkNodeImportItem] = Field(..., min_items=1, max_items=500)
    default_ssh_key: Optional[str] = Field(None, description="Default SSH key for all nodes")
    default_password: Optional[str] = Field(None, description="Default password for all nodes")
    auto_verify: bool = Field(True, description="Verify connectivity after import")
    skip_on_error: bool = Field(True, description="Continue importing if one fails")


class BulkNodeImportResponse(BaseModel):
    """Response for bulk node import."""
    total_count: int
    imported_count: int
    failed_count: int
    skipped_count: int
    imported_nodes: List[NodeResponse]
    failed_imports: List[Dict[str, Any]]
    imported_at: datetime


class BulkStatusUpdateRequest(BaseModel):
    """Request to update status for multiple nodes."""
    node_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=100)
    status: str = Field(..., pattern="^(NEW|READY|UNREACHABLE|MAINTENANCE|DECOMMISSIONED)$")
    reason: Optional[str] = Field(None, description="Reason for status change")


class BulkGroupAssignRequest(BaseModel):
    """Request to assign nodes to groups."""
    node_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=100)
    add_group_ids: Optional[List[uuid.UUID]] = Field(None, description="Groups to add nodes to")
    remove_group_ids: Optional[List[uuid.UUID]] = Field(None, description="Groups to remove nodes from")
    replace_groups: bool = Field(False, description="Replace all groups with add_group_ids")


class BulkTagUpdateRequest(BaseModel):
    """Request to update tags for multiple nodes."""
    node_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=100)
    add_tags: Optional[List[str]] = Field(None, description="Tags to add")
    remove_tags: Optional[List[str]] = Field(None, description="Tags to remove")


class BulkDeleteRequest(BaseModel):
    """Request to delete multiple nodes."""
    node_ids: List[uuid.UUID] = Field(..., min_items=1, max_items=100)
    force: bool = Field(False, description="Force delete even if nodes have active jobs")


class BulkActionResponse(BaseModel):
    """Generic response for bulk actions."""
    total_count: int
    success_count: int
    failed_count: int
    results: List[Dict[str, Any]]
    completed_at: datetime


class InventoryExportRequest(BaseModel):
    """Request for inventory export."""
    format: str = Field("yaml", pattern="^(yaml|ini|json)$")
    node_ids: Optional[List[uuid.UUID]] = Field(None, description="Specific nodes to export")
    group_ids: Optional[List[uuid.UUID]] = Field(None, description="Export nodes in these groups")
    include_credentials: bool = Field(False, description="Include credential paths in export")
    include_vars: bool = Field(True, description="Include group variables")


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
# Bulk Import Endpoints
# =============================================================================

@router.post(
    "/import",
    response_model=BulkNodeImportResponse,
    dependencies=[Depends(RequirePermission("node.node.create"))],
)
async def bulk_import_nodes(
    data: BulkNodeImportRequest,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Import multiple nodes at once.

    Supports up to 500 nodes per request. Each node can have individual
    credentials or use the default SSH key/password provided.
    """
    imported_nodes = []
    failed_imports = []
    skipped_count = 0

    for item in data.nodes:
        try:
            # Determine credentials
            ssh_key = item.ssh_private_key or data.default_ssh_key
            password = item.password or data.default_password

            if item.credential_type == "ssh_key" and not ssh_key:
                if data.skip_on_error:
                    failed_imports.append({
                        "name": item.name,
                        "host": item.host,
                        "error": "No SSH key provided",
                        "error_type": "missing_credential"
                    })
                    continue
                else:
                    raise CredentialError(f"No SSH key for node {item.name}")

            if item.credential_type == "password" and not password:
                if data.skip_on_error:
                    failed_imports.append({
                        "name": item.name,
                        "host": item.host,
                        "error": "No password provided",
                        "error_type": "missing_credential"
                    })
                    continue
                else:
                    raise CredentialError(f"No password for node {item.name}")

            # Create node
            node_data = NodeCreate(
                name=item.name,
                host=item.host,
                port=item.port,
                ssh_user=item.ssh_user,
                connection_type=item.connection_type,
                credential_type=item.credential_type,
                ssh_private_key=ssh_key if item.credential_type == "ssh_key" else None,
                password=password if item.credential_type == "password" else None,
                tags=item.tags or [],
                labels=item.labels or {},
                group_ids=[]  # Would resolve group_names to IDs
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
                except Exception:
                    pass  # Don't fail import on verification error

            imported_nodes.append(NodeResponse(
                id=node.id,
                tenant_id=node.tenant_id,
                name=node.name,
                display_name=node.display_name,
                host=node.host,
                port=node.port,
                connection_type=node.connection_type.value,
                ssh_user=node.ssh_user,
                node_type=node.node_type.value if node.node_type else "generic",
                labels=node.labels or {},
                tags=node.tags or [],
                status=node.status.value,
                created_at=node.created_at,
                updated_at=node.updated_at,
                group_ids=[],
                group_names=[],
                accelerator_summary={}
            ))

        except CredentialError as e:
            if data.skip_on_error:
                failed_imports.append({
                    "name": item.name,
                    "host": item.host,
                    "error": str(e),
                    "error_type": "credential_error"
                })
            else:
                raise HTTPException(400, str(e))
        except Exception as e:
            if data.skip_on_error:
                failed_imports.append({
                    "name": item.name,
                    "host": item.host,
                    "error": str(e),
                    "error_type": "import_error"
                })
            else:
                raise HTTPException(500, f"Import failed: {str(e)}")

    logger.info(
        "Bulk import completed",
        total=len(data.nodes),
        imported=len(imported_nodes),
        failed=len(failed_imports),
        user_id=current_user.user_id
    )

    return BulkNodeImportResponse(
        total_count=len(data.nodes),
        imported_count=len(imported_nodes),
        failed_count=len(failed_imports),
        skipped_count=skipped_count,
        imported_nodes=imported_nodes,
        failed_imports=failed_imports,
        imported_at=datetime.utcnow()
    )


@router.post(
    "/import/csv",
    response_model=BulkNodeImportResponse,
    dependencies=[Depends(RequirePermission("node.node.create"))],
)
async def bulk_import_from_csv(
    file: UploadFile = File(...),
    default_ssh_key: Optional[str] = Query(None),
    default_password: Optional[str] = Query(None),
    auto_verify: bool = Query(True),
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Import nodes from CSV file.

    CSV format:
    name,host,port,ssh_user,connection_type,credential_type,tags

    Example:
    server1,192.168.1.10,22,root,ssh,ssh_key,"tag1,tag2"
    server2,192.168.1.11,22,ubuntu,ssh,password,"prod"
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "File must be a CSV file")

    content = await file.read()
    decoded = content.decode('utf-8')

    # Parse CSV
    reader = csv.DictReader(io.StringIO(decoded))
    nodes = []

    for row in reader:
        tags = row.get('tags', '').split(',') if row.get('tags') else []
        tags = [t.strip() for t in tags if t.strip()]

        nodes.append(BulkNodeImportItem(
            name=row.get('name', '').strip(),
            host=row.get('host', '').strip(),
            port=int(row.get('port', 22)),
            ssh_user=row.get('ssh_user', 'root').strip(),
            connection_type=row.get('connection_type', 'ssh').strip(),
            credential_type=row.get('credential_type', 'ssh_key').strip(),
            tags=tags
        ))

    # Use standard import
    request = BulkNodeImportRequest(
        nodes=nodes,
        default_ssh_key=default_ssh_key,
        default_password=default_password,
        auto_verify=auto_verify,
        skip_on_error=True
    )

    return await bulk_import_nodes(request, service, current_user)


# =============================================================================
# Bulk Action Endpoints
# =============================================================================

@router.post(
    "/status",
    response_model=BulkActionResponse,
    dependencies=[Depends(RequirePermission("node.node.update"))],
)
async def bulk_update_status(
    data: BulkStatusUpdateRequest,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Update status for multiple nodes.

    Useful for putting nodes into maintenance or marking as decommissioned.
    """
    results = []
    success_count = 0

    from app.schemas.node_management import NodeUpdate

    for node_id in data.node_ids:
        try:
            update = NodeUpdate(status=data.status)
            await service.update_node(
                node_id,
                update,
                uuid.UUID(current_user.user_id)
            )
            results.append({
                "node_id": str(node_id),
                "status": "success",
                "new_status": data.status
            })
            success_count += 1
        except NodeNotFoundError:
            results.append({
                "node_id": str(node_id),
                "status": "failed",
                "error": "Node not found"
            })
        except Exception as e:
            results.append({
                "node_id": str(node_id),
                "status": "failed",
                "error": str(e)
            })

    return BulkActionResponse(
        total_count=len(data.node_ids),
        success_count=success_count,
        failed_count=len(data.node_ids) - success_count,
        results=results,
        completed_at=datetime.utcnow()
    )


@router.post(
    "/groups",
    response_model=BulkActionResponse,
    dependencies=[Depends(RequirePermission("node.node.update"))],
)
async def bulk_assign_groups(
    data: BulkGroupAssignRequest,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Assign nodes to groups in bulk.

    Options:
    - Add nodes to additional groups
    - Remove nodes from specific groups
    - Replace all group assignments
    """
    results = []
    success_count = 0

    from app.schemas.node_management import NodeUpdate

    for node_id in data.node_ids:
        try:
            node = await service.get_node(node_id)
            if not node:
                results.append({
                    "node_id": str(node_id),
                    "status": "failed",
                    "error": "Node not found"
                })
                continue

            # Calculate new group IDs
            current_group_ids = set(g.id for g in node.groups)

            if data.replace_groups:
                new_group_ids = set(data.add_group_ids or [])
            else:
                new_group_ids = current_group_ids.copy()
                if data.add_group_ids:
                    new_group_ids.update(data.add_group_ids)
                if data.remove_group_ids:
                    new_group_ids -= set(data.remove_group_ids)

            # Update node
            update = NodeUpdate(group_ids=list(new_group_ids))
            await service.update_node(
                node_id,
                update,
                uuid.UUID(current_user.user_id)
            )

            results.append({
                "node_id": str(node_id),
                "status": "success",
                "group_count": len(new_group_ids)
            })
            success_count += 1

        except Exception as e:
            results.append({
                "node_id": str(node_id),
                "status": "failed",
                "error": str(e)
            })

    return BulkActionResponse(
        total_count=len(data.node_ids),
        success_count=success_count,
        failed_count=len(data.node_ids) - success_count,
        results=results,
        completed_at=datetime.utcnow()
    )


@router.post(
    "/tags",
    response_model=BulkActionResponse,
    dependencies=[Depends(RequirePermission("node.node.update"))],
)
async def bulk_update_tags(
    data: BulkTagUpdateRequest,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Update tags for multiple nodes."""
    results = []
    success_count = 0

    from app.schemas.node_management import NodeUpdate

    for node_id in data.node_ids:
        try:
            node = await service.get_node(node_id)
            if not node:
                results.append({
                    "node_id": str(node_id),
                    "status": "failed",
                    "error": "Node not found"
                })
                continue

            # Calculate new tags
            current_tags = set(node.tags or [])

            if data.add_tags:
                current_tags.update(data.add_tags)
            if data.remove_tags:
                current_tags -= set(data.remove_tags)

            # Update node
            update = NodeUpdate(tags=list(current_tags))
            await service.update_node(
                node_id,
                update,
                uuid.UUID(current_user.user_id)
            )

            results.append({
                "node_id": str(node_id),
                "status": "success",
                "tag_count": len(current_tags)
            })
            success_count += 1

        except Exception as e:
            results.append({
                "node_id": str(node_id),
                "status": "failed",
                "error": str(e)
            })

    return BulkActionResponse(
        total_count=len(data.node_ids),
        success_count=success_count,
        failed_count=len(data.node_ids) - success_count,
        results=results,
        completed_at=datetime.utcnow()
    )


@router.post(
    "/delete",
    response_model=BulkActionResponse,
    dependencies=[Depends(RequirePermission("node.node.delete"))],
)
async def bulk_delete_nodes(
    data: BulkDeleteRequest,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Delete multiple nodes.

    By default, nodes are soft-deleted (decommissioned).
    """
    results = []
    success_count = 0

    for node_id in data.node_ids:
        try:
            await service.delete_node(
                node_id,
                uuid.UUID(current_user.user_id)
            )
            results.append({
                "node_id": str(node_id),
                "status": "success"
            })
            success_count += 1

        except NodeNotFoundError:
            results.append({
                "node_id": str(node_id),
                "status": "failed",
                "error": "Node not found"
            })
        except Exception as e:
            results.append({
                "node_id": str(node_id),
                "status": "failed",
                "error": str(e)
            })

    return BulkActionResponse(
        total_count=len(data.node_ids),
        success_count=success_count,
        failed_count=len(data.node_ids) - success_count,
        results=results,
        completed_at=datetime.utcnow()
    )


# =============================================================================
# Inventory Export Endpoints
# =============================================================================

inventory_router = APIRouter(prefix="/inventory", tags=["Inventory Export"])


@inventory_router.get(
    "/export",
    dependencies=[Depends(RequirePermission("node.node.view"))],
)
async def export_inventory(
    format: str = Query("yaml", pattern="^(yaml|ini|json)$"),
    node_ids: Optional[List[uuid.UUID]] = Query(None),
    group_ids: Optional[List[uuid.UUID]] = Query(None),
    include_vars: bool = Query(True),
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Export inventory in various formats.

    Formats:
    - **yaml**: Ansible YAML inventory
    - **ini**: Ansible INI inventory
    - **json**: JSON format for programmatic use
    """
    # Generate inventory content
    inventory_yaml = await service.generate_inventory(
        node_ids=node_ids,
        group_ids=group_ids
    )

    # Get group vars if requested
    group_vars = {}
    if include_vars:
        group_vars = await service.generate_group_vars(group_ids=group_ids)

    if format == "yaml":
        content = inventory_yaml
        if include_vars and group_vars:
            content += "\n# Group Variables\n"
            content += yaml.dump({"group_vars": group_vars}, default_flow_style=False)

        return Response(
            content=content,
            media_type="application/x-yaml",
            headers={
                "Content-Disposition": "attachment; filename=inventory.yml"
            }
        )

    elif format == "ini":
        # Convert YAML to INI format
        inventory_data = yaml.safe_load(inventory_yaml)
        ini_content = _convert_to_ini(inventory_data)

        return Response(
            content=ini_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": "attachment; filename=inventory.ini"
            }
        )

    elif format == "json":
        import json
        inventory_data = yaml.safe_load(inventory_yaml)
        inventory_data["group_vars"] = group_vars

        return Response(
            content=json.dumps(inventory_data, indent=2, default=str),
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=inventory.json"
            }
        )


@inventory_router.get(
    "/template",
    dependencies=[Depends(RequirePermission("node.node.view"))],
)
async def get_import_template():
    """
    Get CSV template for bulk import.

    Returns a sample CSV file that can be used as a template for bulk imports.
    """
    template = """name,host,port,ssh_user,connection_type,credential_type,tags
server1,192.168.1.10,22,root,ssh,ssh_key,"production,web"
server2,192.168.1.11,22,ubuntu,ssh,password,"staging"
win-server1,192.168.1.20,5986,Administrator,winrm,winrm,"windows,production"
"""

    return Response(
        content=template,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=node_import_template.csv"
        }
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _convert_to_ini(inventory_data: Dict) -> str:
    """Convert YAML inventory data to INI format."""
    lines = []

    # All hosts
    all_hosts = inventory_data.get("all", {}).get("hosts", {})
    if all_hosts:
        lines.append("[all]")
        for host_name, host_vars in all_hosts.items():
            var_parts = [f"{k}={v}" for k, v in host_vars.items()]
            lines.append(f"{host_name} {' '.join(var_parts)}")
        lines.append("")

    # Group children
    children = inventory_data.get("all", {}).get("children", {})
    for group_name, group_data in children.items():
        lines.append(f"[{group_name}]")
        group_hosts = group_data.get("hosts", {})
        for host_name in group_hosts:
            lines.append(host_name)
        lines.append("")

    return "\n".join(lines)

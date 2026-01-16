"""
Node Management API Endpoints.

REST API for managing nodes, groups, credentials, job templates, and job runs.
All endpoints require authentication and use session/cookie-based auth.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.authz.dependencies import RequirePermission, RequireModule
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_tenant_id, get_redis
from app.models.node import NodeStatus, JobStatus, AcceleratorType
from app.schemas.node_management import (
    NodeCreate, NodeUpdate, NodeResponse, NodeDetailResponse, NodeListResponse,
    NodeGroupCreate, NodeGroupUpdate, NodeGroupResponse, NodeGroupListResponse,
    GroupVarCreate, GroupVarUpdate, GroupVarResponse,
    JobTemplateResponse, JobTemplateListResponse,
    JobRunCreate, JobRunResponse, JobRunDetailResponse, JobRunListResponse,
    JobRunCancel, JobRunEventResponse,
    AcceleratorResponse, AcceleratorListResponse,
    NodeFactsResponse, AuditLogResponse, AuditLogListResponse,
    ConnectivityCheckCreate, ConnectivityCheckResponse, BulkConnectivityCheckResponse,
    FactsCollectionCreate, DriverInstallCreate,
    NodeStatsResponse, JobStatsResponse, DashboardStatsResponse,
    PaginationParams, PaginatedResponse,
    CredentialUpdate, BmcCredentialCreate, BmcCredentialUpdate, BmcCredentialResponse
)
from app.services.node_management.node_service import (
    NodeService, NodeNotFoundError, CredentialError, JobExecutionError
)

from redis.asyncio import Redis


logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/nodes", tags=["Node Management"])


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
# Node Endpoints
# =============================================================================

@router.get(
    "",
    response_model=NodeListResponse,
    dependencies=[Depends(RequirePermission("node.node.view"))],
)
async def list_nodes(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=255),
    status: Optional[str] = Query(None),
    accel_type: Optional[str] = Query(None),
    group_id: Optional[uuid.UUID] = Query(None),
    tags: Optional[List[str]] = Query(None),
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    List nodes with filtering and pagination.

    - **search**: Search by name, host, or display_name
    - **status**: Filter by node status (NEW, READY, UNREACHABLE, MAINTENANCE, DECOMMISSIONED)
    - **accel_type**: Filter by accelerator type (nvidia_gpu, amd_gpu, etc.)
    - **group_id**: Filter by node group
    - **tags**: Filter by tags (all tags must match)
    """
    pagination = PaginationParams(page=page, page_size=page_size)

    # Parse status
    node_status = None
    if status:
        try:
            node_status = NodeStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    # Parse accelerator type
    accelerator_type = None
    if accel_type:
        try:
            accelerator_type = AcceleratorType(accel_type)
        except ValueError:
            raise HTTPException(400, f"Invalid accelerator type: {accel_type}")

    nodes, total = await service.list_nodes(
        pagination=pagination,
        search=search,
        status=node_status,
        accel_type=accelerator_type,
        group_id=group_id,
        tags=tags
    )

    # Convert to response
    node_responses = []
    for node in nodes:
        accel_summary = {}
        for acc in node.accelerators:
            acc_type = acc.type.value
            accel_summary[acc_type] = accel_summary.get(acc_type, 0) + 1

        node_responses.append(NodeResponse(
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
            os_release=node.os_release,
            kernel_version=node.kernel_version,
            cpu_cores=node.cpu_cores,
            cpu_model=node.cpu_model,
            mem_mb=node.mem_mb,
            disk_mb=node.disk_mb,
            architecture=node.architecture,
            last_seen_at=node.last_seen_at,
            last_job_run_at=node.last_job_run_at,
            created_at=node.created_at,
            updated_at=node.updated_at,
            group_ids=[g.id for g in node.groups],
            group_names=[g.name for g in node.groups],
            accelerator_summary=accel_summary
        ))

    return NodeListResponse(
        nodes=node_responses,
        pagination=PaginatedResponse.create(total, page, page_size)
    )


@router.post(
    "",
    response_model=NodeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission("node.node.create"))],
)
async def create_node(
    request: Request,
    data: NodeCreate,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Create a new managed node.

    Requires SSH credentials (key or password) to connect to the node.
    """
    try:
        node = await service.create_node(data, uuid.UUID(current_user.user_id))

        return NodeResponse(
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
            group_ids=[g.id for g in node.groups],
            group_names=[g.name for g in node.groups],
            accelerator_summary={}
        )
    except CredentialError as e:
        raise HTTPException(400, str(e))


@router.get(
    "/{node_id}",
    response_model=NodeDetailResponse,
    dependencies=[Depends(RequirePermission("node.node.view"))],
)
async def get_node(
    node_id: uuid.UUID,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Get detailed node information."""
    node = await service.get_node(node_id)
    if not node:
        raise HTTPException(404, f"Node {node_id} not found")

    # Build accelerator list
    accelerators = [
        AcceleratorResponse(
            id=acc.id,
            node_id=acc.node_id,
            type=acc.type.value,
            vendor=acc.vendor,
            model=acc.model,
            device_id=acc.device_id,
            slot=acc.slot,
            bus_id=acc.bus_id,
            numa_node=acc.numa_node,
            memory_mb=acc.memory_mb,
            cores=acc.cores,
            mig_capable=acc.mig_capable,
            mig_mode=acc.mig_mode,
            compute_capability=acc.compute_capability,
            driver_version=acc.driver_version,
            firmware_version=acc.firmware_version,
            health_status=acc.health_status,
            temperature_celsius=acc.temperature_celsius,
            power_usage_watts=acc.power_usage_watts,
            utilization_percent=acc.utilization_percent,
            discovered_at=acc.discovered_at
        )
        for acc in node.accelerators
    ]

    # Get latest facts
    last_facts = None
    if node.fact_snapshots:
        latest_snapshot = node.fact_snapshots[0]
        last_facts = latest_snapshot.facts

    return NodeDetailResponse(
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
        os_release=node.os_release,
        kernel_version=node.kernel_version,
        cpu_cores=node.cpu_cores,
        cpu_model=node.cpu_model,
        mem_mb=node.mem_mb,
        disk_mb=node.disk_mb,
        architecture=node.architecture,
        last_seen_at=node.last_seen_at,
        last_job_run_at=node.last_job_run_at,
        created_at=node.created_at,
        updated_at=node.updated_at,
        group_ids=[g.id for g in node.groups],
        group_names=[g.name for g in node.groups],
        accelerator_summary={acc.type.value: 1 for acc in node.accelerators},
        credentials_exist=node.credentials is not None,
        bmc_configured=node.bmc_credentials is not None,
        accelerators=accelerators,
        last_facts=last_facts
    )


@router.patch(
    "/{node_id}",
    response_model=NodeResponse,
    dependencies=[Depends(RequirePermission("node.node.update"))],
)
async def update_node(
    node_id: uuid.UUID,
    data: NodeUpdate,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Update node properties."""
    try:
        node = await service.update_node(node_id, data, uuid.UUID(current_user.user_id))

        return NodeResponse(
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
            os_release=node.os_release,
            kernel_version=node.kernel_version,
            cpu_cores=node.cpu_cores,
            cpu_model=node.cpu_model,
            mem_mb=node.mem_mb,
            disk_mb=node.disk_mb,
            architecture=node.architecture,
            last_seen_at=node.last_seen_at,
            last_job_run_at=node.last_job_run_at,
            created_at=node.created_at,
            updated_at=node.updated_at,
            group_ids=[g.id for g in node.groups],
            group_names=[g.name for g in node.groups],
            accelerator_summary={}
        )
    except NodeNotFoundError:
        raise HTTPException(404, f"Node {node_id} not found")


@router.delete(
    "/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission("node.node.delete"))],
)
async def delete_node(
    node_id: uuid.UUID,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Decommission a node (soft delete).

    The node will be marked as DECOMMISSIONED but not removed from the database.
    """
    try:
        await service.delete_node(node_id, uuid.UUID(current_user.user_id))
    except NodeNotFoundError:
        raise HTTPException(404, f"Node {node_id} not found")


# =============================================================================
# Node Connectivity Verification
# =============================================================================

@router.post(
    "/{node_id}:verify",
    response_model=ConnectivityCheckResponse,
    dependencies=[Depends(RequirePermission("node.node.execute"))],
)
async def verify_node_connectivity(
    node_id: uuid.UUID,
    update_status: bool = Query(True, description="Update node status based on result"),
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Verify connectivity to a node.

    Tests TCP port connectivity and SSH authentication.
    Updates node status to READY or UNREACHABLE based on result.
    """
    try:
        result = await service.verify_connectivity(
            node_id,
            uuid.UUID(current_user.user_id),
            update_status=update_status
        )
        return ConnectivityCheckResponse(**result)
    except NodeNotFoundError:
        raise HTTPException(404, f"Node {node_id} not found")


@router.post(
    ":verify-bulk",
    response_model=BulkConnectivityCheckResponse,
    dependencies=[Depends(RequirePermission("node.node.execute"))],
)
async def verify_nodes_connectivity_bulk(
    data: ConnectivityCheckCreate,
    update_status: bool = Query(True, description="Update node status based on result"),
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Verify connectivity for multiple nodes.

    Tests all nodes concurrently and returns aggregated results.
    Updates node statuses to READY or UNREACHABLE based on results.
    """
    result = await service.verify_connectivity_bulk(
        data.node_ids,
        uuid.UUID(current_user.user_id),
        update_status=update_status
    )
    return BulkConnectivityCheckResponse(
        checked_count=result["checked_count"],
        reachable_count=result["reachable_count"],
        unreachable_count=result["unreachable_count"],
        results=[ConnectivityCheckResponse(**r) for r in result["results"]],
        checked_at=result["checked_at"]
    )


# =============================================================================
# Node Actions
# =============================================================================

@router.post(
    "/{node_id}:collect_facts",
    response_model=JobRunResponse,
    dependencies=[Depends(RequirePermission("node.node.execute"))],
)
async def collect_node_facts(
    node_id: uuid.UUID,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Trigger facts collection for a node."""
    # Get collect_facts template
    templates = await service.list_job_templates(category="discovery")
    collect_facts_template = next(
        (t for t in templates if "collect_facts" in t.name.lower()),
        None
    )

    if not collect_facts_template:
        raise HTTPException(500, "collect_facts template not found")

    # Create job run
    job_data = JobRunCreate(
        template_id=collect_facts_template.id,
        target_type="node",
        target_node_ids=[node_id],
        extra_vars={}
    )

    try:
        job_run = await service.create_job_run(
            job_data,
            uuid.UUID(current_user.user_id),
            current_user.email
        )
        return _job_run_to_response(job_run)
    except JobExecutionError as e:
        raise HTTPException(400, str(e))


@router.post(
    "/{node_id}:run",
    response_model=JobRunResponse,
    dependencies=[Depends(RequirePermission("node.node.execute"))],
)
async def run_job_on_node(
    node_id: uuid.UUID,
    data: JobRunCreate,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Run a job template on a specific node."""
    # Override target to this specific node
    data.target_type = "node"
    data.target_node_ids = [node_id]
    data.target_group_ids = None

    try:
        job_run = await service.create_job_run(
            data,
            uuid.UUID(current_user.user_id),
            current_user.email
        )
        return _job_run_to_response(job_run)
    except JobExecutionError as e:
        raise HTTPException(400, str(e))


# =============================================================================
# Node Groups
# =============================================================================

node_groups_router = APIRouter(prefix="/node-groups", tags=["Node Groups"])


@node_groups_router.get(
    "",
    response_model=NodeGroupListResponse,
    dependencies=[Depends(RequirePermission("node.group.view"))],
)
async def list_node_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """List all node groups."""
    pagination = PaginationParams(page=page, page_size=page_size)
    groups, total = await service.list_groups(pagination)

    return NodeGroupListResponse(
        groups=[
            NodeGroupResponse(
                id=g.id,
                tenant_id=g.tenant_id,
                name=g.name,
                display_name=g.display_name,
                description=g.description,
                parent_id=g.parent_id,
                priority=g.priority,
                is_system=g.is_system,
                node_count=len(g.nodes),
                created_at=g.created_at,
                updated_at=g.updated_at,
                parent_name=g.parent.name if g.parent else None,
                children_names=[c.name for c in g.children] if hasattr(g, 'children') else [],
                has_vars=len(g.group_vars) > 0 if g.group_vars else False
            )
            for g in groups
        ],
        pagination=PaginatedResponse.create(total, page, page_size)
    )


@node_groups_router.post(
    "",
    response_model=NodeGroupResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission("node.group.create"))],
)
async def create_node_group(
    data: NodeGroupCreate,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Create a new node group."""
    group = await service.create_group(data, uuid.UUID(current_user.user_id))

    return NodeGroupResponse(
        id=group.id,
        tenant_id=group.tenant_id,
        name=group.name,
        display_name=group.display_name,
        description=group.description,
        parent_id=group.parent_id,
        priority=group.priority,
        is_system=group.is_system,
        node_count=len(group.nodes) if group.nodes else 0,
        created_at=group.created_at,
        updated_at=group.updated_at
    )


@node_groups_router.get(
    "/{group_id}/vars",
    response_model=GroupVarResponse,
    dependencies=[Depends(RequirePermission("node.group.view"))],
)
async def get_group_vars(
    group_id: uuid.UUID,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Get variables for a specific group."""
    group_var = await service.get_group_vars(group_id)
    if not group_var:
        # Return empty vars
        return GroupVarResponse(
            id=uuid.uuid4(),
            tenant_id=service.tenant_id,
            scope="group",
            group_id=group_id,
            vars={},
            version=0,
            updated_by=None,
            change_description=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    return GroupVarResponse(
        id=group_var.id,
        tenant_id=group_var.tenant_id,
        scope=group_var.scope,
        group_id=group_var.group_id,
        vars=group_var.vars,
        version=group_var.version,
        updated_by=group_var.updated_by,
        change_description=group_var.change_description,
        created_at=group_var.created_at,
        updated_at=group_var.updated_at
    )


@node_groups_router.put(
    "/{group_id}/vars",
    response_model=GroupVarResponse,
    dependencies=[Depends(RequirePermission("node.group.update"))],
)
async def update_group_vars(
    group_id: uuid.UUID,
    data: GroupVarUpdate,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Update variables for a specific group."""
    group_var = await service.set_group_vars(group_id, data, uuid.UUID(current_user.user_id))

    return GroupVarResponse(
        id=group_var.id,
        tenant_id=group_var.tenant_id,
        scope=group_var.scope,
        group_id=group_var.group_id,
        vars=group_var.vars,
        version=group_var.version,
        updated_by=group_var.updated_by,
        change_description=group_var.change_description,
        created_at=group_var.created_at,
        updated_at=group_var.updated_at
    )


# =============================================================================
# Global Variables
# =============================================================================

group_vars_router = APIRouter(prefix="/group-vars", tags=["Group Variables"])


@group_vars_router.get(
    "/all",
    response_model=GroupVarResponse,
    dependencies=[Depends(RequirePermission("node.group.view"))],
)
async def get_global_vars(
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Get global (all) variables."""
    group_var = await service.get_global_vars()
    if not group_var:
        return GroupVarResponse(
            id=uuid.uuid4(),
            tenant_id=service.tenant_id,
            scope="all",
            group_id=None,
            vars={},
            version=0,
            updated_by=None,
            change_description=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    return GroupVarResponse(
        id=group_var.id,
        tenant_id=group_var.tenant_id,
        scope=group_var.scope,
        group_id=group_var.group_id,
        vars=group_var.vars,
        version=group_var.version,
        updated_by=group_var.updated_by,
        change_description=group_var.change_description,
        created_at=group_var.created_at,
        updated_at=group_var.updated_at
    )


@group_vars_router.put(
    "/all",
    response_model=GroupVarResponse,
    dependencies=[Depends(RequirePermission("node.group.update"))],
)
async def update_global_vars(
    data: GroupVarCreate,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Update global (all) variables."""
    group_var = await service.set_global_vars(data, uuid.UUID(current_user.user_id))

    return GroupVarResponse(
        id=group_var.id,
        tenant_id=group_var.tenant_id,
        scope=group_var.scope,
        group_id=group_var.group_id,
        vars=group_var.vars,
        version=group_var.version,
        updated_by=group_var.updated_by,
        change_description=group_var.change_description,
        created_at=group_var.created_at,
        updated_at=group_var.updated_at
    )


# =============================================================================
# Job Templates
# =============================================================================

job_templates_router = APIRouter(prefix="/job-templates", tags=["Job Templates"])


@job_templates_router.get(
    "",
    response_model=JobTemplateListResponse,
    dependencies=[Depends(RequirePermission("node.template.view"))],
)
async def list_job_templates(
    category: Optional[str] = Query(None),
    enabled_only: bool = Query(True),
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """List available job templates."""
    templates = await service.list_job_templates(
        category=category,
        enabled_only=enabled_only
    )

    return JobTemplateListResponse(
        templates=[
            JobTemplateResponse(
                id=t.id,
                tenant_id=t.tenant_id,
                name=t.name,
                display_name=t.display_name,
                description=t.description,
                category=t.category,
                playbook_path=t.playbook_path,
                become=t.become,
                become_method=t.become_method,
                become_user=t.become_user,
                timeout_seconds=t.timeout_seconds,
                max_retries=t.max_retries,
                supports_serial=t.supports_serial,
                default_serial=t.default_serial,
                default_vars=t.default_vars or {},
                tags=t.tags or [],
                enabled=t.enabled,
                is_system=t.is_system,
                required_roles=t.required_roles or [],
                version=t.version,
                author=t.author,
                documentation_url=t.documentation_url,
                created_at=t.created_at,
                updated_at=t.updated_at
            )
            for t in templates
        ],
        pagination=PaginatedResponse.create(len(templates), 1, 100)
    )


@job_templates_router.get(
    "/{template_id}",
    response_model=JobTemplateResponse,
    dependencies=[Depends(RequirePermission("node.template.view"))],
)
async def get_job_template(
    template_id: uuid.UUID,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Get a job template by ID."""
    template = await service.get_job_template(template_id)
    if not template:
        raise HTTPException(404, f"Template {template_id} not found")

    return JobTemplateResponse(
        id=template.id,
        tenant_id=template.tenant_id,
        name=template.name,
        display_name=template.display_name,
        description=template.description,
        category=template.category,
        playbook_path=template.playbook_path,
        become=template.become,
        become_method=template.become_method,
        become_user=template.become_user,
        timeout_seconds=template.timeout_seconds,
        max_retries=template.max_retries,
        supports_serial=template.supports_serial,
        default_serial=template.default_serial,
        default_vars=template.default_vars or {},
        tags=template.tags or [],
        enabled=template.enabled,
        is_system=template.is_system,
        required_roles=template.required_roles or [],
        version=template.version,
        author=template.author,
        documentation_url=template.documentation_url,
        created_at=template.created_at,
        updated_at=template.updated_at
    )


# =============================================================================
# Job Runs
# =============================================================================

job_runs_router = APIRouter(prefix="/job-runs", tags=["Job Runs"])


@job_runs_router.post(
    "",
    response_model=JobRunResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission("node.job.execute"))],
)
async def create_job_run(
    data: JobRunCreate,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Create and queue a new job run."""
    try:
        job_run = await service.create_job_run(
            data,
            uuid.UUID(current_user.user_id),
            current_user.email
        )
        return _job_run_to_response(job_run)
    except JobExecutionError as e:
        raise HTTPException(400, str(e))


@job_runs_router.get(
    "",
    response_model=JobRunListResponse,
    dependencies=[Depends(RequirePermission("node.job.view"))],
)
async def list_job_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    template_id: Optional[uuid.UUID] = Query(None),
    node_id: Optional[uuid.UUID] = Query(None),
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """List job runs with filtering."""
    pagination = PaginationParams(page=page, page_size=page_size)

    job_status = None
    if status:
        try:
            job_status = JobStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")

    runs, total = await service.list_job_runs(
        pagination=pagination,
        status=job_status,
        template_id=template_id,
        node_id=node_id
    )

    return JobRunListResponse(
        runs=[_job_run_to_response(r) for r in runs],
        pagination=PaginatedResponse.create(total, page, page_size)
    )


@job_runs_router.get(
    "/{job_run_id}",
    response_model=JobRunDetailResponse,
    dependencies=[Depends(RequirePermission("node.job.view"))],
)
async def get_job_run(
    job_run_id: uuid.UUID,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Get job run details."""
    job_run = await service.get_job_run(job_run_id)
    if not job_run:
        raise HTTPException(404, f"Job run {job_run_id} not found")

    return _job_run_to_detail_response(job_run)


@job_runs_router.post(
    "/{job_run_id}:cancel",
    response_model=JobRunResponse,
    dependencies=[Depends(RequirePermission("node.job.cancel"))],
)
async def cancel_job_run(
    job_run_id: uuid.UUID,
    data: JobRunCancel,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Cancel a running or pending job."""
    try:
        job_run = await service.cancel_job_run(
            job_run_id,
            uuid.UUID(current_user.user_id),
            data.reason
        )
        return _job_run_to_response(job_run)
    except JobExecutionError as e:
        raise HTTPException(400, str(e))


@job_runs_router.get(
    "/{job_run_id}/events",
    dependencies=[Depends(RequirePermission("node.job.view"))],
)
async def get_job_run_events(
    job_run_id: uuid.UUID,
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """
    Get job run events (for log display).

    Use SSE for real-time streaming when job is running.
    """
    job_run = await service.get_job_run(job_run_id)
    if not job_run:
        raise HTTPException(404, f"Job run {job_run_id} not found")

    events = [
        JobRunEventResponse(
            id=e.id,
            job_run_id=e.job_run_id,
            seq=e.seq,
            ts=e.ts,
            event_type=e.event_type,
            hostname=e.hostname,
            category=e.category,
            is_ok=e.is_ok,
            payload=e.payload
        )
        for e in job_run.events
    ]

    return {"events": events, "count": len(events)}


# =============================================================================
# Statistics / Dashboard
# =============================================================================

stats_router = APIRouter(prefix="/stats", tags=["Statistics"])


@stats_router.get(
    "/dashboard",
    response_model=DashboardStatsResponse,
    dependencies=[Depends(RequirePermission("node.node.view"))],
)
async def get_dashboard_stats(
    service: NodeService = Depends(get_node_service),
    current_user: Dict = Depends(get_current_user)
):
    """Get dashboard statistics."""
    node_stats = await service.get_node_stats()
    job_stats = await service.get_job_stats()

    # Count accelerators
    total_accel = sum(node_stats.get("by_accelerator", {}).values())

    return DashboardStatsResponse(
        nodes=NodeStatsResponse(**node_stats),
        jobs=JobStatsResponse(**job_stats),
        accelerators=node_stats.get("by_accelerator", {}),
        total_accelerators=total_accel
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _job_run_to_response(job_run) -> JobRunResponse:
    """Convert JobRun model to response schema."""
    return JobRunResponse(
        id=job_run.id,
        tenant_id=job_run.tenant_id,
        template_id=job_run.template_id,
        template_name=job_run.template.name if job_run.template else None,
        created_by=job_run.created_by,
        created_by_email=job_run.created_by_email,
        target_type=job_run.target_type,
        status=job_run.status.value,
        created_at=job_run.created_at,
        started_at=job_run.started_at,
        finished_at=job_run.finished_at,
        duration_seconds=job_run.duration_seconds,
        summary=job_run.summary,
        error_message=job_run.error_message,
        artifacts_bucket=job_run.artifacts_bucket,
        artifacts_prefix=job_run.artifacts_prefix,
        serial=job_run.serial,
        current_batch=job_run.current_batch,
        total_batches=job_run.total_batches,
        worker_id=job_run.worker_id,
        node_count=len(job_run.nodes) if job_run.nodes else 0
    )


def _job_run_to_detail_response(job_run) -> JobRunDetailResponse:
    """Convert JobRun model to detail response schema."""
    base = _job_run_to_response(job_run)

    return JobRunDetailResponse(
        **base.model_dump(),
        template=JobTemplateResponse(
            id=job_run.template.id,
            tenant_id=job_run.template.tenant_id,
            name=job_run.template.name,
            display_name=job_run.template.display_name,
            description=job_run.template.description,
            category=job_run.template.category,
            playbook_path=job_run.template.playbook_path,
            become=job_run.template.become,
            become_method=job_run.template.become_method,
            become_user=job_run.template.become_user,
            timeout_seconds=job_run.template.timeout_seconds,
            max_retries=job_run.template.max_retries,
            supports_serial=job_run.template.supports_serial,
            default_serial=job_run.template.default_serial,
            default_vars=job_run.template.default_vars or {},
            tags=job_run.template.tags or [],
            enabled=job_run.template.enabled,
            is_system=job_run.template.is_system,
            required_roles=job_run.template.required_roles or [],
            version=job_run.template.version,
            author=job_run.template.author,
            documentation_url=job_run.template.documentation_url,
            created_at=job_run.template.created_at,
            updated_at=job_run.template.updated_at
        ) if job_run.template else None,
        nodes=[
            NodeResponse(
                id=n.id,
                tenant_id=n.tenant_id,
                name=n.name,
                display_name=n.display_name,
                host=n.host,
                port=n.port,
                connection_type=n.connection_type.value,
                ssh_user=n.ssh_user,
                node_type=n.node_type.value if n.node_type else "generic",
                labels=n.labels or {},
                tags=n.tags or [],
                status=n.status.value,
                created_at=n.created_at,
                updated_at=n.updated_at,
                group_ids=[],
                group_names=[],
                accelerator_summary={}
            )
            for n in job_run.nodes
        ] if job_run.nodes else [],
        events_count=len(job_run.events) if job_run.events else 0
    )


# =============================================================================
# Register All Routers
# =============================================================================

# Main nodes router is already defined above
# These additional routers need to be included in main.py

__all__ = [
    "router",
    "node_groups_router",
    "group_vars_router",
    "job_templates_router",
    "job_runs_router",
    "stats_router"
]

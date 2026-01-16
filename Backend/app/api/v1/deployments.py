"""
Model Deployment API Routes.

Provides endpoints for creating, managing, and monitoring model deployments.
Supports vLLM, SGLang, and Xinference frameworks.

Reference documentation:
- vLLM: https://docs.vllm.ai/en/latest/getting_started/quickstart/
- SGLang: https://docs.sglang.io/
- Xinference: https://inference.readthedocs.io/en/latest/getting_started/using_xinference.html
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.authz.dependencies import RequirePermission
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.deployment import DeploymentStatus, DeploymentFramework
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentUpdate,
    DeploymentResponse,
    DeploymentDetailResponse,
    DeploymentListResponse,
    DeploymentLogResponse,
    DeploymentLogListResponse,
    DeploymentActionResponse,
    DeploymentHealthResponse,
    CompatibilityCheckRequest,
    CompatibilityCheckResponse,
    FrameworkCompatibility,
    NodeAcceleratorsResponse,
    AcceleratorDevice,
    QuickDeployRequest,
    QuickDeployResponse,
    FrameworkConfigTemplatesResponse,
    FrameworkConfigTemplate,
    LogStreamResponse,
    LogLine,
    PaginatedResponse,
)
from app.services.deployment import DeploymentService, CompatibilityEvaluator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deployments", tags=["deployments"])


# =============================================================================
# Helper Functions
# =============================================================================

def get_deployment_service(
    db: AsyncSession,
    current_user: User,
) -> DeploymentService:
    """Get deployment service instance."""
    # For now, use a default tenant_id (in production, extract from user/session)
    tenant_id = getattr(current_user, 'tenant_id', None) or uuid.uuid4()
    return DeploymentService(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        user_email=current_user.email,
    )


def deployment_to_response(deployment, node_info: dict = None) -> DeploymentResponse:
    """Convert deployment model to response schema."""
    return DeploymentResponse(
        id=deployment.id,
        tenant_id=deployment.tenant_id,
        name=deployment.name,
        display_name=deployment.display_name,
        description=deployment.description,
        framework=deployment.framework.value,
        deployment_mode=deployment.deployment_mode.value,
        node_id=deployment.node_id,
        model_source=deployment.model_source.value,
        model_repo_id=deployment.model_repo_id,
        model_revision=deployment.model_revision,
        model_local_path=deployment.model_local_path,
        host=deployment.host,
        port=deployment.port,
        served_model_name=deployment.served_model_name,
        gpu_devices=deployment.gpu_devices,
        tensor_parallel_size=deployment.tensor_parallel_size,
        gpu_memory_utilization=deployment.gpu_memory_utilization,
        env_table=deployment.env_table or [],
        args_table=deployment.args_table or [],
        status=deployment.status.value,
        health_status=deployment.health_status or "unknown",
        last_health_check_at=deployment.last_health_check_at,
        error_message=deployment.error_message,
        endpoints=deployment.endpoints or {},
        labels=deployment.labels or {},
        tags=deployment.tags or [],
        created_by=deployment.created_by,
        created_by_email=deployment.created_by_email,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
        started_at=deployment.started_at,
        stopped_at=deployment.stopped_at,
        node_name=node_info.get("name") if node_info else (deployment.node.name if deployment.node else None),
        node_host=node_info.get("host") if node_info else (deployment.node.host if deployment.node else None),
    )


# =============================================================================
# Deployment CRUD
# =============================================================================

@router.get(
    "",
    response_model=DeploymentListResponse,
    dependencies=[Depends(RequirePermission("deployment.deployment.view"))],
)
async def list_deployments(
    status: Optional[str] = Query(None, description="Filter by status"),
    framework: Optional[str] = Query(None, description="Filter by framework"),
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
    search: Optional[str] = Query(None, description="Search term"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeploymentListResponse:
    """
    List deployments with filtering and pagination.

    - **status**: Filter by deployment status (PENDING, RUNNING, STOPPED, etc.)
    - **framework**: Filter by framework (vllm, sglang, xinference)
    - **node_id**: Filter by node ID
    - **search**: Search in name, display_name, model_repo_id
    """
    service = get_deployment_service(db, current_user)

    # Parse filters
    status_enum = DeploymentStatus(status) if status else None
    framework_enum = DeploymentFramework(framework) if framework else None
    node_uuid = uuid.UUID(node_id) if node_id else None

    deployments, total = await service.list_deployments(
        page=page,
        page_size=page_size,
        status=status_enum,
        framework=framework_enum,
        node_id=node_uuid,
        search=search,
    )

    return DeploymentListResponse(
        deployments=[deployment_to_response(d) for d in deployments],
        pagination=PaginatedResponse.create(total, page, page_size),
    )


@router.post(
    "",
    response_model=DeploymentResponse,
    status_code=201,
    dependencies=[Depends(RequirePermission("deployment.deployment.create"))],
)
async def create_deployment(
    data: DeploymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeploymentResponse:
    """
    Create a new model deployment.

    Creates a deployment configuration and triggers the deployment pipeline:
    1. Validates node compatibility
    2. Allocates a port
    3. Stores configuration
    4. Triggers async deployment worker (model download, framework install, service start)
    """
    service = get_deployment_service(db, current_user)

    try:
        deployment = await service.create_deployment(data)
        await db.commit()
        return deployment_to_response(deployment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/templates",
    response_model=FrameworkConfigTemplatesResponse,
    dependencies=[Depends(RequirePermission("deployment.deployment.view"))],
)
async def get_framework_templates(
    current_user: User = Depends(get_current_user),
) -> FrameworkConfigTemplatesResponse:
    """
    Get recommended configuration templates for each framework.

    Returns recommended environment variables and CLI arguments for
    vLLM, SGLang, and Xinference.
    """
    # Static templates
    templates = [
        FrameworkConfigTemplate(
            framework="vllm",
            description="High-performance LLM inference with vLLM",
            recommended_args=[
                {"key": "--max-model-len", "value": "4096", "arg_type": "int", "enabled": True},
                {"key": "--gpu-memory-utilization", "value": "0.9", "arg_type": "float", "enabled": True},
                {"key": "--enable-prefix-caching", "value": "", "arg_type": "bool", "enabled": False},
            ],
            recommended_env=[
                {"name": "VLLM_ATTENTION_BACKEND", "value": "FLASHINFER", "is_sensitive": False},
            ],
            documentation_url="https://docs.vllm.ai/en/latest/getting_started/quickstart/",
        ),
        FrameworkConfigTemplate(
            framework="sglang",
            description="Fast serving with RadixAttention",
            recommended_args=[
                {"key": "--mem-fraction-static", "value": "0.9", "arg_type": "float", "enabled": True},
                {"key": "--chunked-prefill-size", "value": "4096", "arg_type": "int", "enabled": True},
            ],
            recommended_env=[],
            documentation_url="https://docs.sglang.io/",
        ),
        FrameworkConfigTemplate(
            framework="xinference",
            description="Multi-framework inference platform",
            recommended_args=[
                {"key": "--n-gpu", "value": "auto", "arg_type": "string", "enabled": True},
            ],
            recommended_env=[
                {"name": "XINFERENCE_MODEL_SRC", "value": "huggingface", "is_sensitive": False},
            ],
            documentation_url="https://inference.readthedocs.io/en/latest/getting_started/using_xinference.html",
        ),
    ]

    return FrameworkConfigTemplatesResponse(templates=templates)


@router.get(
    "/{deployment_id}",
    response_model=DeploymentDetailResponse,
    dependencies=[Depends(RequirePermission("deployment.deployment.view"))],
)
async def get_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeploymentDetailResponse:
    """
    Get deployment details by ID.

    Returns full deployment information including service configuration,
    systemd paths, job tracking, and recent logs.
    """
    service = get_deployment_service(db, current_user)

    try:
        deployment_uuid = uuid.UUID(deployment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment ID format")

    deployment = await service.get_deployment(deployment_uuid)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    # Get recent logs
    logs, _ = await service.get_logs(deployment_uuid, page=1, page_size=20)

    return DeploymentDetailResponse(
        **deployment_to_response(deployment).model_dump(),
        systemd_service_name=deployment.systemd_service_name,
        systemd_unit_path=deployment.systemd_unit_path,
        wrapper_script_path=deployment.wrapper_script_path,
        config_json_path=deployment.config_json_path,
        log_dir=deployment.log_dir,
        install_job_run_id=deployment.install_job_run_id,
        start_job_run_id=deployment.start_job_run_id,
        stop_job_run_id=deployment.stop_job_run_id,
        error_detail=deployment.error_detail,
        retry_count=deployment.retry_count or 0,
        max_retries=deployment.max_retries or 3,
        recent_logs=[
            DeploymentLogResponse(
                id=log.id,
                deployment_id=log.deployment_id,
                level=log.level,
                message=log.message,
                source=log.source,
                operation=log.operation,
                job_run_id=log.job_run_id,
                data=log.data,
                created_at=log.created_at,
            )
            for log in logs
        ],
    )


@router.put(
    "/{deployment_id}",
    response_model=DeploymentResponse,
    dependencies=[Depends(RequirePermission("deployment.deployment.update"))],
)
async def update_deployment(
    deployment_id: str,
    data: DeploymentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeploymentResponse:
    """
    Update a deployment.

    Only allowed when deployment is stopped or failed.
    Changes to GPU configuration or arguments require a restart.
    """
    service = get_deployment_service(db, current_user)

    try:
        deployment_uuid = uuid.UUID(deployment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment ID format")

    try:
        deployment = await service.update_deployment(deployment_uuid, data)
        await db.commit()
        return deployment_to_response(deployment)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{deployment_id}",
    status_code=204,
    dependencies=[Depends(RequirePermission("deployment.deployment.delete"))],
)
async def delete_deployment(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a deployment.

    Only allowed when deployment is stopped or failed.
    Releases the allocated port and cleans up secrets.
    """
    service = get_deployment_service(db, current_user)

    try:
        deployment_uuid = uuid.UUID(deployment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment ID format")

    try:
        await service.delete_deployment(deployment_uuid)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Deployment Lifecycle Actions
# =============================================================================

@router.post(
    "/{deployment_id}/start",
    response_model=DeploymentActionResponse,
    dependencies=[Depends(RequirePermission("deployment.deployment.manage"))],
)
async def start_deployment(
    deployment_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeploymentActionResponse:
    """
    Start a deployment.

    Triggers the deployment pipeline:
    1. Download model (if not cached)
    2. Install framework (if not installed)
    3. Start systemd service

    Returns immediately; use GET /deployments/{id} to monitor progress.
    """
    service = get_deployment_service(db, current_user)

    try:
        deployment_uuid = uuid.UUID(deployment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment ID format")

    try:
        deployment = await service.start_deployment(deployment_uuid)
        await db.commit()

        # TODO: Trigger Celery task for actual deployment
        # background_tasks.add_task(deploy_model_task, deployment_uuid)

        return DeploymentActionResponse(
            deployment_id=deployment.id,
            action="start",
            status="pending",
            message="Deployment start initiated. Monitor status via GET /deployments/{id}.",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{deployment_id}/stop",
    response_model=DeploymentActionResponse,
    dependencies=[Depends(RequirePermission("deployment.deployment.manage"))],
)
async def stop_deployment(
    deployment_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeploymentActionResponse:
    """
    Stop a running deployment.

    Stops the systemd service but preserves the configuration
    and downloaded model for later restart.
    """
    service = get_deployment_service(db, current_user)

    try:
        deployment_uuid = uuid.UUID(deployment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment ID format")

    try:
        deployment = await service.stop_deployment(deployment_uuid)
        await db.commit()

        return DeploymentActionResponse(
            deployment_id=deployment.id,
            action="stop",
            status="stopped",
            message="Deployment stopped successfully.",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{deployment_id}/restart",
    response_model=DeploymentActionResponse,
    dependencies=[Depends(RequirePermission("deployment.deployment.manage"))],
)
async def restart_deployment(
    deployment_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeploymentActionResponse:
    """
    Restart a running deployment.

    Stops and restarts the service with the current configuration.
    """
    service = get_deployment_service(db, current_user)

    try:
        deployment_uuid = uuid.UUID(deployment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment ID format")

    try:
        deployment = await service.restart_deployment(deployment_uuid)
        await db.commit()

        return DeploymentActionResponse(
            deployment_id=deployment.id,
            action="restart",
            status="starting",
            message="Deployment restart initiated.",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Health and Monitoring
# =============================================================================

@router.get(
    "/{deployment_id}/health",
    response_model=DeploymentHealthResponse,
    dependencies=[Depends(RequirePermission("deployment.deployment.view"))],
)
async def check_deployment_health(
    deployment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeploymentHealthResponse:
    """
    Check deployment health.

    Returns cached health status from the last health check.
    Health checks run automatically in the background.
    """
    service = get_deployment_service(db, current_user)

    try:
        deployment_uuid = uuid.UUID(deployment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment ID format")

    try:
        health = await service.check_health(deployment_uuid)
        return DeploymentHealthResponse(
            deployment_id=deployment_uuid,
            health_status=health["status"],
            last_check_at=health.get("last_check_at") or datetime.utcnow(),
            endpoints=health.get("endpoints", {}),
            error=health.get("error"),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{deployment_id}/logs",
    response_model=DeploymentLogListResponse,
    dependencies=[Depends(RequirePermission("deployment.deployment.view"))],
)
async def get_deployment_logs(
    deployment_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=1000, description="Items per page"),
    level: Optional[str] = Query(None, description="Filter by log level"),
    operation: Optional[str] = Query(None, description="Filter by operation"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeploymentLogListResponse:
    """
    Get deployment logs.

    Returns platform logs for the deployment (creation, updates, lifecycle events).
    For service stdout/stderr, use the /logs/stream endpoint.
    """
    service = get_deployment_service(db, current_user)

    try:
        deployment_uuid = uuid.UUID(deployment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deployment ID format")

    logs, total = await service.get_logs(
        deployment_uuid,
        page=page,
        page_size=page_size,
        level=level,
        operation=operation,
    )

    return DeploymentLogListResponse(
        logs=[
            DeploymentLogResponse(
                id=log.id,
                deployment_id=log.deployment_id,
                level=log.level,
                message=log.message,
                source=log.source,
                operation=log.operation,
                job_run_id=log.job_run_id,
                data=log.data,
                created_at=log.created_at,
            )
            for log in logs
        ],
        pagination=PaginatedResponse.create(total, page, page_size),
    )


# =============================================================================
# Compatibility Check
# =============================================================================

@router.post(
    "/compatibility",
    response_model=CompatibilityCheckResponse,
    dependencies=[Depends(RequirePermission("deployment.deployment.view"))],
)
async def check_compatibility(
    request: CompatibilityCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompatibilityCheckResponse:
    """
    Check node compatibility with deployment frameworks.

    Evaluates whether a node can support vLLM, SGLang, and/or Xinference
    based on hardware capabilities, driver versions, and OS requirements.

    Returns compatibility status, reason if not supported, and recommended
    installation profile.
    """
    evaluator = CompatibilityEvaluator(db)

    # Parse framework filter
    frameworks = None
    if request.frameworks:
        frameworks = [DeploymentFramework(f) for f in request.frameworks]

    try:
        results = await evaluator.evaluate_node(request.node_id, frameworks)

        # Get node info for response
        from sqlalchemy import select
        from app.models.node import Node
        stmt = select(Node).where(Node.id == request.node_id)
        node = (await db.execute(stmt)).scalar_one_or_none()

        if not node:
            raise HTTPException(status_code=404, detail="Node not found")

        return CompatibilityCheckResponse(
            node_id=node.id,
            node_name=node.name,
            node_host=node.host,
            frameworks=[
                FrameworkCompatibility(
                    framework=r.framework.value,
                    supported=r.supported,
                    reason=r.reason,
                    install_profile=r.install_profile,
                    capabilities=r.capabilities,
                    requirements=r.requirements,
                )
                for r in results
            ],
            evaluated_at=datetime.utcnow(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# Node Accelerators (for GPU selection UI)
# =============================================================================

@router.get(
    "/nodes/{node_id}/accelerators",
    response_model=NodeAcceleratorsResponse,
    dependencies=[Depends(RequirePermission("deployment.deployment.view"))],
)
async def get_node_accelerators(
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NodeAcceleratorsResponse:
    """
    Get accelerators available on a node.

    Returns list of GPU/NPU devices with their indices, models, memory,
    and health status for the deployment GPU selection UI.
    """
    service = get_deployment_service(db, current_user)

    try:
        node_uuid = uuid.UUID(node_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid node ID format")

    try:
        node, accelerators = await service.get_node_accelerators(node_uuid)

        # Determine primary accelerator type
        accelerator_type = None
        if accelerators:
            accelerator_type = accelerators[0].type.value

        return NodeAcceleratorsResponse(
            node_id=node.id,
            node_name=node.name,
            accelerator_type=accelerator_type,
            accelerator_count=len(accelerators),
            devices=[
                AcceleratorDevice(
                    index=acc.slot or i,
                    device_type=acc.type.value,
                    vendor=acc.vendor or "unknown",
                    model=acc.model or "unknown",
                    memory_mb=acc.memory_mb or 0,
                    uuid=acc.device_id,
                    health_status=acc.health_status or "unknown",
                    utilization_percent=acc.utilization_percent,
                )
                for i, acc in enumerate(accelerators)
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# Quick Deploy
# =============================================================================

@router.post(
    "/quick-deploy",
    response_model=QuickDeployResponse,
    dependencies=[Depends(RequirePermission("deployment.deployment.create"))],
)
async def quick_deploy(
    request: QuickDeployRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuickDeployResponse:
    """
    Quick deploy a model with minimal configuration.

    Uses sensible defaults for all optional parameters.
    Good for testing or simple deployments.
    """
    service = get_deployment_service(db, current_user)

    # Build full deployment create request with defaults
    data = DeploymentCreate(
        name=request.name,
        node_id=request.node_id,
        framework=request.framework,
        model_repo_id=request.model_repo_id,
        port=request.port,
        gpu_devices=request.gpu_devices,
    )

    try:
        deployment = await service.create_deployment(data)
        await db.commit()

        # Trigger start
        await service.start_deployment(deployment.id)
        await db.commit()

        return QuickDeployResponse(
            deployment_id=deployment.id,
            status="pending",
            message=f"Deployment '{request.name}' created and starting. Monitor via GET /deployments/{deployment.id}.",
            estimated_time_minutes=5,  # Rough estimate
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

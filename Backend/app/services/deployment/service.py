"""
Model Deployment Service.

Core service for managing model deployments including creation,
lifecycle management (start/stop/restart), health monitoring,
and cleanup.

Reference documentation:
- vLLM: https://docs.vllm.ai/en/latest/getting_started/quickstart/
- SGLang: https://docs.sglang.io/
- Xinference: https://inference.readthedocs.io/en/latest/getting_started/using_xinference.html
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.deployment import (
    Deployment,
    DeploymentLog,
    DeploymentStatus,
    DeploymentFramework,
    DeploymentMode,
    ModelSource,
    SecretsKV,
)
from app.models.node import Node, Accelerator, AcceleratorType
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentUpdate,
    EnvTableEntry,
    ArgsTableEntry,
)
from app.services.deployment.port_manager import PortManager
from app.services.deployment.compatibility import CompatibilityEvaluator


class DeploymentService:
    """Service for managing model deployments."""

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID, user_email: str = ""):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.user_email = user_email
        self.port_manager = PortManager(db, tenant_id)
        self.compatibility_evaluator = CompatibilityEvaluator(db)

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def list_deployments(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[DeploymentStatus] = None,
        framework: Optional[DeploymentFramework] = None,
        node_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Deployment], int]:
        """List deployments with filtering and pagination."""
        # Base query
        stmt = (
            select(Deployment)
            .where(Deployment.tenant_id == self.tenant_id)
            .options(selectinload(Deployment.node))
        )

        # Apply filters
        if status:
            stmt = stmt.where(Deployment.status == status)
        if framework:
            stmt = stmt.where(Deployment.framework == framework)
        if node_id:
            stmt = stmt.where(Deployment.node_id == node_id)
        if search:
            search_filter = or_(
                Deployment.name.ilike(f"%{search}%"),
                Deployment.display_name.ilike(f"%{search}%"),
                Deployment.model_repo_id.ilike(f"%{search}%"),
            )
            stmt = stmt.where(search_filter)

        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # Apply pagination
        stmt = stmt.order_by(Deployment.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        deployments = list(result.scalars().all())

        return deployments, total

    async def get_deployment(self, deployment_id: uuid.UUID) -> Optional[Deployment]:
        """Get a deployment by ID."""
        stmt = (
            select(Deployment)
            .where(
                and_(
                    Deployment.id == deployment_id,
                    Deployment.tenant_id == self.tenant_id,
                )
            )
            .options(selectinload(Deployment.node), selectinload(Deployment.logs))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_deployment(self, data: DeploymentCreate) -> Deployment:
        """
        Create a new deployment.

        Args:
            data: Deployment creation data

        Returns:
            Created deployment

        Raises:
            ValueError: If validation fails
        """
        # Validate node exists and is ready
        node = await self._get_node(data.node_id)
        if not node:
            raise ValueError(f"Node not found: {data.node_id}")

        # Check compatibility
        framework = DeploymentFramework(data.framework)
        compat_results = await self.compatibility_evaluator.evaluate_node(
            data.node_id, [framework]
        )
        compat = compat_results[0]
        if not compat.supported:
            raise ValueError(
                f"Framework {data.framework} not supported on node: {compat.reason}"
            )

        # Allocate port
        port = await self.port_manager.allocate_port(
            node_id=data.node_id,
            preferred_port=data.port,
        )

        # Process sensitive environment variables
        sensitive_refs = {}
        env_table_processed = []
        for env in data.env_table:
            if env.is_sensitive and env.value:
                # Store in secrets_kv
                secret_key = f"deployment_{uuid.uuid4().hex[:8]}_{env.name}"
                secret = await self._create_secret(secret_key, env.value)
                sensitive_refs[env.name] = str(secret.id)
                # Don't store value in env_table
                env_table_processed.append(
                    {"name": env.name, "value": "", "is_sensitive": True}
                )
            else:
                env_table_processed.append(env.model_dump())

        # Process args_table
        args_table_processed = [arg.model_dump() for arg in data.args_table]

        # Determine served model name
        served_name = data.served_model_name or data.model_repo_id.split("/")[-1]

        # Build deployment paths
        deployment_id = uuid.uuid4()
        work_dir = f"{settings.deployment.work_dir}/{deployment_id}"
        log_dir = f"{settings.deployment.log_root}/{deployment_id}"

        # Create deployment
        deployment = Deployment(
            id=deployment_id,
            tenant_id=self.tenant_id,
            name=data.name,
            display_name=data.display_name or data.name,
            description=data.description,
            framework=framework,
            deployment_mode=DeploymentMode(data.deployment_mode),
            node_id=data.node_id,
            model_source=ModelSource(data.model_source),
            model_repo_id=data.model_repo_id,
            model_revision=data.model_revision,
            host=data.host,
            port=port,
            served_model_name=served_name,
            gpu_devices=data.gpu_devices,
            tensor_parallel_size=data.tensor_parallel_size,
            gpu_memory_utilization=data.gpu_memory_utilization,
            env_table=env_table_processed,
            args_table=args_table_processed,
            sensitive_env_refs=sensitive_refs,
            status=DeploymentStatus.PENDING,
            systemd_service_name=f"noveris-model-{deployment_id.hex[:12]}",
            systemd_unit_path=f"{settings.deployment.systemd_service_dir}/noveris-model-{deployment_id.hex[:12]}.service",
            wrapper_script_path=f"{work_dir}/run.py",
            config_json_path=f"{work_dir}/config.json",
            log_dir=log_dir,
            stdout_log_path=f"{log_dir}/stdout.log",
            stderr_log_path=f"{log_dir}/stderr.log",
            labels=data.labels,
            tags=data.tags,
            created_by=self.user_id,
            created_by_email=self.user_email,
        )

        self.db.add(deployment)
        await self.db.flush()

        # Update port allocation with deployment ID
        allocation = await self.port_manager.get_allocation(data.node_id, port)
        if allocation:
            allocation.deployment_id = deployment.id

        # Add creation log
        await self._add_log(
            deployment.id,
            "info",
            f"Deployment created: {data.name}",
            source="api",
            operation="create",
        )

        return deployment

    async def update_deployment(
        self,
        deployment_id: uuid.UUID,
        data: DeploymentUpdate,
    ) -> Deployment:
        """Update a deployment."""
        deployment = await self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment not found: {deployment_id}")

        # Only allow updates when stopped or failed
        if deployment.status not in [DeploymentStatus.STOPPED, DeploymentStatus.FAILED]:
            raise ValueError(
                f"Cannot update deployment in status {deployment.status.value}. "
                "Stop the deployment first."
            )

        # Update fields
        if data.display_name is not None:
            deployment.display_name = data.display_name
        if data.description is not None:
            deployment.description = data.description
        if data.gpu_devices is not None:
            deployment.gpu_devices = data.gpu_devices
        if data.tensor_parallel_size is not None:
            deployment.tensor_parallel_size = data.tensor_parallel_size
        if data.gpu_memory_utilization is not None:
            deployment.gpu_memory_utilization = data.gpu_memory_utilization
        if data.labels is not None:
            deployment.labels = data.labels
        if data.tags is not None:
            deployment.tags = data.tags

        # Handle env_table update
        if data.env_table is not None:
            env_table_processed = []
            sensitive_refs = dict(deployment.sensitive_env_refs or {})

            for env in data.env_table:
                if env.is_sensitive and env.value:
                    # Update or create secret
                    if env.name in sensitive_refs:
                        # Update existing secret
                        await self._update_secret(
                            uuid.UUID(sensitive_refs[env.name]), env.value
                        )
                    else:
                        # Create new secret
                        secret_key = f"deployment_{deployment.id.hex[:8]}_{env.name}"
                        secret = await self._create_secret(secret_key, env.value)
                        sensitive_refs[env.name] = str(secret.id)

                    env_table_processed.append(
                        {"name": env.name, "value": "", "is_sensitive": True}
                    )
                else:
                    env_table_processed.append(env.model_dump())

            deployment.env_table = env_table_processed
            deployment.sensitive_env_refs = sensitive_refs

        # Handle args_table update
        if data.args_table is not None:
            deployment.args_table = [arg.model_dump() for arg in data.args_table]

        await self._add_log(
            deployment.id,
            "info",
            "Deployment updated",
            source="api",
            operation="update",
        )

        return deployment

    async def delete_deployment(self, deployment_id: uuid.UUID) -> None:
        """Delete a deployment."""
        deployment = await self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment not found: {deployment_id}")

        # Don't allow deletion of running deployments
        if deployment.status in [
            DeploymentStatus.RUNNING,
            DeploymentStatus.STARTING,
            DeploymentStatus.INSTALLING,
            DeploymentStatus.DOWNLOADING,
        ]:
            raise ValueError(
                f"Cannot delete deployment in status {deployment.status.value}. "
                "Stop the deployment first."
            )

        # Release port
        if deployment.port and deployment.node_id:
            await self.port_manager.release_port(deployment.node_id, deployment.port)

        # Delete secrets
        for secret_id in (deployment.sensitive_env_refs or {}).values():
            await self._delete_secret(uuid.UUID(secret_id))

        # Delete deployment (cascade deletes logs)
        await self.db.delete(deployment)

    # =========================================================================
    # Lifecycle Operations
    # =========================================================================

    async def start_deployment(self, deployment_id: uuid.UUID) -> Deployment:
        """
        Start a deployment.

        This triggers the deployment pipeline:
        1. Download model (if not cached)
        2. Install framework (if not installed)
        3. Start service

        Returns the deployment with updated status.
        """
        deployment = await self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment not found: {deployment_id}")

        # Validate status
        allowed_statuses = [
            DeploymentStatus.PENDING,
            DeploymentStatus.STOPPED,
            DeploymentStatus.FAILED,
        ]
        if deployment.status not in allowed_statuses:
            raise ValueError(
                f"Cannot start deployment in status {deployment.status.value}"
            )

        # Update status
        deployment.status = DeploymentStatus.PENDING

        await self._add_log(
            deployment.id,
            "info",
            "Deployment start requested",
            source="api",
            operation="start",
        )

        # Note: Actual deployment work is done by Celery worker
        # See app/workers/deployment_worker.py

        return deployment

    async def stop_deployment(self, deployment_id: uuid.UUID) -> Deployment:
        """Stop a running deployment."""
        deployment = await self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment not found: {deployment_id}")

        if deployment.status != DeploymentStatus.RUNNING:
            raise ValueError(
                f"Cannot stop deployment in status {deployment.status.value}"
            )

        deployment.status = DeploymentStatus.STOPPED
        deployment.stopped_at = datetime.utcnow()

        await self._add_log(
            deployment.id,
            "info",
            "Deployment stop requested",
            source="api",
            operation="stop",
        )

        return deployment

    async def restart_deployment(self, deployment_id: uuid.UUID) -> Deployment:
        """Restart a deployment."""
        deployment = await self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment not found: {deployment_id}")

        if deployment.status != DeploymentStatus.RUNNING:
            raise ValueError(
                f"Cannot restart deployment in status {deployment.status.value}"
            )

        # Mark for restart
        deployment.status = DeploymentStatus.STARTING

        await self._add_log(
            deployment.id,
            "info",
            "Deployment restart requested",
            source="api",
            operation="restart",
        )

        return deployment

    # =========================================================================
    # Health Check
    # =========================================================================

    async def check_health(self, deployment_id: uuid.UUID) -> Dict[str, Any]:
        """
        Check deployment health by querying its endpoints.

        Returns health status and response time.
        """
        deployment = await self.get_deployment(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment not found: {deployment_id}")

        if deployment.status != DeploymentStatus.RUNNING:
            return {
                "status": "not_running",
                "error": f"Deployment is in status {deployment.status.value}",
            }

        # Note: Actual health check is done by background task
        # This returns cached health status
        return {
            "status": deployment.health_status,
            "last_check_at": deployment.last_health_check_at,
            "error": deployment.health_check_error,
            "endpoints": deployment.endpoints,
        }

    # =========================================================================
    # Logs
    # =========================================================================

    async def get_logs(
        self,
        deployment_id: uuid.UUID,
        page: int = 1,
        page_size: int = 100,
        level: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> Tuple[List[DeploymentLog], int]:
        """Get deployment logs with filtering."""
        stmt = select(DeploymentLog).where(
            DeploymentLog.deployment_id == deployment_id
        )

        if level:
            stmt = stmt.where(DeploymentLog.level == level)
        if operation:
            stmt = stmt.where(DeploymentLog.operation == operation)

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # Paginate
        stmt = stmt.order_by(DeploymentLog.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        logs = list(result.scalars().all())

        return logs, total

    # =========================================================================
    # GPU/Accelerator Info
    # =========================================================================

    async def get_node_accelerators(
        self,
        node_id: uuid.UUID,
    ) -> Tuple[Node, List[Accelerator]]:
        """Get node and its accelerators for GPU selection UI."""
        node = await self._get_node(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")

        stmt = select(Accelerator).where(Accelerator.node_id == node_id)
        result = await self.db.execute(stmt)
        accelerators = list(result.scalars().all())

        return node, accelerators

    # =========================================================================
    # Framework Config Templates
    # =========================================================================

    def get_framework_templates(self) -> List[Dict[str, Any]]:
        """Get recommended configuration templates for each framework."""
        return [
            {
                "framework": "vllm",
                "description": "High-performance LLM inference with vLLM",
                "recommended_args": [
                    {"key": "--max-model-len", "value": "4096", "arg_type": "int", "enabled": True},
                    {"key": "--gpu-memory-utilization", "value": "0.9", "arg_type": "float", "enabled": True},
                    {"key": "--enable-prefix-caching", "value": "", "arg_type": "bool", "enabled": False},
                ],
                "recommended_env": [
                    {"name": "VLLM_ATTENTION_BACKEND", "value": "FLASHINFER", "is_sensitive": False},
                ],
                "documentation_url": "https://docs.vllm.ai/en/latest/getting_started/quickstart/",
            },
            {
                "framework": "sglang",
                "description": "Fast serving with RadixAttention",
                "recommended_args": [
                    {"key": "--mem-fraction-static", "value": "0.9", "arg_type": "float", "enabled": True},
                    {"key": "--chunked-prefill-size", "value": "4096", "arg_type": "int", "enabled": True},
                ],
                "recommended_env": [],
                "documentation_url": "https://docs.sglang.io/",
            },
            {
                "framework": "xinference",
                "description": "Multi-framework inference platform",
                "recommended_args": [
                    {"key": "--n-gpu", "value": "auto", "arg_type": "string", "enabled": True},
                ],
                "recommended_env": [
                    {"name": "XINFERENCE_MODEL_SRC", "value": "huggingface", "is_sensitive": False},
                ],
                "documentation_url": "https://inference.readthedocs.io/en/latest/getting_started/using_xinference.html",
            },
        ]

    # =========================================================================
    # Private Helpers
    # =========================================================================

    async def _get_node(self, node_id: uuid.UUID) -> Optional[Node]:
        """Get node by ID."""
        stmt = select(Node).where(
            and_(
                Node.id == node_id,
                Node.tenant_id == self.tenant_id,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _add_log(
        self,
        deployment_id: uuid.UUID,
        level: str,
        message: str,
        source: Optional[str] = None,
        operation: Optional[str] = None,
        job_run_id: Optional[uuid.UUID] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> DeploymentLog:
        """Add a log entry for a deployment."""
        log = DeploymentLog(
            deployment_id=deployment_id,
            level=level,
            message=message,
            source=source,
            operation=operation,
            job_run_id=job_run_id,
            data=data,
        )
        self.db.add(log)
        return log

    async def _create_secret(self, key: str, value: str) -> SecretsKV:
        """Create an encrypted secret."""
        from app.core.security import encrypt_value

        ciphertext = encrypt_value(value)
        secret = SecretsKV(
            tenant_id=self.tenant_id,
            key=key,
            ciphertext=ciphertext,
            created_by=self.user_id,
        )
        self.db.add(secret)
        await self.db.flush()
        return secret

    async def _update_secret(self, secret_id: uuid.UUID, value: str) -> None:
        """Update an encrypted secret."""
        from app.core.security import encrypt_value

        stmt = select(SecretsKV).where(SecretsKV.id == secret_id)
        result = await self.db.execute(stmt)
        secret = result.scalar_one_or_none()
        if secret:
            secret.ciphertext = encrypt_value(value)
            secret.updated_at = datetime.utcnow()

    async def _delete_secret(self, secret_id: uuid.UUID) -> None:
        """Delete a secret."""
        stmt = select(SecretsKV).where(SecretsKV.id == secret_id)
        result = await self.db.execute(stmt)
        secret = result.scalar_one_or_none()
        if secret:
            await self.db.delete(secret)

    async def _get_secret_value(self, secret_id: uuid.UUID) -> Optional[str]:
        """Get decrypted secret value."""
        from app.core.security import decrypt_value

        stmt = select(SecretsKV).where(SecretsKV.id == secret_id)
        result = await self.db.execute(stmt)
        secret = result.scalar_one_or_none()
        if secret:
            return decrypt_value(secret.ciphertext)
        return None

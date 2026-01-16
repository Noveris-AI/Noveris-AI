"""
Node Management Service Layer.

Business logic for node management operations:
- Node CRUD operations
- Credential management
- Group and variable management
- Job execution coordination
- Inventory generation
"""

import uuid
import json
import yaml
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from sqlalchemy import select, func, and_, or_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from redis.asyncio import Redis
import structlog

from app.core.config import settings
from app.models.node import (
    Node, NodeCredential, NodeBmcCredential, NodeGroup, GroupVar,
    NodeFactSnapshot, Accelerator, JobTemplate, JobRun, JobRunEvent,
    AuditLog, NodeStatus, ConnectionType, JobStatus, AuthType,
    AcceleratorType, node_group_association, job_run_nodes
)
from app.schemas.node_management import (
    NodeCreate, NodeUpdate, NodeGroupCreate, NodeGroupUpdate,
    GroupVarCreate, GroupVarUpdate, JobRunCreate, PaginationParams
)
from app.services.node_management.credential_service import (
    get_credential_service, CredentialService
)
from app.services.node_management.job_queue_service import (
    JobQueueService, get_job_queue_service
)

logger = structlog.get_logger(__name__)


class NodeManagementError(Exception):
    """Base exception for node management errors."""
    pass


class NodeNotFoundError(NodeManagementError):
    """Node not found."""
    pass


class CredentialError(NodeManagementError):
    """Credential operation error."""
    pass


class JobExecutionError(NodeManagementError):
    """Job execution error."""
    pass


class NodeService:
    """Service for node operations."""

    def __init__(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        redis_client: Optional[Redis] = None
    ):
        self.db = db
        self.tenant_id = tenant_id
        self._redis_client = redis_client
        self._credential_service: Optional[CredentialService] = None
        self._job_queue_service: Optional[JobQueueService] = None

    @property
    def credential_service(self) -> CredentialService:
        """Lazy-load credential service."""
        if self._credential_service is None:
            self._credential_service = get_credential_service()
        return self._credential_service

    @property
    def job_queue_service(self) -> Optional[JobQueueService]:
        """Lazy-load job queue service (requires redis client)."""
        if self._job_queue_service is None and self._redis_client is not None:
            self._job_queue_service = get_job_queue_service(self._redis_client)
        return self._job_queue_service

    # ==========================================================================
    # Node CRUD
    # ==========================================================================

    async def list_nodes(
        self,
        pagination: PaginationParams,
        search: Optional[str] = None,
        status: Optional[NodeStatus] = None,
        accel_type: Optional[AcceleratorType] = None,
        group_id: Optional[uuid.UUID] = None,
        tags: Optional[List[str]] = None
    ) -> Tuple[List[Node], int]:
        """List nodes with filtering and pagination."""
        # Base query
        query = (
            select(Node)
            .where(Node.tenant_id == self.tenant_id)
            .options(selectinload(Node.groups), selectinload(Node.accelerators))
        )

        # Apply filters
        if search:
            search_filter = or_(
                Node.name.ilike(f"%{search}%"),
                Node.host.ilike(f"%{search}%"),
                Node.display_name.ilike(f"%{search}%")
            )
            query = query.where(search_filter)

        if status:
            query = query.where(Node.status == status)

        if group_id:
            query = query.join(node_group_association).where(
                node_group_association.c.node_group_id == group_id
            )

        if tags:
            query = query.where(Node.tags.contains(tags))

        if accel_type:
            query = query.join(Accelerator).where(Accelerator.type == accel_type)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)

        # Apply pagination
        query = query.order_by(Node.created_at.desc())
        query = query.offset(pagination.offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        nodes = result.scalars().all()

        return list(nodes), total or 0

    async def get_node(self, node_id: uuid.UUID) -> Optional[Node]:
        """Get a single node by ID."""
        query = (
            select(Node)
            .where(and_(Node.id == node_id, Node.tenant_id == self.tenant_id))
            .options(
                selectinload(Node.groups),
                selectinload(Node.accelerators),
                selectinload(Node.credentials),
                selectinload(Node.bmc_credentials),
                selectinload(Node.fact_snapshots)
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_node(self, data: NodeCreate, user_id: uuid.UUID) -> Node:
        """Create a new node with credentials."""
        # Create node
        node = Node(
            tenant_id=self.tenant_id,
            name=data.name,
            display_name=data.display_name or data.name,
            host=data.host,
            port=data.port,
            connection_type=ConnectionType(data.connection_type),
            ssh_user=data.ssh_user,
            labels=data.labels,
            tags=data.tags,
            status=NodeStatus.NEW.value
        )
        self.db.add(node)
        await self.db.flush()

        # Create credentials based on connection type
        if data.connection_type == "local":
            # Local connections don't need credentials
            pass
        elif data.connection_type == "winrm":
            # WinRM credentials for Windows nodes
            encrypted = self.credential_service.encrypt_winrm_credentials(
                username=data.ssh_user or "Administrator",
                password=data.password,
                transport=data.winrm_transport,
                cert_pem=data.winrm_cert_pem,
                cert_key_pem=data.winrm_cert_key_pem,
                server_cert_validation=data.winrm_server_cert_validation,
                kerberos_realm=data.winrm_kerberos_realm
            )
            auth_type = AuthType.PASSWORD.value  # WinRM uses password-based auth primarily
            credential = NodeCredential(
                tenant_id=self.tenant_id,
                node_id=node.id,
                auth_type=auth_type,
                encrypted_payload=encrypted,
                key_version=settings.credential.key_version,
            )
            self.db.add(credential)
        elif data.credential_type == "ssh_key" and data.ssh_private_key:
            encrypted = self.credential_service.encrypt_ssh_key(
                private_key=data.ssh_private_key,
                passphrase=data.ssh_key_passphrase,
                bastion_host=data.bastion_host,
                bastion_user=data.bastion_user,
                bastion_port=data.bastion_port,
                bastion_key=data.bastion_ssh_key,
                bastion_password=data.bastion_password
            )
            auth_type = AuthType.SSH_KEY.value
            credential = NodeCredential(
                tenant_id=self.tenant_id,
                node_id=node.id,
                auth_type=auth_type,
                encrypted_payload=encrypted,
                key_version=settings.credential.key_version,
                bastion_host=data.bastion_host,
                bastion_port=data.bastion_port,
                bastion_user=data.bastion_user
            )
            self.db.add(credential)
        elif data.credential_type == "password" and data.password:
            encrypted = self.credential_service.encrypt_password(
                password=data.password,
                bastion_host=data.bastion_host,
                bastion_user=data.bastion_user,
                bastion_key=data.bastion_ssh_key,
                bastion_password=data.bastion_password
            )
            auth_type = AuthType.PASSWORD.value
            credential = NodeCredential(
                tenant_id=self.tenant_id,
                node_id=node.id,
                auth_type=auth_type,
                encrypted_payload=encrypted,
                key_version=settings.credential.key_version,
                bastion_host=data.bastion_host,
                bastion_port=data.bastion_port,
                bastion_user=data.bastion_user
            )
            self.db.add(credential)
        else:
            raise CredentialError("Invalid credential configuration")

        # Assign to groups
        if data.group_ids:
            groups = await self._get_groups_by_ids(data.group_ids)
            node.groups = groups

        await self.db.commit()
        await self.db.refresh(node)

        # Create audit log
        await self._audit_log(
            user_id, "create", "node", node.id, node.name,
            diff={"after": {"name": node.name, "host": node.host}}
        )

        logger.info("Node created", node_id=str(node.id), name=node.name)
        return node

    async def update_node(
        self,
        node_id: uuid.UUID,
        data: NodeUpdate,
        user_id: uuid.UUID
    ) -> Node:
        """Update an existing node."""
        node = await self.get_node(node_id)
        if not node:
            raise NodeNotFoundError(f"Node {node_id} not found")

        # Track changes
        before = {
            "display_name": node.display_name,
            "port": node.port,
            "ssh_user": node.ssh_user,
            "status": node.status if node.status else None,
            "tags": node.tags
        }

        # Update fields
        if data.display_name is not None:
            node.display_name = data.display_name
        if data.port is not None:
            node.port = data.port
        if data.ssh_user is not None:
            node.ssh_user = data.ssh_user
        if data.node_type is not None:
            node.node_type = data.node_type
        if data.labels is not None:
            node.labels = data.labels
        if data.tags is not None:
            node.tags = data.tags
        if data.status is not None:
            node.status = NodeStatus(data.status)

        # Update group assignments
        if data.group_ids is not None:
            groups = await self._get_groups_by_ids(data.group_ids)
            node.groups = groups

        await self.db.commit()
        await self.db.refresh(node)

        # Audit log
        after = {
            "display_name": node.display_name,
            "port": node.port,
            "ssh_user": node.ssh_user,
            "status": node.status if node.status else None,
            "tags": node.tags
        }
        await self._audit_log(
            user_id, "update", "node", node.id, node.name,
            diff={"before": before, "after": after}
        )

        return node

    async def delete_node(self, node_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Soft delete a node (decommission)."""
        node = await self.get_node(node_id)
        if not node:
            raise NodeNotFoundError(f"Node {node_id} not found")

        node.status = NodeStatus.DECOMMISSIONED.value
        node.decommissioned_at = datetime.utcnow()

        await self.db.commit()

        await self._audit_log(
            user_id, "delete", "node", node.id, node.name,
            diff={"status": "DECOMMISSIONED"}
        )

        logger.info("Node decommissioned", node_id=str(node_id))
        return True

    async def verify_connectivity(
        self,
        node_id: uuid.UUID,
        user_id: uuid.UUID,
        update_status: bool = True
    ) -> Dict[str, Any]:
        """
        Verify connectivity to a node.

        Performs:
        1. TCP port check (SSH/WinRM port)
        2. Optional SSH authentication test (if credentials exist)
        3. Updates node status if update_status is True

        Args:
            node_id: The node ID to verify
            user_id: User performing the verification
            update_status: Whether to update node status based on result

        Returns:
            Dict with verification results
        """
        import asyncio
        import time

        node = await self.get_node(node_id)
        if not node:
            raise NodeNotFoundError(f"Node {node_id} not found")

        status_before = node.status
        start_time = time.time()
        result = {
            "node_id": node_id,
            "node_name": node.name,
            "host": node.host,
            "port": node.port,
            "connection_type": node.connection_type,
            "is_reachable": False,
            "ssh_reachable": False,
            "response_time_ms": None,
            "error_message": None,
            "checked_at": datetime.utcnow(),
            "status_before": status_before,
            "status_after": status_before,
        }

        # Local connection is always reachable
        if node.connection_type == ConnectionType.LOCAL.value:
            result["is_reachable"] = True
            result["ssh_reachable"] = True
            result["response_time_ms"] = 0.0
            if update_status and node.status != NodeStatus.DECOMMISSIONED.value:
                node.status = NodeStatus.READY.value
                node.last_seen_at = datetime.utcnow()
                await self.db.commit()
                result["status_after"] = NodeStatus.READY.value
            return result

        # TCP port check
        try:
            connect_start = time.time()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(node.host, node.port),
                timeout=10.0
            )
            connect_time = (time.time() - connect_start) * 1000
            writer.close()
            await writer.wait_closed()

            result["is_reachable"] = True
            result["response_time_ms"] = round(connect_time, 2)

            # Verify authentication based on connection type
            if node.connection_type == ConnectionType.WINRM.value:
                # WinRM authentication verification
                if node.credentials:
                    try:
                        winrm_result = await self._verify_winrm_auth(node)
                        result["ssh_reachable"] = winrm_result["success"]  # Reuse field for WinRM auth
                        if not winrm_result["success"]:
                            result["error_message"] = winrm_result.get("error", "WinRM auth failed")
                    except Exception as winrm_err:
                        result["ssh_reachable"] = False
                        result["error_message"] = f"WinRM auth error: {str(winrm_err)}"
                else:
                    result["ssh_reachable"] = False
                    result["error_message"] = "No WinRM credentials configured"
            else:
                # SSH authentication verification
                if node.credentials:
                    try:
                        ssh_result = await self._verify_ssh_auth(node)
                        result["ssh_reachable"] = ssh_result["success"]
                        if not ssh_result["success"]:
                            result["error_message"] = ssh_result.get("error", "SSH auth failed")
                    except Exception as ssh_err:
                        result["ssh_reachable"] = False
                        result["error_message"] = f"SSH auth error: {str(ssh_err)}"
                else:
                    # No credentials, but port is reachable
                    result["ssh_reachable"] = False
                    result["error_message"] = "No credentials configured"

        except asyncio.TimeoutError:
            result["is_reachable"] = False
            result["error_message"] = f"Connection timeout to {node.host}:{node.port}"
        except OSError as e:
            result["is_reachable"] = False
            result["error_message"] = f"Connection error: {str(e)}"
        except Exception as e:
            result["is_reachable"] = False
            result["error_message"] = f"Unexpected error: {str(e)}"

        # Update node status based on result
        if update_status and node.status != NodeStatus.DECOMMISSIONED.value:
            if result["is_reachable"] and result["ssh_reachable"]:
                node.status = NodeStatus.READY.value
                node.last_seen_at = datetime.utcnow()
            elif result["is_reachable"]:
                # Port reachable but SSH auth failed - might be credential issue
                node.status = NodeStatus.NEW.value
            else:
                node.status = NodeStatus.UNREACHABLE.value

            await self.db.commit()
            result["status_after"] = node.status

        # Audit log
        await self._audit_log(
            user_id, "verify", "node", node.id, node.name,
            diff={
                "is_reachable": result["is_reachable"],
                "ssh_reachable": result["ssh_reachable"],
                "status_before": status_before,
                "status_after": result["status_after"],
            }
        )

        total_time = (time.time() - start_time) * 1000
        logger.info(
            "Node connectivity verified",
            node_id=str(node_id),
            is_reachable=result["is_reachable"],
            ssh_reachable=result["ssh_reachable"],
            total_time_ms=round(total_time, 2)
        )

        return result

    async def _verify_winrm_auth(self, node: Node) -> Dict[str, Any]:
        """
        Verify WinRM authentication to Windows nodes.

        Uses pywinrm library to test WinRM connectivity and authentication.
        Falls back to PowerShell remoting test via subprocess if pywinrm unavailable.
        """
        import asyncio

        creds = await self._get_decrypted_credentials(node.id)
        if not creds:
            return {"success": False, "error": "No credentials found"}

        # Check credential type
        if creds.get("type") != "winrm":
            return {"success": False, "error": "Invalid credential type for WinRM"}

        username = creds.get("username", "Administrator")
        password = creds.get("password")
        transport = creds.get("transport", "ntlm")
        server_cert_validation = creds.get("server_cert_validation", "validate")

        # Determine protocol based on cert validation
        protocol = "https" if server_cert_validation == "validate" else "http"
        endpoint = f"{protocol}://{node.host}:{node.port}/wsman"

        try:
            # Try using pywinrm library
            try:
                import winrm

                # Configure session based on transport
                session_kwargs = {
                    "transport": transport,
                    "server_cert_validation": server_cert_validation,
                }

                # Certificate auth
                if transport == "certificate":
                    cert_pem = creds.get("cert_pem")
                    cert_key_pem = creds.get("cert_key_pem")
                    if cert_pem and cert_key_pem:
                        # Write temp cert files
                        import tempfile
                        import os

                        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
                            f.write(cert_pem)
                            cert_file = f.name
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
                            f.write(cert_key_pem)
                            key_file = f.name

                        try:
                            session_kwargs["cert_pem"] = cert_file
                            session_kwargs["cert_key_pem"] = key_file

                            session = winrm.Session(
                                endpoint,
                                auth=(username, password or ""),
                                **session_kwargs
                            )
                            # Run simple command to verify
                            result = session.run_cmd("hostname")
                            if result.status_code == 0:
                                return {
                                    "success": True,
                                    "hostname": result.std_out.decode().strip()
                                }
                            else:
                                return {
                                    "success": False,
                                    "error": result.std_err.decode().strip() or "Command failed"
                                }
                        finally:
                            os.unlink(cert_file)
                            os.unlink(key_file)
                else:
                    # Password-based auth (NTLM, Kerberos, Basic, CredSSP)
                    session = winrm.Session(
                        endpoint,
                        auth=(username, password or ""),
                        **session_kwargs
                    )

                    # Run simple command to verify connectivity
                    result = session.run_cmd("hostname")
                    if result.status_code == 0:
                        return {
                            "success": True,
                            "hostname": result.std_out.decode().strip()
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.std_err.decode().strip() or "Command failed"
                        }

            except ImportError:
                # pywinrm not installed, try PowerShell Test-WSMan
                logger.warning(
                    "pywinrm not installed, falling back to Test-WSMan",
                    node_id=str(node.id)
                )

                # Use PowerShell to test WinRM (requires pwsh on host)
                ps_cmd = [
                    "pwsh", "-NoProfile", "-NonInteractive", "-Command",
                    f"Test-WSMan -ComputerName {node.host} -Port {node.port} "
                    f"-Authentication {transport.capitalize()} -ErrorAction Stop"
                ]

                proc = await asyncio.create_subprocess_exec(
                    *ps_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=15.0
                )

                if proc.returncode == 0:
                    return {"success": True}
                else:
                    # Try basic TCP connection test as fallback
                    return {
                        "success": False,
                        "error": f"WinRM test failed: {stderr.decode().strip()}"
                    }

        except asyncio.TimeoutError:
            return {"success": False, "error": "WinRM authentication timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _verify_ssh_auth(self, node: Node) -> Dict[str, Any]:
        """
        Verify SSH authentication using credentials.

        Uses a simple SSH connection test via subprocess (paramiko/asyncssh alternative).
        For full production use, consider using ansible-runner or asyncssh library.
        """
        import asyncio
        import tempfile
        import os

        creds = await self._get_decrypted_credentials(node.id)
        if not creds:
            return {"success": False, "error": "No credentials found"}

        try:
            # For SSH key auth
            if "private_key" in creds:
                # Write temp key file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
                    f.write(creds["private_key"])
                    key_file = f.name
                os.chmod(key_file, 0o600)

                try:
                    # Use ssh command with key
                    ssh_cmd = [
                        "ssh",
                        "-i", key_file,
                        "-o", "StrictHostKeyChecking=accept-new",
                        "-o", "UserKnownHostsFile=/dev/null",
                        "-o", "BatchMode=yes",
                        "-o", "ConnectTimeout=10",
                        "-p", str(node.port),
                        f"{node.ssh_user or 'root'}@{node.host}",
                        "echo", "OK"
                    ]

                    proc = await asyncio.create_subprocess_exec(
                        *ssh_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=15.0
                    )

                    if proc.returncode == 0 and b"OK" in stdout:
                        return {"success": True}
                    else:
                        return {
                            "success": False,
                            "error": stderr.decode().strip() or "SSH connection failed"
                        }
                finally:
                    os.unlink(key_file)

            # For password auth (requires sshpass)
            elif "password" in creds:
                # Check if sshpass is available
                check_sshpass = await asyncio.create_subprocess_exec(
                    "which", "sshpass",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await check_sshpass.communicate()

                if check_sshpass.returncode != 0:
                    return {
                        "success": False,
                        "error": "sshpass not installed (required for password auth test)"
                    }

                ssh_cmd = [
                    "sshpass", "-p", creds["password"],
                    "ssh",
                    "-o", "StrictHostKeyChecking=accept-new",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "ConnectTimeout=10",
                    "-p", str(node.port),
                    f"{node.ssh_user or 'root'}@{node.host}",
                    "echo", "OK"
                ]

                proc = await asyncio.create_subprocess_exec(
                    *ssh_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=15.0
                )

                if proc.returncode == 0 and b"OK" in stdout:
                    return {"success": True}
                else:
                    return {
                        "success": False,
                        "error": stderr.decode().strip() or "SSH password auth failed"
                    }

            else:
                return {"success": False, "error": "No valid credentials found"}

        except asyncio.TimeoutError:
            return {"success": False, "error": "SSH auth timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def verify_connectivity_bulk(
        self,
        node_ids: List[uuid.UUID],
        user_id: uuid.UUID,
        update_status: bool = True
    ) -> Dict[str, Any]:
        """
        Verify connectivity for multiple nodes concurrently.

        Args:
            node_ids: List of node IDs to verify
            user_id: User performing the verification
            update_status: Whether to update node status based on results

        Returns:
            Dict with bulk verification results
        """
        import asyncio

        # Verify all nodes concurrently
        tasks = [
            self.verify_connectivity(node_id, user_id, update_status)
            for node_id in node_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        verified_results = []
        reachable_count = 0
        unreachable_count = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Handle errors gracefully
                verified_results.append({
                    "node_id": node_ids[i],
                    "node_name": "unknown",
                    "host": "unknown",
                    "port": 0,
                    "connection_type": "unknown",
                    "is_reachable": False,
                    "ssh_reachable": False,
                    "response_time_ms": None,
                    "error_message": str(result),
                    "checked_at": datetime.utcnow(),
                    "status_before": "unknown",
                    "status_after": "unknown",
                })
                unreachable_count += 1
            else:
                verified_results.append(result)
                if result["is_reachable"] and result["ssh_reachable"]:
                    reachable_count += 1
                else:
                    unreachable_count += 1

        return {
            "checked_count": len(node_ids),
            "reachable_count": reachable_count,
            "unreachable_count": unreachable_count,
            "results": verified_results,
            "checked_at": datetime.utcnow(),
        }

    # ==========================================================================
    # Node Group Operations
    # ==========================================================================

    async def list_groups(
        self,
        pagination: PaginationParams
    ) -> Tuple[List[NodeGroup], int]:
        """List node groups."""
        query = (
            select(NodeGroup)
            .where(NodeGroup.tenant_id == self.tenant_id)
            .options(selectinload(NodeGroup.nodes), selectinload(NodeGroup.group_vars))
            .order_by(NodeGroup.name)
        )

        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)

        query = query.offset(pagination.offset).limit(pagination.page_size)
        result = await self.db.execute(query)
        groups = result.scalars().all()

        return list(groups), total or 0

    async def create_group(
        self,
        data: NodeGroupCreate,
        user_id: uuid.UUID
    ) -> NodeGroup:
        """Create a new node group."""
        group = NodeGroup(
            tenant_id=self.tenant_id,
            name=data.name,
            display_name=data.display_name or data.name,
            description=data.description,
            parent_id=data.parent_id,
            priority=data.priority
        )
        self.db.add(group)
        await self.db.flush()

        # Add initial variables
        if data.initial_vars:
            group_var = GroupVar(
                tenant_id=self.tenant_id,
                scope="group",
                group_id=group.id,
                vars=data.initial_vars,
                updated_by=user_id
            )
            self.db.add(group_var)

        # Add nodes
        if data.node_ids:
            nodes = await self._get_nodes_by_ids(data.node_ids)
            group.nodes = nodes

        await self.db.commit()
        await self.db.refresh(group)

        await self._audit_log(
            user_id, "create", "node_group", group.id, group.name
        )

        return group

    async def update_group(
        self,
        group_id: uuid.UUID,
        data: NodeGroupUpdate,
        user_id: uuid.UUID
    ) -> NodeGroup:
        """Update a node group."""
        query = select(NodeGroup).where(
            and_(NodeGroup.id == group_id, NodeGroup.tenant_id == self.tenant_id)
        )
        result = await self.db.execute(query)
        group = result.scalar_one_or_none()

        if not group:
            raise NodeManagementError(f"Group {group_id} not found")

        if data.display_name is not None:
            group.display_name = data.display_name
        if data.description is not None:
            group.description = data.description
        if data.parent_id is not None:
            group.parent_id = data.parent_id
        if data.priority is not None:
            group.priority = data.priority
        if data.node_ids is not None:
            nodes = await self._get_nodes_by_ids(data.node_ids)
            group.nodes = nodes

        await self.db.commit()
        await self.db.refresh(group)

        return group

    # ==========================================================================
    # Group Variables
    # ==========================================================================

    async def get_global_vars(self) -> Optional[GroupVar]:
        """Get global (all) variables."""
        query = select(GroupVar).where(
            and_(
                GroupVar.tenant_id == self.tenant_id,
                GroupVar.scope == "all"
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def set_global_vars(
        self,
        data: GroupVarCreate,
        user_id: uuid.UUID
    ) -> GroupVar:
        """Set global variables."""
        existing = await self.get_global_vars()

        if existing:
            existing.vars = data.vars
            existing.version += 1
            existing.updated_by = user_id
            existing.change_description = data.change_description
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        else:
            group_var = GroupVar(
                tenant_id=self.tenant_id,
                scope="all",
                vars=data.vars,
                updated_by=user_id,
                change_description=data.change_description
            )
            self.db.add(group_var)
            await self.db.commit()
            await self.db.refresh(group_var)
            return group_var

    async def get_group_vars(self, group_id: uuid.UUID) -> Optional[GroupVar]:
        """Get variables for a specific group."""
        query = select(GroupVar).where(
            and_(
                GroupVar.tenant_id == self.tenant_id,
                GroupVar.group_id == group_id
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def set_group_vars(
        self,
        group_id: uuid.UUID,
        data: GroupVarUpdate,
        user_id: uuid.UUID
    ) -> GroupVar:
        """Set variables for a group."""
        existing = await self.get_group_vars(group_id)

        if existing:
            if data.merge_strategy == "merge":
                existing.vars = {**existing.vars, **(data.vars or {})}
            elif data.merge_strategy == "delete":
                for key in (data.vars or {}):
                    existing.vars.pop(key, None)
            else:  # replace
                existing.vars = data.vars or {}

            existing.version += 1
            existing.updated_by = user_id
            existing.change_description = data.change_description
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        else:
            group_var = GroupVar(
                tenant_id=self.tenant_id,
                scope="group",
                group_id=group_id,
                vars=data.vars or {},
                updated_by=user_id,
                change_description=data.change_description
            )
            self.db.add(group_var)
            await self.db.commit()
            await self.db.refresh(group_var)
            return group_var

    # ==========================================================================
    # Inventory Generation
    # ==========================================================================

    async def generate_inventory(
        self,
        node_ids: Optional[List[uuid.UUID]] = None,
        group_ids: Optional[List[uuid.UUID]] = None
    ) -> str:
        """Generate Ansible inventory for specified nodes/groups."""
        inventory = {"all": {"hosts": {}, "children": {}}}

        # Get nodes
        if node_ids:
            nodes = await self._get_nodes_by_ids(node_ids)
        elif group_ids:
            nodes = []
            for gid in group_ids:
                group_nodes = await self._get_nodes_in_group(gid)
                nodes.extend(group_nodes)
            nodes = list(set(nodes))  # Deduplicate
        else:
            # All active nodes
            query = select(Node).where(
                and_(
                    Node.tenant_id == self.tenant_id,
                    Node.status.in_([NodeStatus.READY, NodeStatus.NEW])
                )
            )
            result = await self.db.execute(query)
            nodes = result.scalars().all()

        # Build inventory
        for node in nodes:
            host_vars = {
                "ansible_host": node.host,
                "ansible_port": node.port,
            }

            # Set connection type and user based on node connection type
            if node.connection_type == ConnectionType.LOCAL.value:
                host_vars["ansible_connection"] = "local"
                host_vars["ansible_user"] = node.ssh_user or "root"

            elif node.connection_type == ConnectionType.WINRM:
                # WinRM connection for Windows nodes
                host_vars["ansible_connection"] = "winrm"
                host_vars["ansible_user"] = node.ssh_user or "Administrator"

                # Add WinRM-specific credentials
                if node.credentials:
                    creds = await self._get_decrypted_credentials(node.id)
                    if creds and creds.get("type") == "winrm":
                        # WinRM transport (ntlm, kerberos, basic, certificate, credssp)
                        transport = creds.get("transport", "ntlm")
                        host_vars["ansible_winrm_transport"] = transport

                        # Server certificate validation
                        cert_validation = creds.get("server_cert_validation", "validate")
                        if cert_validation == "ignore":
                            host_vars["ansible_winrm_server_cert_validation"] = "ignore"

                        # Determine scheme based on port and cert validation
                        if node.port == 5985:
                            host_vars["ansible_winrm_scheme"] = "http"
                        else:
                            host_vars["ansible_winrm_scheme"] = "https"

                        # Password for most auth methods
                        if "password" in creds:
                            host_vars["ansible_password"] = creds["password"]

                        # Certificate authentication
                        if transport == "certificate":
                            if creds.get("cert_pem"):
                                cert_path = self._write_temp_cert(
                                    node.id, "cert", creds["cert_pem"]
                                )
                                host_vars["ansible_winrm_cert_pem"] = cert_path
                            if creds.get("cert_key_pem"):
                                key_path = self._write_temp_cert(
                                    node.id, "key", creds["cert_key_pem"]
                                )
                                host_vars["ansible_winrm_cert_key_pem"] = key_path

                        # Kerberos realm
                        if transport == "kerberos" and creds.get("kerberos_realm"):
                            host_vars["ansible_winrm_kerberos_delegation"] = True

            else:
                # SSH connection (default)
                host_vars["ansible_user"] = node.ssh_user or "root"

                # Add SSH credentials if available
                if node.credentials:
                    creds = await self._get_decrypted_credentials(node.id)
                    if creds:
                        if "private_key" in creds:
                            # Write key to temp file for Ansible
                            key_path = self._write_temp_key(node.id, creds["private_key"])
                            host_vars["ansible_ssh_private_key_file"] = key_path
                        elif "password" in creds:
                            host_vars["ansible_password"] = creds["password"]

                        # Bastion configuration
                        if creds.get("bastion"):
                            bastion = creds["bastion"]
                            host_vars["ansible_ssh_common_args"] = (
                                f"-o ProxyJump={bastion['user']}@{bastion['host']}:{bastion.get('port', 22)}"
                            )

            inventory["all"]["hosts"][node.name] = host_vars

            # Add to group children
            for group in node.groups:
                if group.name not in inventory["all"]["children"]:
                    inventory["all"]["children"][group.name] = {"hosts": {}}
                inventory["all"]["children"][group.name]["hosts"][node.name] = {}

        return yaml.dump(inventory, default_flow_style=False)

    async def generate_group_vars(
        self,
        group_ids: Optional[List[uuid.UUID]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Generate group_vars structure for Ansible."""
        result = {}

        # Global vars
        global_vars = await self.get_global_vars()
        if global_vars:
            result["all"] = global_vars.vars

        # Group-specific vars
        if group_ids:
            for gid in group_ids:
                group_var = await self.get_group_vars(gid)
                if group_var and group_var.group:
                    result[group_var.group.name] = group_var.vars

        return result

    # ==========================================================================
    # Job Templates
    # ==========================================================================

    async def list_job_templates(
        self,
        category: Optional[str] = None,
        enabled_only: bool = True
    ) -> List[JobTemplate]:
        """List job templates."""
        query = select(JobTemplate).where(JobTemplate.tenant_id == self.tenant_id)

        if category:
            query = query.where(JobTemplate.category == category)
        if enabled_only:
            query = query.where(JobTemplate.enabled == True)

        query = query.order_by(JobTemplate.category, JobTemplate.name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_job_template(self, template_id: uuid.UUID) -> Optional[JobTemplate]:
        """Get a job template by ID."""
        query = select(JobTemplate).where(
            and_(
                JobTemplate.id == template_id,
                JobTemplate.tenant_id == self.tenant_id
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    # ==========================================================================
    # Job Runs
    # ==========================================================================

    async def create_job_run(
        self,
        data: JobRunCreate,
        user_id: uuid.UUID,
        user_email: Optional[str] = None
    ) -> JobRun:
        """Create a new job run."""
        # Get template
        template = await self.get_job_template(data.template_id)
        if not template:
            raise JobExecutionError(f"Template {data.template_id} not found")

        if not template.enabled:
            raise JobExecutionError(f"Template {template.name} is disabled")

        # Validate extra_vars against schema
        if template.input_schema:
            self._validate_extra_vars(data.extra_vars, template.input_schema)

        # Create job run
        job_run = JobRun(
            tenant_id=self.tenant_id,
            template_id=template.id,
            template_snapshot={
                "name": template.name,
                "playbook_path": template.playbook_path,
                "become": template.become,
                "timeout_seconds": template.timeout_seconds
            },
            created_by=user_id,
            created_by_email=user_email,
            target_type=data.target_type,
            target_node_ids=[str(nid) for nid in (data.target_node_ids or [])],
            target_group_ids=[str(gid) for gid in (data.target_group_ids or [])],
            extra_vars={**template.default_vars, **data.extra_vars},
            serial=data.serial or template.default_serial,
            status=JobStatus.PENDING.value,
            artifacts_bucket=settings.node_management.artifacts_bucket,
            artifacts_prefix=f"jobs/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4()}"
        )
        self.db.add(job_run)
        await self.db.flush()

        # Link nodes
        if data.target_node_ids:
            nodes = await self._get_nodes_by_ids(data.target_node_ids)
            job_run.nodes = nodes

        # Generate inventory
        inventory = await self.generate_inventory(
            node_ids=data.target_node_ids,
            group_ids=data.target_group_ids
        )
        job_run.inventory_content = inventory

        await self.db.commit()
        await self.db.refresh(job_run)

        await self._audit_log(
            user_id, "execute", "job_run", job_run.id, template.name,
            request_summary={
                "template": template.name,
                "target_type": data.target_type,
                "node_count": len(data.target_node_ids or [])
            }
        )

        # Enqueue job for worker execution
        if self.job_queue_service:
            job_info = {
                "job_run_id": str(job_run.id),
                "tenant_id": str(self.tenant_id),
                "playbook_path": template.playbook_path,
                "inventory_content": inventory,
                "extra_vars": job_run.extra_vars,
                "target_node_ids": job_run.target_node_ids,
                "target_group_ids": job_run.target_group_ids,
                "template_snapshot": job_run.template_snapshot,
                "become": template.become,
                "become_method": template.become_method,
                "become_user": template.become_user,
                "timeout_seconds": template.timeout_seconds,
                "serial": job_run.serial,
                "artifacts_bucket": job_run.artifacts_bucket,
                "artifacts_prefix": job_run.artifacts_prefix,
            }
            enqueued = await self.job_queue_service.enqueue_job(job_info)
            if not enqueued:
                logger.warning(
                    "Failed to enqueue job - will remain PENDING",
                    job_run_id=str(job_run.id)
                )
        else:
            logger.warning(
                "No job queue service available - job created but not enqueued",
                job_run_id=str(job_run.id)
            )

        logger.info(
            "Job run created",
            job_run_id=str(job_run.id),
            template=template.name,
            status="PENDING"
        )

        return job_run

    async def list_job_runs(
        self,
        pagination: PaginationParams,
        status: Optional[JobStatus] = None,
        template_id: Optional[uuid.UUID] = None,
        node_id: Optional[uuid.UUID] = None
    ) -> Tuple[List[JobRun], int]:
        """List job runs with filtering."""
        query = (
            select(JobRun)
            .where(JobRun.tenant_id == self.tenant_id)
            .options(selectinload(JobRun.template), selectinload(JobRun.nodes))
        )

        if status:
            query = query.where(JobRun.status == status)
        if template_id:
            query = query.where(JobRun.template_id == template_id)
        if node_id:
            query = query.join(job_run_nodes).where(
                job_run_nodes.c.node_id == node_id
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)

        query = query.order_by(JobRun.created_at.desc())
        query = query.offset(pagination.offset).limit(pagination.page_size)

        result = await self.db.execute(query)
        runs = result.scalars().all()

        return list(runs), total or 0

    async def get_job_run(self, job_run_id: uuid.UUID) -> Optional[JobRun]:
        """Get a job run by ID."""
        query = (
            select(JobRun)
            .where(and_(JobRun.id == job_run_id, JobRun.tenant_id == self.tenant_id))
            .options(
                selectinload(JobRun.template),
                selectinload(JobRun.nodes),
                selectinload(JobRun.events)
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def cancel_job_run(
        self,
        job_run_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: Optional[str] = None
    ) -> JobRun:
        """Cancel a running or pending job."""
        job_run = await self.get_job_run(job_run_id)
        if not job_run:
            raise JobExecutionError(f"Job run {job_run_id} not found")

        if job_run.status not in [JobStatus.PENDING.value, JobStatus.RUNNING.value]:
            raise JobExecutionError(
                f"Cannot cancel job in {job_run.status} state"
            )

        job_run.status = JobStatus.CANCELED.value
        job_run.canceled_at = datetime.utcnow()
        job_run.canceled_by = user_id
        job_run.cancellation_reason = reason

        await self.db.commit()
        await self.db.refresh(job_run)

        await self._audit_log(
            user_id, "cancel", "job_run", job_run.id, None,
            diff={"reason": reason}
        )

        return job_run

    # ==========================================================================
    # Statistics
    # ==========================================================================

    async def get_node_stats(self) -> Dict[str, Any]:
        """Get node statistics."""
        # Total count
        total_query = select(func.count()).select_from(Node).where(
            Node.tenant_id == self.tenant_id
        )
        total = await self.db.scalar(total_query)

        # By status
        status_query = (
            select(Node.status, func.count())
            .where(Node.tenant_id == self.tenant_id)
            .group_by(Node.status)
        )
        status_result = await self.db.execute(status_query)
        by_status = {row[0]: row[1] for row in status_result}

        # By node type
        type_query = (
            select(Node.node_type, func.count())
            .where(Node.tenant_id == self.tenant_id)
            .group_by(Node.node_type)
        )
        type_result = await self.db.execute(type_query)
        by_type = {row[0] if row[0] else "generic": row[1] for row in type_result}

        # By accelerator type
        accel_query = (
            select(Accelerator.type, func.count(func.distinct(Accelerator.node_id)))
            .join(Node)
            .where(Node.tenant_id == self.tenant_id)
            .group_by(Accelerator.type)
        )
        accel_result = await self.db.execute(accel_query)
        by_accel = {row[0]: row[1] for row in accel_result}

        return {
            "total": total or 0,
            "by_status": by_status,
            "by_type": by_type,
            "by_accelerator": by_accel,
            "unreachable": by_status.get("UNREACHABLE", 0),
            "maintenance": by_status.get("MAINTENANCE", 0)
        }

    async def get_job_stats(self) -> Dict[str, Any]:
        """Get job execution statistics."""
        # Count by status
        status_query = (
            select(JobRun.status, func.count())
            .where(JobRun.tenant_id == self.tenant_id)
            .group_by(JobRun.status)
        )
        status_result = await self.db.execute(status_query)
        counts = {row[0].value: row[1] for row in status_result}

        total = sum(counts.values())
        succeeded = counts.get("SUCCEEDED", 0)
        failed = counts.get("FAILED", 0)

        success_rate = (succeeded / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "running": counts.get("RUNNING", 0),
            "pending": counts.get("PENDING", 0),
            "succeeded": succeeded,
            "failed": failed,
            "canceled": counts.get("CANCELED", 0),
            "success_rate": round(success_rate, 2)
        }

    # ==========================================================================
    # Helper Methods
    # ==========================================================================

    async def _get_groups_by_ids(self, group_ids: List[uuid.UUID]) -> List[NodeGroup]:
        """Get groups by IDs."""
        query = select(NodeGroup).where(
            and_(
                NodeGroup.id.in_(group_ids),
                NodeGroup.tenant_id == self.tenant_id
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_nodes_by_ids(self, node_ids: List[uuid.UUID]) -> List[Node]:
        """Get nodes by IDs."""
        query = select(Node).where(
            and_(
                Node.id.in_(node_ids),
                Node.tenant_id == self.tenant_id
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_nodes_in_group(self, group_id: uuid.UUID) -> List[Node]:
        """Get all nodes in a group."""
        query = (
            select(Node)
            .join(node_group_association)
            .where(
                and_(
                    node_group_association.c.node_group_id == group_id,
                    Node.tenant_id == self.tenant_id
                )
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_decrypted_credentials(
        self,
        node_id: uuid.UUID
    ) -> Optional[Dict[str, Any]]:
        """Get decrypted credentials for a node."""
        query = select(NodeCredential).where(NodeCredential.node_id == node_id)
        result = await self.db.execute(query)
        cred = result.scalar_one_or_none()

        if not cred:
            return None

        try:
            return self.credential_service.decrypt(cred.encrypted_payload)
        except Exception as e:
            logger.error("Failed to decrypt credentials", node_id=str(node_id), error=str(e))
            return None

    def _write_temp_key(self, node_id: uuid.UUID, private_key: str) -> str:
        """Write SSH key to temp file for Ansible."""
        work_dir = Path(settings.ansible.work_dir)
        keys_dir = work_dir / "keys"
        keys_dir.mkdir(parents=True, exist_ok=True)

        key_path = keys_dir / f"{node_id}.pem"
        key_path.write_text(private_key)
        key_path.chmod(0o600)

        return str(key_path)

    def _write_temp_cert(self, node_id: uuid.UUID, cert_type: str, content: str) -> str:
        """Write WinRM certificate to temp file for Ansible.

        Args:
            node_id: Node ID for unique filename
            cert_type: Either 'cert' or 'key'
            content: PEM-encoded certificate or key content

        Returns:
            Path to the written certificate file
        """
        work_dir = Path(settings.ansible.work_dir)
        certs_dir = work_dir / "certs"
        certs_dir.mkdir(parents=True, exist_ok=True)

        cert_path = certs_dir / f"{node_id}_{cert_type}.pem"
        cert_path.write_text(content)
        cert_path.chmod(0o600)

        return str(cert_path)

    def _validate_extra_vars(
        self,
        extra_vars: Dict[str, Any],
        schema: Dict[str, Any]
    ) -> None:
        """Validate extra_vars against JSON Schema."""
        try:
            import jsonschema
            jsonschema.validate(extra_vars, schema)
        except ImportError:
            logger.warning("jsonschema not installed, skipping validation")
        except jsonschema.ValidationError as e:
            raise JobExecutionError(f"Invalid extra_vars: {e.message}")

    async def _audit_log(
        self,
        actor_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID,
        resource_name: Optional[str] = None,
        diff: Optional[Dict] = None,
        request_summary: Optional[Dict] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> None:
        """Create an audit log entry."""
        log = AuditLog(
            tenant_id=self.tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            diff=diff,
            request_summary=request_summary,
            status=status,
            error_message=error_message
        )
        self.db.add(log)
        # Don't commit here - let the caller commit

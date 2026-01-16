"""
Port Manager Service.

Manages port allocation for deployments to prevent conflicts.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.deployment import PortAllocation


class PortManager:
    """Manages port allocation for deployments."""

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID):
        self.db = db
        self.tenant_id = tenant_id
        self.port_start = settings.deployment.port_range_start
        self.port_end = settings.deployment.port_range_end

    async def allocate_port(
        self,
        node_id: uuid.UUID,
        deployment_id: Optional[uuid.UUID] = None,
        preferred_port: Optional[int] = None,
    ) -> int:
        """
        Allocate a port for a deployment.

        Args:
            node_id: Node to allocate port on
            deployment_id: Optional deployment ID to associate
            preferred_port: Optional preferred port (if available)

        Returns:
            Allocated port number

        Raises:
            ValueError: If no ports available
        """
        # Try preferred port first
        if preferred_port:
            if await self._is_port_available(node_id, preferred_port):
                await self._create_allocation(node_id, preferred_port, deployment_id)
                return preferred_port

        # Find next available port
        allocated_ports = await self._get_allocated_ports(node_id)
        allocated_set = set(allocated_ports)

        for port in range(self.port_start, self.port_end + 1):
            if port not in allocated_set:
                await self._create_allocation(node_id, port, deployment_id)
                return port

        raise ValueError(
            f"No available ports in range [{self.port_start}, {self.port_end}] "
            f"for node {node_id}"
        )

    async def release_port(
        self,
        node_id: uuid.UUID,
        port: int,
    ) -> None:
        """
        Release an allocated port.

        Args:
            node_id: Node the port is allocated on
            port: Port to release
        """
        stmt = select(PortAllocation).where(
            and_(
                PortAllocation.node_id == node_id,
                PortAllocation.port == port,
                PortAllocation.is_active == True,
            )
        )
        result = await self.db.execute(stmt)
        allocation = result.scalar_one_or_none()

        if allocation:
            allocation.is_active = False
            allocation.released_at = datetime.utcnow()

    async def get_allocation(
        self,
        node_id: uuid.UUID,
        port: int,
    ) -> Optional[PortAllocation]:
        """Get port allocation record."""
        stmt = select(PortAllocation).where(
            and_(
                PortAllocation.node_id == node_id,
                PortAllocation.port == port,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_allocations_for_node(
        self,
        node_id: uuid.UUID,
        active_only: bool = True,
    ) -> List[PortAllocation]:
        """Get all port allocations for a node."""
        stmt = select(PortAllocation).where(PortAllocation.node_id == node_id)
        if active_only:
            stmt = stmt.where(PortAllocation.is_active == True)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _is_port_available(self, node_id: uuid.UUID, port: int) -> bool:
        """Check if a port is available on a node."""
        # Check range
        if port < self.port_start or port > self.port_end:
            return False

        stmt = select(PortAllocation).where(
            and_(
                PortAllocation.node_id == node_id,
                PortAllocation.port == port,
                PortAllocation.is_active == True,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is None

    async def _get_allocated_ports(self, node_id: uuid.UUID) -> List[int]:
        """Get list of allocated ports on a node."""
        stmt = select(PortAllocation.port).where(
            and_(
                PortAllocation.node_id == node_id,
                PortAllocation.is_active == True,
            )
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def _create_allocation(
        self,
        node_id: uuid.UUID,
        port: int,
        deployment_id: Optional[uuid.UUID] = None,
    ) -> PortAllocation:
        """Create a new port allocation."""
        allocation = PortAllocation(
            tenant_id=self.tenant_id,
            node_id=node_id,
            port=port,
            deployment_id=deployment_id,
            is_active=True,
        )
        self.db.add(allocation)
        return allocation

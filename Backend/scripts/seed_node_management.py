"""
Node Management Seed Script.

Seeds initial job templates and default node groups.
"""

import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import models
import sys
sys.path.insert(0, '/app')
from app.models.node import JobTemplate, NodeGroup, GroupVar
from app.core.config import settings


# Default Job Templates
DEFAULT_TEMPLATES = [
    {
        "name": "collect_facts",
        "display_name": "收集节点信息",
        "description": "收集节点的硬件配置、系统信息和加速器详情",
        "category": "discovery",
        "playbook_path": "collect_facts.yml",
        "become": True,
        "timeout_seconds": 300,
        "is_system": True,
        "tags": ["discovery", "facts"],
    },
    {
        "name": "install_nvidia_driver",
        "display_name": "安装 NVIDIA 驱动",
        "description": "安装或更新 NVIDIA GPU 驱动、CUDA Toolkit 和相关工具",
        "category": "drivers",
        "playbook_path": "drivers/nvidia.yml",
        "become": True,
        "timeout_seconds": 1800,
        "supports_serial": True,
        "default_serial": 1,
        "is_system": True,
        "tags": ["nvidia", "driver", "cuda"],
        "default_vars": {
            "nvidia_driver_version": "535",
            "install_cuda": True,
            "install_fabricmanager": False,
        },
    },
    {
        "name": "install_amd_driver",
        "display_name": "安装 AMD 驱动",
        "description": "安装或更新 AMD ROCm 驱动",
        "category": "drivers",
        "playbook_path": "drivers/amd.yml",
        "become": True,
        "timeout_seconds": 1800,
        "supports_serial": True,
        "default_serial": 1,
        "is_system": True,
        "tags": ["amd", "rocm", "driver"],
        "default_vars": {
            "rocm_version": "6.0",
        },
    },
    {
        "name": "install_intel_driver",
        "display_name": "安装 Intel 驱动",
        "description": "安装或更新 Intel oneAPI 和 GPU 驱动",
        "category": "drivers",
        "playbook_path": "drivers/intel.yml",
        "become": True,
        "timeout_seconds": 1800,
        "supports_serial": True,
        "default_serial": 1,
        "is_system": True,
        "tags": ["intel", "oneapi", "driver"],
    },
    {
        "name": "install_ascend_driver",
        "display_name": "安装华为 Ascend 驱动",
        "description": "安装或更新华为昇腾 NPU 驱动和 CANN 工具包",
        "category": "drivers",
        "playbook_path": "drivers/ascend.yml",
        "become": True,
        "timeout_seconds": 1800,
        "supports_serial": True,
        "default_serial": 1,
        "is_system": True,
        "tags": ["huawei", "ascend", "npu", "cann"],
        "default_vars": {
            "cann_version": "8.0.RC1",
            "ascend_driver_version": "24.1.rc1",
        },
    },
    {
        "name": "deploy_node_exporter",
        "display_name": "部署 Node Exporter",
        "description": "部署 Prometheus Node Exporter 用于系统指标监控",
        "category": "monitoring",
        "playbook_path": "monitoring/node_exporter.yml",
        "become": True,
        "timeout_seconds": 600,
        "is_system": True,
        "tags": ["monitoring", "prometheus", "node_exporter"],
        "default_vars": {
            "node_exporter_port": 9100,
            "node_exporter_version": "1.7.0",
        },
    },
    {
        "name": "deploy_dcgm_exporter",
        "display_name": "部署 DCGM Exporter",
        "description": "部署 NVIDIA DCGM Exporter 用于 GPU 监控",
        "category": "monitoring",
        "playbook_path": "monitoring/dcgm_exporter.yml",
        "become": True,
        "timeout_seconds": 600,
        "is_system": True,
        "tags": ["monitoring", "nvidia", "dcgm", "prometheus"],
        "default_vars": {
            "dcgm_exporter_port": 9400,
            "deploy_mode": "systemd",
        },
    },
    {
        "name": "connectivity_check",
        "display_name": "连通性检查",
        "description": "检查节点 SSH 连接和基本系统可用性",
        "category": "discovery",
        "playbook_path": "connectivity_check.yml",
        "become": False,
        "timeout_seconds": 60,
        "is_system": True,
        "tags": ["check", "connectivity"],
    },
    {
        "name": "health_check",
        "display_name": "健康检查",
        "description": "全面检查节点健康状态，包括磁盘、内存、CPU负载、GPU温度等",
        "category": "discovery",
        "playbook_path": "health_check.yml",
        "become": True,
        "timeout_seconds": 300,
        "is_system": True,
        "tags": ["check", "health", "monitoring"],
        "default_vars": {
            "disk_warning_percent": 80,
            "disk_critical_percent": 90,
            "memory_warning_percent": 80,
            "check_gpu": True,
        },
    },
]

# Default Node Groups
DEFAULT_GROUPS = [
    {
        "name": "all",
        "display_name": "所有节点",
        "description": "默认分组，包含所有节点",
        "is_system": True,
        "priority": 0,
    },
    {
        "name": "gpu_nodes",
        "display_name": "GPU 节点",
        "description": "配备 GPU 加速器的计算节点",
        "is_system": True,
        "priority": 10,
    },
    {
        "name": "npu_nodes",
        "display_name": "NPU 节点",
        "description": "配备 NPU 加速器的计算节点",
        "is_system": True,
        "priority": 10,
    },
    {
        "name": "cpu_nodes",
        "display_name": "CPU 节点",
        "description": "仅 CPU 的计算节点",
        "is_system": True,
        "priority": 10,
    },
]


async def seed_job_templates(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Seed default job templates."""
    count = 0

    for template_data in DEFAULT_TEMPLATES:
        # Check if template exists
        stmt = select(JobTemplate).where(
            JobTemplate.tenant_id == tenant_id,
            JobTemplate.name == template_data["name"]
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"  - Template '{template_data['name']}' already exists, skipping")
            continue

        template = JobTemplate(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name=template_data["name"],
            display_name=template_data["display_name"],
            description=template_data.get("description"),
            category=template_data["category"],
            playbook_path=template_data["playbook_path"],
            become=template_data.get("become", True),
            become_method="sudo",
            become_user="root",
            timeout_seconds=template_data.get("timeout_seconds", 600),
            max_retries=0,
            supports_serial=template_data.get("supports_serial", False),
            default_serial=template_data.get("default_serial", 0),
            default_vars=template_data.get("default_vars", {}),
            tags=template_data.get("tags", []),
            enabled=True,
            is_system=template_data.get("is_system", False),
            version="1.0.0",
            author="system",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(template)
        count += 1
        print(f"  + Created template: {template_data['name']}")

    return count


async def seed_node_groups(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Seed default node groups."""
    count = 0

    for group_data in DEFAULT_GROUPS:
        # Check if group exists
        stmt = select(NodeGroup).where(
            NodeGroup.tenant_id == tenant_id,
            NodeGroup.name == group_data["name"]
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"  - Group '{group_data['name']}' already exists, skipping")
            continue

        group = NodeGroup(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name=group_data["name"],
            display_name=group_data["display_name"],
            description=group_data.get("description"),
            is_system=group_data.get("is_system", False),
            priority=group_data.get("priority", 50),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(group)
        count += 1
        print(f"  + Created group: {group_data['name']}")

    return count


async def seed_global_vars(session: AsyncSession, tenant_id: uuid.UUID) -> bool:
    """Seed default global variables."""
    # Check if global vars exist
    stmt = select(GroupVar).where(
        GroupVar.tenant_id == tenant_id,
        GroupVar.scope == "all"
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        print("  - Global vars already exist, skipping")
        return False

    global_vars = GroupVar(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        scope="all",
        vars={
            "ansible_python_interpreter": "/usr/bin/python3",
            "ansible_ssh_common_args": "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
            "gather_facts_timeout": 30,
        },
        version=1,
        change_description="Initial default configuration",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(global_vars)
    print("  + Created global vars")
    return True


async def main():
    """Main seed function."""
    print("=" * 60)
    print("Node Management Seed Script")
    print("=" * 60)

    # Get database URL
    database_url = settings.database.dsn.replace("postgresql://", "postgresql+asyncpg://")

    print(f"\nDatabase: {database_url.split('@')[1] if '@' in database_url else database_url}")

    # Create engine and session
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # For multi-tenant, we need a tenant ID
    # In production, you'd pass this as an argument or read from env
    tenant_id = uuid.UUID(settings.default_tenant_id) if hasattr(settings, 'default_tenant_id') else uuid.uuid4()

    print(f"Tenant ID: {tenant_id}")

    async with async_session() as session:
        try:
            # Seed job templates
            print("\n[1/3] Seeding Job Templates...")
            templates_created = await seed_job_templates(session, tenant_id)

            # Seed node groups
            print("\n[2/3] Seeding Node Groups...")
            groups_created = await seed_node_groups(session, tenant_id)

            # Seed global vars
            print("\n[3/3] Seeding Global Variables...")
            vars_created = await seed_global_vars(session, tenant_id)

            # Commit
            await session.commit()

            print("\n" + "=" * 60)
            print("Seed completed successfully!")
            print(f"  - Templates created: {templates_created}")
            print(f"  - Groups created: {groups_created}")
            print(f"  - Global vars created: {1 if vars_created else 0}")
            print("=" * 60)

        except Exception as e:
            print(f"\nError during seeding: {e}")
            await session.rollback()
            raise

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

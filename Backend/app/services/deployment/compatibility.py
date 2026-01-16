"""
Deployment Compatibility Evaluator Service.

Evaluates whether a node can support specific deployment frameworks
based on hardware capabilities, driver versions, and OS requirements.

Reference documentation:
- vLLM Requirements: https://docs.vllm.ai/en/stable/getting_started/installation/gpu/
- vLLM CPU: https://docs.vllm.ai/en/stable/getting_started/installation/cpu/
- vLLM ROCm: https://docs.vllm.ai/en/v0.6.5/getting_started/amd-installation.html
- vLLM Ascend: https://docs.vllm.ai/projects/ascend/en/latest/
- SGLang: https://docs.sglang.io/get_started/install.html
- SGLang Ascend: https://docs.sglang.io/platforms/ascend_npu_support.html
- Xinference: https://inference.readthedocs.io/en/stable/getting_started/installation.html
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.node import Node, Accelerator, NodeFactSnapshot, AcceleratorType
from app.models.deployment import DeploymentCompatibility, DeploymentFramework


@dataclass
class FrameworkRequirements:
    """Framework installation requirements."""

    # Python version requirements (semver-like)
    python_min: str = "3.10"
    python_max: str = "3.13"

    # CUDA requirements for NVIDIA GPUs
    cuda_min: Optional[str] = None
    cuda_recommended: Optional[str] = None

    # ROCm requirements for AMD GPUs
    rocm_min: Optional[str] = None
    rocm_recommended: Optional[str] = None

    # CANN requirements for Ascend NPUs
    cann_min: Optional[str] = None
    cann_recommended: Optional[str] = None

    # OS requirements
    os_families: List[str] = None  # ["debian", "redhat", "darwin"]

    # Compute capability for NVIDIA
    nvidia_compute_capability_min: Optional[str] = None

    # Supported accelerator types
    supported_accelerators: List[str] = None


# Framework requirement definitions based on official documentation
FRAMEWORK_REQUIREMENTS: Dict[DeploymentFramework, FrameworkRequirements] = {
    DeploymentFramework.VLLM: FrameworkRequirements(
        python_min="3.10",
        python_max="3.13",
        cuda_min="12.1",
        cuda_recommended="12.9",
        rocm_min="6.2",
        rocm_recommended="6.2",
        cann_min="8.3",
        cann_recommended="8.3",
        os_families=["debian", "redhat"],  # Linux only
        nvidia_compute_capability_min="7.0",  # V100+
        supported_accelerators=[
            AcceleratorType.NVIDIA_GPU.value,
            AcceleratorType.AMD_GPU.value,
            AcceleratorType.ASCEND_NPU.value,
        ],
    ),
    DeploymentFramework.SGLANG: FrameworkRequirements(
        python_min="3.10",
        python_max="3.13",
        cuda_min="12.1",
        cuda_recommended="12.9",
        rocm_min="6.2",
        rocm_recommended="7.0",
        cann_min="8.3",
        cann_recommended="8.3",
        os_families=["debian", "redhat"],  # Linux only
        nvidia_compute_capability_min="7.5",  # Turing+
        supported_accelerators=[
            AcceleratorType.NVIDIA_GPU.value,
            AcceleratorType.AMD_GPU.value,
            AcceleratorType.ASCEND_NPU.value,
        ],
    ),
    DeploymentFramework.XINFERENCE: FrameworkRequirements(
        python_min="3.9",
        python_max="3.12",
        cuda_min="11.8",
        cuda_recommended="12.4",
        rocm_min="5.7",
        rocm_recommended="6.1",
        os_families=["debian", "redhat", "darwin"],  # Supports macOS
        nvidia_compute_capability_min="6.0",  # Pascal+
        supported_accelerators=[
            AcceleratorType.NVIDIA_GPU.value,
            AcceleratorType.AMD_GPU.value,
            AcceleratorType.INTEL_GPU.value,  # Via llama.cpp
            AcceleratorType.ASCEND_NPU.value,
            AcceleratorType.GENERIC_ACCEL.value,  # Via llama.cpp
        ],
    ),
}


def parse_version(version: Optional[str]) -> Tuple[int, ...]:
    """Parse version string to tuple for comparison."""
    if not version:
        return (0,)
    # Extract numeric parts
    parts = re.findall(r"\d+", version)
    return tuple(int(p) for p in parts) if parts else (0,)


def version_gte(version: str, min_version: str) -> bool:
    """Check if version >= min_version."""
    return parse_version(version) >= parse_version(min_version)


def version_lte(version: str, max_version: str) -> bool:
    """Check if version <= max_version."""
    return parse_version(version) <= parse_version(max_version)


def version_in_range(version: str, min_version: str, max_version: str) -> bool:
    """Check if min_version <= version <= max_version."""
    return version_gte(version, min_version) and version_lte(version, max_version)


@dataclass
class CompatibilityResult:
    """Result of compatibility evaluation."""

    framework: DeploymentFramework
    supported: bool
    reason: Optional[str] = None
    install_profile: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    requirements: Optional[Dict[str, str]] = None


class CompatibilityEvaluator:
    """Evaluates deployment compatibility for nodes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_node(
        self,
        node_id: uuid.UUID,
        frameworks: Optional[List[DeploymentFramework]] = None,
    ) -> List[CompatibilityResult]:
        """
        Evaluate a node's compatibility with deployment frameworks.

        Args:
            node_id: Node to evaluate
            frameworks: Frameworks to check (defaults to all)

        Returns:
            List of compatibility results
        """
        # Get node with accelerators
        stmt = select(Node).where(Node.id == node_id)
        result = await self.db.execute(stmt)
        node = result.scalar_one_or_none()

        if not node:
            raise ValueError(f"Node not found: {node_id}")

        # Get accelerators
        stmt = select(Accelerator).where(Accelerator.node_id == node_id)
        result = await self.db.execute(stmt)
        accelerators = list(result.scalars().all())

        # Get latest facts
        stmt = (
            select(NodeFactSnapshot)
            .where(NodeFactSnapshot.node_id == node_id)
            .order_by(NodeFactSnapshot.collected_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        facts_snapshot = result.scalar_one_or_none()
        facts = facts_snapshot.facts if facts_snapshot else {}

        # Build capabilities from node data
        capabilities = self._build_capabilities(node, accelerators, facts)

        # Evaluate each framework
        frameworks = frameworks or list(DeploymentFramework)
        results = []

        for framework in frameworks:
            result = self._evaluate_framework(framework, capabilities, accelerators, node)
            results.append(result)

            # Cache result in database
            await self._cache_result(node_id, result, capabilities)

        return results

    def _build_capabilities(
        self,
        node: Node,
        accelerators: List[Accelerator],
        facts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build capabilities dictionary from node data."""
        # Extract Python version from facts
        python_version = None
        if facts:
            # Try to find Python version from various sources
            if "ansible_python" in facts:
                python_version = facts["ansible_python"].get("version", {}).get("string")
            elif "ansible_python_version" in facts:
                python_version = facts["ansible_python_version"]

        # Determine OS family
        os_family = None
        if node.os_release:
            os_lower = node.os_release.lower()
            if any(d in os_lower for d in ["ubuntu", "debian"]):
                os_family = "debian"
            elif any(d in os_lower for d in ["centos", "rhel", "rocky", "alma", "fedora"]):
                os_family = "redhat"
            elif "darwin" in os_lower or "macos" in os_lower:
                os_family = "darwin"

        # Extract runtime versions from accelerators
        cuda_version = None
        rocm_version = None
        cann_version = None
        nvidia_driver = None

        for acc in accelerators:
            if acc.type == AcceleratorType.NVIDIA_GPU:
                cuda_version = cuda_version or acc.toolkit_version
                nvidia_driver = nvidia_driver or acc.driver_version
            elif acc.type == AcceleratorType.AMD_GPU:
                rocm_version = rocm_version or acc.toolkit_version
            elif acc.type == AcceleratorType.ASCEND_NPU:
                cann_version = cann_version or acc.toolkit_version

        # Get compute capability for NVIDIA
        compute_capability = None
        for acc in accelerators:
            if acc.type == AcceleratorType.NVIDIA_GPU and acc.compute_capability:
                compute_capability = acc.compute_capability
                break

        return {
            "python_version": python_version,
            "os_family": os_family,
            "os_release": node.os_release,
            "architecture": node.architecture,
            "kernel_version": node.kernel_version,
            "cuda_version": cuda_version,
            "nvidia_driver": nvidia_driver,
            "rocm_version": rocm_version,
            "cann_version": cann_version,
            "compute_capability": compute_capability,
            "accelerator_types": list(set(acc.type.value for acc in accelerators)),
            "accelerator_count": len(accelerators),
            "total_gpu_memory_mb": sum(acc.memory_mb or 0 for acc in accelerators),
        }

    def _evaluate_framework(
        self,
        framework: DeploymentFramework,
        capabilities: Dict[str, Any],
        accelerators: List[Accelerator],
        node: Node,
    ) -> CompatibilityResult:
        """Evaluate a single framework's compatibility."""
        reqs = FRAMEWORK_REQUIREMENTS.get(framework)
        if not reqs:
            return CompatibilityResult(
                framework=framework,
                supported=False,
                reason="Framework not configured for compatibility checking",
            )

        issues = []
        install_profile = "cpu_only"  # Default to CPU-only

        # Check OS family
        if reqs.os_families and capabilities.get("os_family"):
            if capabilities["os_family"] not in reqs.os_families:
                issues.append(
                    f"OS not supported: {capabilities.get('os_release')} "
                    f"(requires: {', '.join(reqs.os_families)})"
                )

        # Check Python version
        python_version = capabilities.get("python_version")
        if python_version:
            if not version_in_range(python_version, reqs.python_min, reqs.python_max):
                issues.append(
                    f"Python version {python_version} not in range "
                    f"[{reqs.python_min}, {reqs.python_max}]"
                )

        # Determine install profile based on accelerators
        accelerator_types = capabilities.get("accelerator_types", [])

        if AcceleratorType.NVIDIA_GPU.value in accelerator_types:
            # NVIDIA GPU path
            cuda_version = capabilities.get("cuda_version")
            compute_cap = capabilities.get("compute_capability")

            if not cuda_version and reqs.cuda_min:
                issues.append("CUDA not detected (required for NVIDIA GPU)")
            elif cuda_version and reqs.cuda_min:
                if not version_gte(cuda_version, reqs.cuda_min):
                    issues.append(
                        f"CUDA version {cuda_version} too old "
                        f"(requires >= {reqs.cuda_min})"
                    )
                else:
                    install_profile = "nvidia_cuda"

            if compute_cap and reqs.nvidia_compute_capability_min:
                if not version_gte(compute_cap, reqs.nvidia_compute_capability_min):
                    issues.append(
                        f"GPU compute capability {compute_cap} too old "
                        f"(requires >= {reqs.nvidia_compute_capability_min})"
                    )

        elif AcceleratorType.AMD_GPU.value in accelerator_types:
            # AMD GPU path
            rocm_version = capabilities.get("rocm_version")

            if not rocm_version and reqs.rocm_min:
                issues.append("ROCm not detected (required for AMD GPU)")
            elif rocm_version and reqs.rocm_min:
                if not version_gte(rocm_version, reqs.rocm_min):
                    issues.append(
                        f"ROCm version {rocm_version} too old "
                        f"(requires >= {reqs.rocm_min})"
                    )
                else:
                    install_profile = "amd_rocm"

        elif AcceleratorType.ASCEND_NPU.value in accelerator_types:
            # Ascend NPU path
            cann_version = capabilities.get("cann_version")

            if not cann_version and reqs.cann_min:
                issues.append("CANN not detected (required for Ascend NPU)")
            elif cann_version and reqs.cann_min:
                if not version_gte(cann_version, reqs.cann_min):
                    issues.append(
                        f"CANN version {cann_version} too old "
                        f"(requires >= {reqs.cann_min})"
                    )
                else:
                    install_profile = "ascend_cann"

        elif capabilities.get("os_family") == "darwin":
            # macOS - check for Apple Silicon
            arch = capabilities.get("architecture", "").lower()
            if "arm" in arch or "aarch64" in arch:
                install_profile = "apple_mlx"
            else:
                install_profile = "cpu_only"

        # Check if framework supports the accelerator types present
        if accelerator_types and reqs.supported_accelerators:
            unsupported = set(accelerator_types) - set(reqs.supported_accelerators)
            if unsupported and not any(
                t in reqs.supported_accelerators for t in accelerator_types
            ):
                issues.append(
                    f"Accelerator types not supported: {', '.join(unsupported)} "
                    f"(supported: {', '.join(reqs.supported_accelerators)})"
                )

        # Build requirements dict for response
        requirements = {
            "python": f">={reqs.python_min},<={reqs.python_max}",
        }
        if reqs.cuda_min:
            requirements["cuda"] = f">={reqs.cuda_min}"
        if reqs.rocm_min:
            requirements["rocm"] = f">={reqs.rocm_min}"
        if reqs.cann_min:
            requirements["cann"] = f">={reqs.cann_min}"

        # Determine if supported
        supported = len(issues) == 0

        return CompatibilityResult(
            framework=framework,
            supported=supported,
            reason="; ".join(issues) if issues else None,
            install_profile=install_profile if supported else None,
            capabilities=capabilities,
            requirements=requirements,
        )

    async def _cache_result(
        self,
        node_id: uuid.UUID,
        result: CompatibilityResult,
        capabilities: Dict[str, Any],
    ) -> None:
        """Cache compatibility result in database."""
        # Check for existing record
        stmt = select(DeploymentCompatibility).where(
            DeploymentCompatibility.node_id == node_id,
            DeploymentCompatibility.framework == result.framework,
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()

        if existing:
            # Update existing
            existing.supported = result.supported
            existing.reason = result.reason
            existing.install_profile = result.install_profile
            existing.capabilities = capabilities
            existing.requirements = result.requirements
            existing.evaluated_at = datetime.utcnow()
        else:
            # Create new
            compat = DeploymentCompatibility(
                node_id=node_id,
                framework=result.framework,
                supported=result.supported,
                reason=result.reason,
                install_profile=result.install_profile,
                capabilities=capabilities,
                requirements=result.requirements,
            )
            self.db.add(compat)

    async def get_cached_compatibility(
        self,
        node_id: uuid.UUID,
        framework: Optional[DeploymentFramework] = None,
    ) -> List[DeploymentCompatibility]:
        """Get cached compatibility results from database."""
        stmt = select(DeploymentCompatibility).where(
            DeploymentCompatibility.node_id == node_id
        )
        if framework:
            stmt = stmt.where(DeploymentCompatibility.framework == framework)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def clear_cache(self, node_id: uuid.UUID) -> None:
        """Clear cached compatibility results for a node."""
        stmt = select(DeploymentCompatibility).where(
            DeploymentCompatibility.node_id == node_id
        )
        result = await self.db.execute(stmt)
        for compat in result.scalars().all():
            await self.db.delete(compat)

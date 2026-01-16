"""
Accelerator Provider Plugins.

Hardware discovery system for GPU/NPU devices.
Each provider implements a common interface to discover and parse accelerator information.

Supported providers:
- NvidiaProvider: NVIDIA GPUs (nvidia-smi, NVML)
- AmdProvider: AMD GPUs (amd-smi)
- IntelProvider: Intel GPUs (xpu-smi)
- AscendProvider: Huawei Ascend NPU (npu-smi)
- GenericPciProvider: Generic PCI device fallback
- THeadNpuProvider: Alibaba T-Head NPU (NPUSMI - framework)
"""

import asyncio
import json
import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.models.node import AcceleratorType
from app.services.node_management.credential_service import CredentialEncryptionError


@dataclass
class AcceleratorInfo:
    """Normalized accelerator information from providers."""

    type: AcceleratorType
    vendor: str
    model: str
    device_id: str
    slot: Optional[int] = None
    bus_id: Optional[str] = None
    numa_node: Optional[int] = None
    memory_mb: Optional[int] = None
    cores: Optional[int] = None
    topology: Dict[str, Any] = field(default_factory=dict)
    mig_capable: bool = False
    mig_mode: Optional[Dict[str, Any]] = None
    compute_capability: Optional[str] = None
    driver_version: Optional[str] = None
    firmware_version: Optional[str] = None
    toolkit_version: Optional[str] = None
    pci_vendor_id: Optional[str] = None
    pci_device_id: Optional[str] = None
    subsystem_vendor_id: Optional[str] = None
    subsystem_device_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "type": self.type.value,
            "vendor": self.vendor,
            "model": self.model,
            "device_id": self.device_id,
            "slot": self.slot,
            "bus_id": self.bus_id,
            "numa_node": self.numa_node,
            "memory_mb": self.memory_mb,
            "cores": self.cores,
            "topology": self.topology,
            "mig_capable": self.mig_capable,
            "mig_mode": self.mig_mode,
            "compute_capability": self.compute_capability,
            "driver_version": self.driver_version,
            "firmware_version": self.firmware_version,
            "toolkit_version": self.toolkit_version,
            "pci_vendor_id": self.pci_vendor_id,
            "pci_device_id": self.pci_device_id,
            "subsystem_vendor_id": self.subsystem_vendor_id,
            "subsystem_device_id": self.subsystem_device_id,
        }


class AcceleratorProviderError(Exception):
    """Base exception for provider errors."""
    pass


class ToolNotFoundError(AcceleratorProviderError):
    """Raised when the required discovery tool is not found."""
    pass


class ProviderParseError(AcceleratorProviderError):
    """Raised when parsing tool output fails."""
    pass


class AcceleratorProvider(ABC):
    """
    Abstract base class for accelerator providers.

    Each provider must implement the detect() method to discover
    accelerator devices on the system.
    """

    name: str = "base"
    enabled: bool = True

    @abstractmethod
    async def detect(self, host: str = "localhost") -> List[AcceleratorInfo]:
        """
        Detect accelerator devices on the system.

        Args:
            host: Target hostname (for remote detection via Ansible)

        Returns:
            List of detected accelerator information

        Raises:
            ToolNotFoundError: If the discovery tool is not installed
            ProviderParseError: If parsing tool output fails
        """
        pass

    async def _run_command(
        self,
        command: List[str],
        timeout: int = 30
    ) -> Tuple[int, str, str]:
        """
        Run a command and return exit code, stdout, stderr.

        Args:
            command: Command and arguments as a list
            timeout: Timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)

        Raises:
            subprocess.TimeoutExpired: If command times out
        """
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            return process.returncode, stdout.decode('utf-8', errors='replace'), stderr.decode('utf-8', errors='replace')
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise


class NvidiaProvider(AcceleratorProvider):
    """
    NVIDIA GPU provider using nvidia-smi.

    Supports:
    - GPU discovery via nvidia-smi
    - MIG (Multi-Instance GPU) capability detection
    - NVLink topology detection
    - Driver and CUDA version detection
    """

    name = "nvidia"

    # PCI Vendor IDs
    NVIDIA_VENDOR_ID = "10de"

    # Known GPU models mapping (PCI device ID to model name)
    KNOWN_GPUS = {
        # Ampere
        "20bf": "A100-SXM4-40GB",
        "20b5": "A100-SXM4-80GB",
        "20b0": "A100-PCIE-40GB",
        "20b1": "A100-PCIE-80GB",
        "20f1": "A30",
        "20f5": "A10G",
        "2235": "L40",
        "2236": "L40S",
        # Hopper
        "2696": "H100-SXM5-80GB",
        "2699": "H100-PCIE-80GB",
        # Ada Lovelace
        "2684": "RTX 6000 Ada",
        "2685": "RTX 5000 Ada",
        # Volta
        "1db1": "V100-SXM2-16GB",
        "1db4": "V100-SXM2-32GB",
        "1db5": "V100-PCIE-16GB",
        "1db6": "V100-PCIE-32GB",
        # Turing
        "1e04": "T4",
        "1e30": "Quadro RTX 8000",
        # Pascal
        "15f0": "P100-PCIE-16GB",
        "15f1": "P100-SXM2-16GB",
    }

    async def detect(self, host: str = "localhost") -> List[AcceleratorInfo]:
        """Detect NVIDIA GPUs using nvidia-smi."""
        # Check if nvidia-smi is available
        code, _, _ = await self._run_command(["which", "nvidia-smi"], timeout=5)
        if code != 0:
            raise ToolNotFoundError("nvidia-smi not found. Please install NVIDIA drivers.")

        # Query GPU information using CSV format for easy parsing
        query = (
            "name,uuid,pci.bus_id,pci.device_id,pci.sub_device_id,"
            "driver_version,memory.total,compute_cap,gpu_uuid,"
            "product_name,serial,mig.mode.current"
        )

        code, stdout, stderr = await self._run_command([
            "nvidia-smi",
            "--query-gpu=" + query,
            "--format=csv,noheader,nounits"
        ], timeout=30)

        if code != 0 and "no devices found" in stderr.lower():
            return []

        if code != 0:
            raise ProviderParseError(f"nvidia-smi failed: {stderr}")

        accelerators = []
        for line in stdout.strip().split('\n'):
            if not line:
                continue

            try:
                info = self._parse_nvidia_smi_line(line)
                accelerators.append(info)
            except Exception as e:
                # Log warning but continue parsing other lines
                print(f"Warning: Failed to parse nvidia-smi line: {e}")

        # Get driver version (once for all GPUs)
        driver_version = await self._get_driver_version()

        # Get CUDA version
        cuda_version = await self._get_cuda_version()

        # Update driver and toolkit versions
        for acc in accelerators:
            if driver_version:
                acc.driver_version = driver_version
            acc.toolkit_version = cuda_version

        # Detect MIG capability and NVLink topology
        await self._detect_advanced_features(accelerators)

        return accelerators

    def _parse_nvidia_smi_line(self, line: str) -> AcceleratorInfo:
        """Parse a single line from nvidia-smi output."""
        parts = [p.strip() for p in line.split(',')]

        if len(parts) < 5:
            raise ProviderParseError(f"Invalid nvidia-smi output: {line}")

        name = parts[0]
        uuid = parts[1]
        bus_id = parts[2]
        device_id = parts[3]
        sub_device_id = parts[4] if len(parts) > 4 else None

        # Parse memory (in MB)
        memory_mb = None
        if len(parts) > 6:
            try:
                memory_mb = int(parts[6])
            except ValueError:
                pass

        # Parse compute capability
        compute_cap = None
        if len(parts) > 7:
            compute_cap = parts[7]

        # Parse MIG mode
        mig_mode = None
        if len(parts) > 10:
            mig_mode_str = parts[10]
            mig_capable = mig_mode_str not in ["N/A", "Disabled", ""]
            if mig_capable:
                mig_mode = {"enabled": mig_mode_str == "Enabled"}

        # Map device ID to known model
        model = self.KNOWN_GPUS.get(device_id.lower(), name)

        return AcceleratorInfo(
            type=AcceleratorType.NVIDIA_GPU,
            vendor="nvidia",
            model=model,
            device_id=uuid,
            bus_id=bus_id,
            memory_mb=memory_mb,
            compute_capability=compute_cap,
            mig_capable=mig_mode is not None and "enabled" in mig_mode,
            mig_mode=mig_mode,
            pci_vendor_id=self.NVIDIA_VENDOR_ID,
            pci_device_id=device_id.lower(),
            subsystem_device_id=sub_device_id.lower() if sub_device_id else None,
        )

    async def _get_driver_version(self) -> Optional[str]:
        """Get NVIDIA driver version."""
        code, stdout, _ = await self._run_command([
            "nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader,nounits"
        ], timeout=10)
        if code == 0 and stdout.strip():
            return stdout.strip().split('\n')[0].strip()
        return None

    async def _get_cuda_version(self) -> Optional[str]:
        """Get CUDA runtime version."""
        code, stdout, _ = await self._run_command([
            "nvidia-smi"
        ], timeout=10)
        if code == 0:
            # Parse from nvidia-smi header output
            match = re.search(r'CUDA Version:\s*([\d.]+)', stdout)
            if match:
                return match.group(1)
        return None

    async def _detect_advanced_features(self, accelerators: List[AcceleratorInfo]):
        """Detect MIG capability and NVLink topology."""
        # Check MIG capability for A100/H100
        for acc in accelerators:
            if "A100" in acc.model or "H100" in acc.model:
                # These are MIG-capable
                acc.mig_capable = True

        # Detect NVLink topology using nvidia-smi topo
        code, stdout, _ = await self._run_command([
            "nvidia-smi", "topo", "-m"
        ], timeout=10)
        if code == 0:
            self._parse_nvlink_topology(stdout, accelerators)

    def _parse_nvlink_topology(self, output: str, accelerators: List[AcceleratorInfo]):
        """Parse NVLink topology from nvidia-smi topo output."""
        # Simple NVLink detection - look for "NV" in connection type
        if "NV" in output or "NVLink" in output:
            for acc in accelerators:
                acc.topology["nvlink"] = True


class AmdProvider(AcceleratorProvider):
    """
    AMD GPU provider using amd-smi.

    Supports ROCm-compatible AMD GPUs.
    Falls back to rocm-smi for older systems.
    """

    name = "amd"

    AMD_VENDOR_ID = "1022"

    KNOWN_GPUS = {
        # CDNA series
        "0x7388": "MI100",
        "0x738c": "MI200",
        "0x738d": "MI210",
        "0x7408": "MI250X",
        "0x7409": "MI250",
        "0x740f": "MI300A",
        "0x740c": "MI300X",
        # RDNA series (consumer)
        "0x73df": "RX 7900XTX",
        "0x73e0": "RX 7900XT",
        "0x73e1": "RX 7800XT",
    }

    async def detect(self, host: str = "localhost") -> List[AcceleratorInfo]:
        """Detect AMD GPUs using amd-smi or rocm-smi."""
        # Try amd-smi first (ROCm 5.0+)
        tool = await self._find_tool(["amdsmi", "rocm-smi"])
        if not tool:
            raise ToolNotFoundError("amd-smi/rocm-smi not found. Please install ROCm.")

        return await self._detect_amdsmi(tool)

    async def _find_tool(self, tools: List[str]) -> Optional[str]:
        """Find which AMD tool is available."""
        for tool in tools:
            code, _, _ = await self._run_command(["which", tool], timeout=5)
            if code == 0:
                return tool
        return None

    async def _detect_amdsmi(self, tool: str) -> List[AcceleratorInfo]:
        """Detect GPUs using amd-smi."""
        # amd-smi supports JSON output
        code, stdout, stderr = await self._run_command([
            tool, "list", "--json"
        ], timeout=30)

        if code != 0:
            # Fallback to legacy rocm-smi parsing
            return await self._detect_rocm_smi(tool)

        try:
            data = json.loads(stdout)
            return self._parse_amdsmi_json(data)
        except json.JSONDecodeError:
            raise ProviderParseError(f"Failed to parse {tool} JSON output")

    def _parse_amdsmi_json(self, data: Dict) -> List[AcceleratorInfo]:
        """Parse amd-smi JSON output."""
        accelerators = []

        # amd-smi JSON structure varies by version
        # Handle common structures
        cards = data.get("card", [])
        if not cards and len(data) > 0:
            # Sometimes data is directly the card list
            cards = [data]

        for i, card in enumerate(cards):
            # Extract GPU info
            model = card.get("product_name", card.get("model", "AMD GPU"))
            device_id = card.get("id", card.get("gpu_id", f"amd-gpu-{i}"))
            bus_id = card.get("bus_id", None)
            memory_mb = None

            # Parse memory
            vram_info = card.get("vram", card.get("memory", {}))
            if isinstance(vram_info, dict):
                vram_total = vram_info.get("total", vram_info.get("total_memory_mb"))
                if vram_total:
                    # Convert to MB if needed
                    memory_mb = int(vram_total) if isinstance(vram_total, int) else None

            accelerators.append(AcceleratorInfo(
                type=AcceleratorType.AMD_GPU,
                vendor="amd",
                model=model,
                device_id=device_id,
                bus_id=bus_id,
                memory_mb=memory_mb,
            ))

        return accelerators

    async def _detect_rocm_smi(self, tool: str) -> List[AcceleratorInfo]:
        """Detect GPUs using legacy rocm-smi."""
        code, stdout, _ = await self._run_command([
            tool, "--showid", "--showmemuse", "--csv"
        ], timeout=30)

        if code != 0:
            raise ProviderParseError(f"{tool} failed: {stdout}")

        accelerators = []
        for line in stdout.strip().split('\n')[1:]:  # Skip header
            if not line:
                continue

            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 3:
                continue

            gpu_id = parts[0]
            model = parts[1] if len(parts) > 1 else "AMD GPU"
            memory_mb = None

            try:
                memory_mb = int(parts[2].replace('MB', '').strip())
            except (ValueError, IndexError):
                pass

            accelerators.append(AcceleratorInfo(
                type=AcceleratorType.AMD_GPU,
                vendor="amd",
                model=model,
                device_id=gpu_id,
                memory_mb=memory_mb,
            ))

        return accelerators


class IntelProvider(AcceleratorProvider):
    """
    Intel GPU provider using xpu-smi.

    Supports Intel Data Center GPU Flex, Max, and Arc series.
    """

    name = "intel"

    INTEL_VENDOR_ID = "8086"

    KNOWN_GPUS = {
        # Data Center GPU Max
        "0x0d55": "Data Center GPU Max 1100",
        "0x0d54": "Data Center GPU Max 1550",
        "0x0d5d": "Data Center GPU Max 1350",
        # Data Center GPU Flex
        "0x56c0": "Data Center GPU Flex 140",
        "0x56c1": "Data Center GPU Flex 170",
        # Arc series (consumer)
        "0x56a0": "Arc A770",
        "0x56a1": "Arc A750",
        "0x56a2": "Arc A580",
    }

    async def detect(self, host: str = "localhost") -> List[AcceleratorInfo]:
        """Detect Intel GPUs using xpu-smi."""
        code, _, _ = await self._run_command(["which", "xpu-smi"], timeout=5)
        if code != 0:
            raise ToolNotFoundError("xpu-smi not found. Please install Intel XPU toolkit.")

        code, stdout, _ = await self._run_command([
            "xpu-smi", "list"
        ], timeout=30)

        if code != 0:
            raise ProviderParseError(f"xpu-smi failed: {stdout}")

        return self._parse_xpu_smi_output(stdout)

    def _parse_xpu_smi_output(self, output: str) -> List[AcceleratorInfo]:
        """Parse xpu-smi output."""
        accelerators = []

        # xpu-smi list output format:
        # ID  Device ID                                    Driver Version
        # 0   0x56C0                                      1.3.26223
        for line in output.strip().split('\n')[1:]:  # Skip header
            if not line or 'ID' in line:
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            try:
                index = int(parts[0])
                device_id = parts[1]
                driver_version = parts[2] if len(parts) > 2 else None

                # Map device ID to model
                model = self.KNOWN_GPUS.get(device_id.upper(), f"Intel GPU {device_id}")

                accelerators.append(AcceleratorInfo(
                    type=AcceleratorType.INTEL_GPU,
                    vendor="intel",
                    model=model,
                    device_id=f"intel-gpu-{index}",
                    pci_device_id=device_id.lstrip('0x').lower(),
                    driver_version=driver_version,
                ))
            except (ValueError, IndexError):
                continue

        return accelerators


class AscendProvider(AcceleratorProvider):
    """
    Huawei Ascend NPU provider using npu-smi.

    Supports Ascend 910, 310, and other NPU series.
    """

    name = "ascend"

    HUAWEI_VENDOR_ID = "19e5"

    KNOWN_NPUS = {
        # Ascend 910 series (training)
        "0xd100": "Ascend 910",
        "0xd1000300": "Ascend 910A",
        "0xd1000301": "Ascend 910B",
        "0xd1000302": "Ascend 910C",
        # Ascend 310 series (inference)
        "0xd801": "Ascend 310",
        "0xd8010300": "Ascend 310P",
        # Ascend 310B series
        "0xd500": "Ascend 310B",
    }

    async def detect(self, host: str = "localhost") -> List[AcceleratorInfo]:
        """Detect Huawei Ascend NPUs using npu-smi."""
        code, _, _ = await self._run_command(["which", "npu-smi"], timeout=5)
        if code != 0:
            raise ToolNotFoundError("npu-smi not found. Please install Ascend toolkit.")

        code, stdout, _ = await self._run_command([
            "npu-smi", "info"
        ], timeout=30)

        if code != 0:
            raise ProviderParseError(f"npu-smi failed: {stdout}")

        return self._parse_npu_smi_output(stdout)

    def _parse_npu_smi_output(self, output: str) -> List[AcceleratorInfo]:
        """Parse npu-smi info output."""
        accelerators = []

        # npu-smi info output format:
        # NPU ID:                    0
        # Product Name:              Ascend 910
        # Version:                   1.0.0
        # ...
        current_npu = {}
        for line in output.strip().split('\n'):
            if not line:
                continue

            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                if key == "NPU ID":
                    if current_npu:
                        accelerators.append(self._build_npu_info(current_npu))
                    current_npu = {"id": value}
                else:
                    current_npu[key] = value

        # Add last NPU
        if current_npu:
            accelerators.append(self._build_npu_info(current_npu))

        return accelerators

    def _build_npu_info(self, npu_data: Dict) -> AcceleratorInfo:
        """Build AcceleratorInfo from npu-smi data."""
        npu_id = npu_data.get("NPU ID", "0")
        product_name = npu_data.get("Product Name", "Ascend NPU")
        version = npu_data.get("Version", None)

        return AcceleratorInfo(
            type=AcceleratorType.ASCEND_NPU,
            vendor="huawei",
            model=product_name,
            device_id=f"ascend-npu-{npu_id}",
            driver_version=version,
        )


class THeadNpuProvider(AcceleratorProvider):
    """
    Alibaba T-Head NPU provider (framework/placeholder).

    T-Head NPUs use NPUSMI or vendor-specific tools.
    This provider implements the framework for future enhancement.
    """

    name = "thead"

    T_HEAD_VENDOR_ID = "1ded"

    async def detect(self, host: str = "localhost") -> List[AcceleratorInfo]:
        """
        Detect T-Head NPUs.

        Note: This is a placeholder implementation.
        Actual implementation depends on the specific T-Head NPU model
        and its SMI tool.
        """
        # Check for NPUSMI tool
        code, _, _ = await self._run_command(["which", "npusmi"], timeout=5)
        if code != 0:
            # Fall back to generic PCI detection
            return await self._detect_via_pci()

        # TODO: Implement NPUSMI parsing when tool specification is available
        raise ToolNotFoundError(
            "T-Head NPUSMI found but parser not implemented. "
            "Please check vendor documentation for NPUSMI command format."
        )

    async def _detect_via_pci(self) -> List[AcceleratorInfo]:
        """Detect T-Head NPUs via PCI (fallback)."""
        # Use lspci to find T-Head devices
        code, stdout, _ = await self._run_command([
            "lspci", "-nn", "-d", f"{self.T_HEAD_VENDOR_ID}:"
        ], timeout=10)

        if code != 0 or not stdout.strip():
            return []

        accelerators = []
        for line in stdout.strip().split('\n'):
            if not line:
                continue

            # Parse lspci output
            # Example: "1a:00.0 Processing accelerators [1200]: Device 1ded,DEVICE_ID (rev 01)"
            parts = line.split(':')
            if len(parts) >= 2:
                bus_id = parts[0].strip()
                device_id = self._extract_pci_id(line)

                accelerators.append(AcceleratorInfo(
                    type=AcceleratorType.T_HEAD_NPU,
                    vendor="t-head",
                    model="T-Head NPU",
                    device_id=f"thead-npu-{bus_id}",
                    bus_id=bus_id,
                    pci_vendor_id=self.T_HEAD_VENDOR_ID,
                    pci_device_id=device_id,
                ))

        return accelerators

    def _extract_pci_id(self, line: str) -> Optional[str]:
        """Extract PCI device ID from lspci output."""
        # Look for pattern like "1ded,1234"
        match = re.search(r'1ded[,:]([0-9a-fA-F]{4})', line)
        if match:
            return match.group(1).lower()
        return None


class GenericPciProvider(AcceleratorProvider):
    """
    Generic PCI accelerator provider as fallback.

    Detects any accelerator-class PCI devices even without vendor tools.
    Useful for unknown or unsupported accelerators.
    """

    name = "generic"

    # PCI classes for accelerators
    ACCELERATOR_PCI_CLASSES = {
        "0300": "VGA compatible controller",  # Legacy GPU class
        "0302": "3D controller",  # Modern GPU class
        "1200": "Processing accelerators",  # Accelerator class
    }

    async def detect(self, host: str = "localhost") -> List[AcceleratorInfo]:
        """Detect accelerators via PCI enumeration."""
        code, stdout, _ = await self._run_command(["which", "lspci"], timeout=5)
        if code != 0:
            raise ToolNotFoundError("lspci not found. Please install pciutils.")

        accelerators = []

        # Get all accelerator-class devices
        for pci_class, class_name in self.ACCELERATOR_PCI_CLASSES.items():
            code, class_output, _ = await self._run_command([
                "lspci", "-nn", "-d", f":{pci_class}"
            ], timeout=10)

            if code == 0 and class_output.strip():
                accelerators.extend(self._parse_lspci_output(class_output, pci_class))

        return accelerators

    def _parse_lspci_output(self, output: str, pci_class: str) -> List[AcceleratorInfo]:
        """Parse lspci output for accelerators."""
        accelerators = []

        for line in output.strip().split('\n'):
            if not line:
                continue

            # Parse lspci output
            # Format: "bus_id: description [vendor_id,device_id]"
            parts = line.split(':', 1)
            if len(parts) < 2:
                continue

            bus_id = parts[0].strip()
            description = parts[1].strip()

            # Extract vendor and device IDs
            vendor_id = None
            device_id = None

            # Look for [vendor_id,device_id] pattern
            id_match = re.search(r'\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]', description)
            if id_match:
                vendor_id = id_match.group(1).lower()
                device_id = id_match.group(2).lower()

                # Try to identify vendor
                vendor = self._identify_vendor(vendor_id)
                model = f"GPU {device_id.upper()}"
            else:
                vendor = "unknown"
                model = description.split('[')[0].strip() if '[' in description else description

            accelerators.append(AcceleratorInfo(
                type=AcceleratorType.GENERIC_ACCEL,
                vendor=vendor,
                model=model,
                device_id=f"generic-pci-{bus_id}",
                bus_id=bus_id,
                pci_vendor_id=vendor_id,
                pci_device_id=device_id,
            ))

        return accelerators

    def _identify_vendor(self, vendor_id: str) -> str:
        """Identify vendor from PCI vendor ID."""
        vendors = {
            "10de": "nvidia",
            "1002": "amd",
            "8086": "intel",
            "19e5": "huawei",
            "1ded": "t-head",
        }
        return vendors.get(vendor_id.lower(), "unknown")


# Provider registry
PROVIDERS: List[AcceleratorProvider] = [
    NvidiaProvider(),
    AmdProvider(),
    IntelProvider(),
    AscendProvider(),
    THeadNpuProvider(),
    GenericPciProvider(),
]

PROVIDER_MAP: Dict[str, AcceleratorProvider] = {
    p.name: p for p in PROVIDERS
}


async def detect_accelerators(
    providers: Optional[List[str]] = None
) -> List[AcceleratorInfo]:
    """
    Detect accelerators using specified providers.

    Args:
        providers: List of provider names to use. None for all.

    Returns:
        List of detected accelerators

    Raises:
        AcceleratorProviderError: If all providers fail
    """
    if providers is None:
        providers_list = PROVIDERS
    else:
        providers_list = [PROVIDER_MAP[p] for p in providers if p in PROVIDER_MAP]

    all_accelerators = []
    errors = []

    for provider in providers_list:
        try:
            accelerators = await provider.detect()
            all_accelerators.extend(accelerators)
        except ToolNotFoundError:
            # Tool not available is expected for some providers
            errors.append(f"{provider.name}: tool not found")
        except Exception as e:
            errors.append(f"{provider.name}: {str(e)}")

    if not all_accelerators and errors:
        # Log warnings but don't fail - might just have no accelerators
        print(f"Accelerator detection warnings: {errors}")

    return all_accelerators


def parse_ansible_facts(facts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse Ansible facts to extract accelerator information.

    Called when facts are collected via Ansible playbook.

    Args:
        facts: Ansible facts dictionary

    Returns:
        List of accelerator info dictionaries ready for database insertion
    """
    accelerators = []

    # Check for ansible nvidia_gpu facts
    if "nvidia_gpu" in facts and isinstance(facts["nvidia_gpu"], dict):
        nvidia_facts = facts["nvidia_gpu"]
        for device in nvidia_facts.get("devices", []):
            accelerators.append({
                "type": AcceleratorType.NVIDIA_GPU.value,
                "vendor": "nvidia",
                "model": device.get("name"),
                "device_id": device.get("uuid"),
                "bus_id": device.get("pci_bus_id"),
                "memory_mb": device.get("memory_total"),
                "compute_capability": device.get("compute_cap"),
                "driver_version": nvidia_facts.get("driver_version"),
            })

    # Check for AMD GPU facts
    if "amd_gpu" in facts:
        # Parse AMD-specific facts
        for device in facts["amd_gpu"].get("devices", []):
            accelerators.append({
                "type": AcceleratorType.AMD_GPU.value,
                "vendor": "amd",
                "model": device.get("product_name"),
                "device_id": device.get("id"),
                "memory_mb": device.get("vram_total"),
            })

    # Check for custom accelerator facts (set by our collect_facts playbook)
    if "noveris_accelerators" in facts:
        for acc in facts["noveris_accelerators"]:
            accelerators.append(acc)

    return accelerators


# Utility functions for Ansible integration
def generate_collect_facts_playbook() -> str:
    """
    Generate the collect_facts playbook for hardware discovery.

    Returns:
        Playbook YAML content
    """
    return """---
- name: Collect Hardware Facts
  hosts: all
  gather_facts: true
  become: true
  tasks:
    - name: Check for NVIDIA GPUs
      ansible.builtin.command: nvidia-smi --query-gpu=name,uuid,pci.bus_id,pci.device_id,memory.total,compute_cap --format=csv,noheader,nounits
      register: nvidia_output
      failed_when: false
      changed_when: false

    - name: Parse NVIDIA GPU info
      ansible.builtin.set_fact:
        nvidia_gpus: "{{ nvidia_output.stdout_lines | map('regex_replace', '^\\s*(\\d+),(.*)$', '\\\\2') | list }}"
      when: nvidia_output.rc == 0

    - name: Check for AMD GPUs
      ansible.builtin.command: roc-smi --showid --showmemuse --csv
      register: amd_output
      failed_when: false
      changed_when: false

    - name: Check lspci for accelerators
      ansible.builtin.command: lspci -nn -d :1200
      register: lspci_accel
      failed_when: false
      changed_when: false

    - name: Collect CPU info
      ansible.builtin.setup:
        filter:
          - ansible_processor
          - ansible_processor_cores
          - ansible_processor_vcpus
          - ansible_architecture
          - ansible_memtotal_mb
          - ansible_swaptotal_mb

    - name: Collect network info
      ansible.builtin.setup:
        filter:
          - ansible_default_ipv4
          - ansible_default_ipv6
          - ansible_interfaces

    - name: Collect disk info
      ansible.builtin.setup:
        filter:
          - ansible_mounts
          - ansible_devices

    - name: Compile accelerator facts
      ansible.builtin.set_fact:
        noveris_accelerators: []
        noveris_facts_collected: true
"""

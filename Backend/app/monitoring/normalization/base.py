"""
Base Accelerator Metrics Normalization Adapter.

This module defines the standard metrics interface and base adapter class
for normalizing GPU/NPU metrics from different vendors.

Standard Metrics (Platform-Wide):
- accelerator_up: Device availability (1=up, 0=down)
- accelerator_temperature_celsius: Device temperature
- accelerator_power_watts: Power consumption
- accelerator_fan_speed_rpm: Fan speed (if available)
- accelerator_memory_total_bytes: Total device memory
- accelerator_memory_used_bytes: Used device memory
- accelerator_memory_free_bytes: Free device memory
- accelerator_memory_utilization_ratio: Memory utilization (0-1)
- accelerator_compute_utilization_ratio: Compute utilization (0-1)
- accelerator_ecc_errors_total: ECC error count
- accelerator_link_nvlink_up: NVLink status (if available)
- accelerator_pcie_gen: PCIe generation
- accelerator_pcie_width: PCIe lane width
- accelerator_partition_type: Partition type (MIG, vGPU)

Standard Labels:
- vendor: nvidia, huawei_ascend, aliyun_npu, amd, intel
- model: Device model name
- device_id: Device index/ID
- device_uuid: Device UUID (if available)
- node_id: Node identifier
- tenant_id: Tenant identifier
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


class AcceleratorVendor(str, Enum):
    """Accelerator vendor types."""

    NVIDIA = "nvidia"
    HUAWEI_ASCEND = "huawei_ascend"
    ALIYUN_NPU = "aliyun_npu"
    AMD = "amd"
    INTEL = "intel"
    CUSTOM = "custom"


class UnitConversion(str, Enum):
    """Unit conversion types."""

    NONE = "none"
    MIB_TO_BYTES = "mib_to_bytes"
    GIB_TO_BYTES = "gib_to_bytes"
    KB_TO_BYTES = "kb_to_bytes"
    MB_TO_BYTES = "mb_to_bytes"
    GB_TO_BYTES = "gb_to_bytes"
    PERCENT_TO_RATIO = "percent_to_ratio"
    CELSIUS_TO_CELSIUS = "celsius"
    WATTS_TO_WATTS = "watts"
    MILLIWATTS_TO_WATTS = "milliwatts_to_watts"
    RPM_TO_RPM = "rpm"


@dataclass
class NormalizedMetric:
    """A normalized metric value."""

    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    unit: Optional[str] = None

    def to_prometheus_format(self) -> str:
        """Convert to Prometheus text format."""
        label_str = ""
        if self.labels:
            label_parts = [f'{k}="{v}"' for k, v in self.labels.items()]
            label_str = "{" + ", ".join(label_parts) + "}"

        return f"{self.name}{label_str} {self.value}"


@dataclass
class DeviceInfo:
    """Accelerator device information."""

    device_id: str
    vendor: AcceleratorVendor
    model: str
    uuid: Optional[str] = None
    serial: Optional[str] = None
    pcie_bus_id: Optional[str] = None
    memory_total_bytes: Optional[int] = None
    compute_capability: Optional[str] = None
    driver_version: Optional[str] = None
    firmware_version: Optional[str] = None
    partition_type: Optional[str] = None  # MIG, vGPU, etc.
    partition_id: Optional[str] = None


@dataclass
class MetricMapping:
    """Mapping from source metric to normalized metric."""

    source_metric: str
    target_metric: str
    unit_conversion: UnitConversion = UnitConversion.NONE
    label_mapping: Dict[str, str] = field(default_factory=dict)
    extra_labels: Dict[str, str] = field(default_factory=dict)
    multiplier: float = 1.0


class BaseAcceleratorAdapter(ABC):
    """
    Base class for accelerator metrics normalization adapters.

    All vendor-specific adapters should inherit from this class and implement
    the abstract methods for collecting and normalizing metrics.
    """

    def __init__(
        self,
        vendor: AcceleratorVendor,
        config: Dict[str, Any],
        mapping: Dict[str, MetricMapping],
        label_mapping: Dict[str, str],
        extra_labels: Dict[str, str],
    ):
        """
        Initialize the adapter.

        Args:
            vendor: Accelerator vendor
            config: Adapter configuration
            mapping: Metric mappings (source -> normalized)
            label_mapping: Label name mappings
            extra_labels: Additional labels to add to all metrics
        """
        self.vendor = vendor
        self.config = config
        self.mapping = mapping
        self.label_mapping = label_mapping
        self.extra_labels = extra_labels
        self._last_collection: Optional[datetime] = None
        self._last_error: Optional[str] = None

    @property
    def vendor_name(self) -> str:
        """Get vendor name string."""
        return self.vendor.value

    @abstractmethod
    async def collect_metrics(self) -> List[NormalizedMetric]:
        """
        Collect and normalize metrics from the accelerator.

        Returns:
            List of normalized metrics
        """
        pass

    @abstractmethod
    async def get_devices(self) -> List[DeviceInfo]:
        """
        Get information about available devices.

        Returns:
            List of device information
        """
        pass

    @abstractmethod
    async def health_check(self) -> Tuple[bool, str]:
        """
        Check adapter health.

        Returns:
            Tuple of (is_healthy, message)
        """
        pass

    def convert_unit(self, value: float, conversion: UnitConversion) -> float:
        """
        Convert metric value to standard unit.

        Args:
            value: Original value
            conversion: Conversion type

        Returns:
            Converted value
        """
        conversions = {
            UnitConversion.NONE: lambda v: v,
            UnitConversion.MIB_TO_BYTES: lambda v: v * 1024 * 1024,
            UnitConversion.GIB_TO_BYTES: lambda v: v * 1024 * 1024 * 1024,
            UnitConversion.KB_TO_BYTES: lambda v: v * 1024,
            UnitConversion.MB_TO_BYTES: lambda v: v * 1000 * 1000,
            UnitConversion.GB_TO_BYTES: lambda v: v * 1000 * 1000 * 1000,
            UnitConversion.PERCENT_TO_RATIO: lambda v: v / 100.0,
            UnitConversion.CELSIUS_TO_CELSIUS: lambda v: v,
            UnitConversion.WATTS_TO_WATTS: lambda v: v,
            UnitConversion.MILLIWATTS_TO_WATTS: lambda v: v / 1000.0,
            UnitConversion.RPM_TO_RPM: lambda v: v,
        }

        converter = conversions.get(conversion, lambda v: v)
        return converter(value)

    def normalize_labels(self, source_labels: Dict[str, str]) -> Dict[str, str]:
        """
        Normalize label names according to mapping.

        Args:
            source_labels: Original labels

        Returns:
            Normalized labels
        """
        normalized = {}

        # Apply label mapping
        for source_key, value in source_labels.items():
            if source_key in self.label_mapping:
                normalized[self.label_mapping[source_key]] = value
            else:
                normalized[source_key] = value

        # Add extra labels
        normalized.update(self.extra_labels)

        # Always add vendor
        normalized["vendor"] = self.vendor_name

        return normalized

    def create_metric(
        self,
        name: str,
        value: float,
        labels: Dict[str, str],
        unit: Optional[str] = None,
    ) -> NormalizedMetric:
        """
        Create a normalized metric.

        Args:
            name: Metric name
            value: Metric value
            labels: Metric labels
            unit: Metric unit

        Returns:
            NormalizedMetric instance
        """
        return NormalizedMetric(
            name=name,
            value=value,
            labels=self.normalize_labels(labels),
            timestamp=datetime.utcnow(),
            unit=unit,
        )


# =============================================================================
# Default Metric Mappings
# =============================================================================

# NVIDIA DCGM Exporter default mappings
NVIDIA_DCGM_MAPPING = {
    "DCGM_FI_DEV_GPU_TEMP": MetricMapping(
        source_metric="DCGM_FI_DEV_GPU_TEMP",
        target_metric="accelerator_temperature_celsius",
        unit_conversion=UnitConversion.CELSIUS_TO_CELSIUS,
    ),
    "DCGM_FI_DEV_POWER_USAGE": MetricMapping(
        source_metric="DCGM_FI_DEV_POWER_USAGE",
        target_metric="accelerator_power_watts",
        unit_conversion=UnitConversion.WATTS_TO_WATTS,
    ),
    "DCGM_FI_DEV_FB_USED": MetricMapping(
        source_metric="DCGM_FI_DEV_FB_USED",
        target_metric="accelerator_memory_used_bytes",
        unit_conversion=UnitConversion.MIB_TO_BYTES,
    ),
    "DCGM_FI_DEV_FB_FREE": MetricMapping(
        source_metric="DCGM_FI_DEV_FB_FREE",
        target_metric="accelerator_memory_free_bytes",
        unit_conversion=UnitConversion.MIB_TO_BYTES,
    ),
    "DCGM_FI_DEV_FB_TOTAL": MetricMapping(
        source_metric="DCGM_FI_DEV_FB_TOTAL",
        target_metric="accelerator_memory_total_bytes",
        unit_conversion=UnitConversion.MIB_TO_BYTES,
    ),
    "DCGM_FI_DEV_GPU_UTIL": MetricMapping(
        source_metric="DCGM_FI_DEV_GPU_UTIL",
        target_metric="accelerator_compute_utilization_ratio",
        unit_conversion=UnitConversion.PERCENT_TO_RATIO,
    ),
    "DCGM_FI_DEV_MEM_COPY_UTIL": MetricMapping(
        source_metric="DCGM_FI_DEV_MEM_COPY_UTIL",
        target_metric="accelerator_memory_utilization_ratio",
        unit_conversion=UnitConversion.PERCENT_TO_RATIO,
    ),
    "DCGM_FI_DEV_ECC_DBE_VOL_TOTAL": MetricMapping(
        source_metric="DCGM_FI_DEV_ECC_DBE_VOL_TOTAL",
        target_metric="accelerator_ecc_errors_total",
        unit_conversion=UnitConversion.NONE,
    ),
}

# NVIDIA DCGM label mapping
NVIDIA_DCGM_LABEL_MAPPING = {
    "gpu": "device_id",
    "UUID": "device_uuid",
    "modelName": "model",
    "Hostname": "hostname",
}

# Huawei Ascend NPU default mappings
ASCEND_NPU_MAPPING = {
    "npu_chip_info_temperature": MetricMapping(
        source_metric="npu_chip_info_temperature",
        target_metric="accelerator_temperature_celsius",
        unit_conversion=UnitConversion.CELSIUS_TO_CELSIUS,
    ),
    "npu_chip_info_power": MetricMapping(
        source_metric="npu_chip_info_power",
        target_metric="accelerator_power_watts",
        unit_conversion=UnitConversion.WATTS_TO_WATTS,
    ),
    "npu_chip_info_hbm_used_memory": MetricMapping(
        source_metric="npu_chip_info_hbm_used_memory",
        target_metric="accelerator_memory_used_bytes",
        unit_conversion=UnitConversion.MB_TO_BYTES,
    ),
    "npu_chip_info_hbm_total_memory": MetricMapping(
        source_metric="npu_chip_info_hbm_total_memory",
        target_metric="accelerator_memory_total_bytes",
        unit_conversion=UnitConversion.MB_TO_BYTES,
    ),
    "npu_chip_info_utilization": MetricMapping(
        source_metric="npu_chip_info_utilization",
        target_metric="accelerator_compute_utilization_ratio",
        unit_conversion=UnitConversion.PERCENT_TO_RATIO,
    ),
    "npu_chip_info_health_status": MetricMapping(
        source_metric="npu_chip_info_health_status",
        target_metric="accelerator_up",
        unit_conversion=UnitConversion.NONE,
    ),
}

# Huawei Ascend NPU label mapping
ASCEND_NPU_LABEL_MAPPING = {
    "id": "device_id",
    "name": "model",
    "vdie_id": "device_uuid",
}

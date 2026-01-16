"""
NVIDIA GPU Metrics Normalization Adapter.

This module provides adapter implementations for NVIDIA GPU metrics:
- DCGM Exporter (recommended for data center)
- nvidia-smi based exporter (fallback)

Reference:
- DCGM Exporter: https://github.com/NVIDIA/dcgm-exporter
- DCGM Metrics: https://docs.nvidia.com/datacenter/dcgm/latest/gpu-telemetry/dcgm-exporter.html
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
import structlog

from app.monitoring.clients.prometheus import PrometheusClient
from app.monitoring.normalization.base import (
    AcceleratorVendor,
    BaseAcceleratorAdapter,
    DeviceInfo,
    MetricMapping,
    NormalizedMetric,
    NVIDIA_DCGM_LABEL_MAPPING,
    NVIDIA_DCGM_MAPPING,
    UnitConversion,
)

logger = structlog.get_logger(__name__)


class NvidiaDcgmAdapter(BaseAcceleratorAdapter):
    """
    NVIDIA DCGM Exporter adapter.

    Collects GPU metrics from DCGM Exporter's Prometheus endpoint.
    This is the recommended adapter for NVIDIA data center GPUs.

    Configuration:
        {
            "exporter_url": "http://localhost:9400",
            "metrics_path": "/metrics",
            "timeout_seconds": 10
        }
    """

    def __init__(
        self,
        config: Dict[str, Any],
        mapping: Optional[Dict[str, MetricMapping]] = None,
        label_mapping: Optional[Dict[str, str]] = None,
        extra_labels: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize NVIDIA DCGM adapter.

        Args:
            config: Adapter configuration
            mapping: Custom metric mappings (defaults to NVIDIA_DCGM_MAPPING)
            label_mapping: Custom label mappings
            extra_labels: Additional labels
        """
        # Convert dict mapping to MetricMapping objects if needed
        final_mapping = {}
        source_mapping = mapping or NVIDIA_DCGM_MAPPING

        for key, value in source_mapping.items():
            if isinstance(value, MetricMapping):
                final_mapping[key] = value
            elif isinstance(value, dict):
                final_mapping[key] = MetricMapping(
                    source_metric=value.get("source_metric", key),
                    target_metric=value["target"],
                    unit_conversion=UnitConversion(value.get("unit", "none")),
                )
            else:
                final_mapping[key] = value

        super().__init__(
            vendor=AcceleratorVendor.NVIDIA,
            config=config,
            mapping=final_mapping,
            label_mapping=label_mapping or NVIDIA_DCGM_LABEL_MAPPING,
            extra_labels=extra_labels or {},
        )

        self.exporter_url = config.get("exporter_url", "http://localhost:9400")
        self.metrics_path = config.get("metrics_path", "/metrics")
        self.timeout_seconds = config.get("timeout_seconds", 10)

        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _parse_prometheus_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse Prometheus text format.

        Args:
            text: Prometheus text format metrics

        Returns:
            List of parsed metrics
        """
        metrics = []
        lines = text.strip().split("\n")

        for line in lines:
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Parse metric line
            # Format: metric_name{label1="value1", label2="value2"} value
            match = re.match(
                r'([a-zA-Z_:][a-zA-Z0-9_:]*)\{([^}]*)\}\s+([0-9.eE+-]+)',
                line
            )

            if match:
                metric_name = match.group(1)
                labels_str = match.group(2)
                value_str = match.group(3)

                # Parse labels
                labels = {}
                if labels_str:
                    label_matches = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"', labels_str)
                    for label_name, label_value in label_matches:
                        labels[label_name] = label_value

                try:
                    value = float(value_str)
                    metrics.append({
                        "name": metric_name,
                        "labels": labels,
                        "value": value,
                    })
                except ValueError:
                    continue
            else:
                # Try without labels
                match = re.match(r'([a-zA-Z_:][a-zA-Z0-9_:]*)\s+([0-9.eE+-]+)', line)
                if match:
                    try:
                        metrics.append({
                            "name": match.group(1),
                            "labels": {},
                            "value": float(match.group(2)),
                        })
                    except ValueError:
                        continue

        return metrics

    async def collect_metrics(self) -> List[NormalizedMetric]:
        """
        Collect and normalize metrics from DCGM Exporter.

        Returns:
            List of normalized metrics
        """
        normalized_metrics = []

        try:
            client = await self._get_client()
            response = await client.get(f"{self.exporter_url}{self.metrics_path}")
            response.raise_for_status()

            raw_metrics = self._parse_prometheus_text(response.text)
            self._last_collection = datetime.utcnow()
            self._last_error = None

            for raw in raw_metrics:
                metric_name = raw["name"]

                # Check if we have a mapping for this metric
                if metric_name in self.mapping:
                    mapping = self.mapping[metric_name]

                    # Convert value
                    converted_value = self.convert_unit(raw["value"], mapping.unit_conversion)
                    if mapping.multiplier != 1.0:
                        converted_value *= mapping.multiplier

                    # Create normalized metric
                    normalized = self.create_metric(
                        name=mapping.target_metric,
                        value=converted_value,
                        labels=raw["labels"],
                    )
                    normalized_metrics.append(normalized)

            # Add accelerator_up metric based on presence of temperature data
            device_temps = {}
            for metric in normalized_metrics:
                if metric.name == "accelerator_temperature_celsius":
                    device_id = metric.labels.get("device_id", "0")
                    device_temps[device_id] = 1.0

            for device_id in device_temps:
                up_metric = self.create_metric(
                    name="accelerator_up",
                    value=1.0,
                    labels={"device_id": device_id},
                )
                normalized_metrics.append(up_metric)

            logger.info(
                "nvidia_dcgm_metrics_collected",
                metric_count=len(normalized_metrics),
            )

        except Exception as e:
            self._last_error = str(e)
            logger.error("nvidia_dcgm_collection_error", error=str(e))

        return normalized_metrics

    async def get_devices(self) -> List[DeviceInfo]:
        """
        Get information about available NVIDIA GPUs.

        Returns:
            List of device information
        """
        devices = []

        try:
            metrics = await self.collect_metrics()

            # Group metrics by device_id
            device_metrics: Dict[str, Dict[str, Any]] = {}

            for metric in metrics:
                device_id = metric.labels.get("device_id", "0")
                if device_id not in device_metrics:
                    device_metrics[device_id] = {
                        "labels": metric.labels,
                    }

                # Extract device info from metrics
                if metric.name == "accelerator_memory_total_bytes":
                    device_metrics[device_id]["memory_total"] = int(metric.value)

            for device_id, info in device_metrics.items():
                labels = info.get("labels", {})
                devices.append(DeviceInfo(
                    device_id=device_id,
                    vendor=AcceleratorVendor.NVIDIA,
                    model=labels.get("model", "Unknown NVIDIA GPU"),
                    uuid=labels.get("device_uuid"),
                    memory_total_bytes=info.get("memory_total"),
                ))

        except Exception as e:
            logger.error("nvidia_get_devices_error", error=str(e))

        return devices

    async def health_check(self) -> Tuple[bool, str]:
        """
        Check DCGM Exporter health.

        Returns:
            Tuple of (is_healthy, message)
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.exporter_url}{self.metrics_path}")

            if response.status_code == 200:
                # Check if we got any GPU metrics
                if "DCGM_FI_DEV_GPU_TEMP" in response.text:
                    return True, "DCGM Exporter is healthy and reporting GPU metrics"
                return True, "DCGM Exporter is responding but no GPU metrics found"

            return False, f"DCGM Exporter returned status {response.status_code}"

        except Exception as e:
            return False, f"DCGM Exporter health check failed: {str(e)}"


class NvidiaPrometheusAdapter(BaseAcceleratorAdapter):
    """
    NVIDIA adapter that reads from Prometheus.

    This adapter queries a Prometheus server for NVIDIA metrics that have
    already been scraped from DCGM Exporter or another source.

    Configuration:
        {
            "prometheus_url": "http://localhost:9090",
            "metric_prefix": "DCGM_"
        }
    """

    def __init__(
        self,
        config: Dict[str, Any],
        prometheus_client: PrometheusClient,
        mapping: Optional[Dict[str, MetricMapping]] = None,
        label_mapping: Optional[Dict[str, str]] = None,
        extra_labels: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize NVIDIA Prometheus adapter.

        Args:
            config: Adapter configuration
            prometheus_client: Prometheus client instance
            mapping: Custom metric mappings
            label_mapping: Custom label mappings
            extra_labels: Additional labels
        """
        # Convert dict mapping
        final_mapping = {}
        source_mapping = mapping or NVIDIA_DCGM_MAPPING

        for key, value in source_mapping.items():
            if isinstance(value, MetricMapping):
                final_mapping[key] = value
            elif isinstance(value, dict):
                final_mapping[key] = MetricMapping(
                    source_metric=value.get("source_metric", key),
                    target_metric=value["target"],
                    unit_conversion=UnitConversion(value.get("unit", "none")),
                )

        super().__init__(
            vendor=AcceleratorVendor.NVIDIA,
            config=config,
            mapping=final_mapping,
            label_mapping=label_mapping or NVIDIA_DCGM_LABEL_MAPPING,
            extra_labels=extra_labels or {},
        )

        self.prometheus = prometheus_client
        self.metric_prefix = config.get("metric_prefix", "DCGM_")

    async def collect_metrics(self) -> List[NormalizedMetric]:
        """
        Collect and normalize NVIDIA metrics from Prometheus.

        Returns:
            List of normalized metrics
        """
        normalized_metrics = []

        try:
            for source_metric, mapping in self.mapping.items():
                # Query Prometheus
                result = await self.prometheus.query(source_metric)

                if result.status == "success" and result.data.get("result"):
                    for item in result.data["result"]:
                        labels = item.get("metric", {})
                        value = float(item["value"][1])

                        # Convert value
                        converted_value = self.convert_unit(value, mapping.unit_conversion)
                        if mapping.multiplier != 1.0:
                            converted_value *= mapping.multiplier

                        # Create normalized metric
                        normalized = self.create_metric(
                            name=mapping.target_metric,
                            value=converted_value,
                            labels=labels,
                        )
                        normalized_metrics.append(normalized)

            self._last_collection = datetime.utcnow()
            self._last_error = None

            logger.info(
                "nvidia_prometheus_metrics_collected",
                metric_count=len(normalized_metrics),
            )

        except Exception as e:
            self._last_error = str(e)
            logger.error("nvidia_prometheus_collection_error", error=str(e))

        return normalized_metrics

    async def get_devices(self) -> List[DeviceInfo]:
        """
        Get device information from Prometheus.

        Returns:
            List of device information
        """
        devices = []

        try:
            # Query for unique GPU instances
            result = await self.prometheus.query(f'{self.metric_prefix}FI_DEV_GPU_TEMP')

            if result.status == "success" and result.data.get("result"):
                seen_devices = set()

                for item in result.data["result"]:
                    labels = item.get("metric", {})
                    device_id = labels.get("gpu", "0")

                    if device_id not in seen_devices:
                        seen_devices.add(device_id)
                        devices.append(DeviceInfo(
                            device_id=device_id,
                            vendor=AcceleratorVendor.NVIDIA,
                            model=labels.get("modelName", "Unknown NVIDIA GPU"),
                            uuid=labels.get("UUID"),
                        ))

        except Exception as e:
            logger.error("nvidia_prometheus_get_devices_error", error=str(e))

        return devices

    async def health_check(self) -> Tuple[bool, str]:
        """
        Check adapter health via Prometheus.

        Returns:
            Tuple of (is_healthy, message)
        """
        is_healthy, message = await self.prometheus.health_check()
        if not is_healthy:
            return False, f"Prometheus unavailable: {message}"

        # Check for NVIDIA metrics
        result = await self.prometheus.query(f'{self.metric_prefix}FI_DEV_GPU_TEMP')

        if result.status == "success":
            if result.data.get("result"):
                return True, f"Found {len(result.data['result'])} NVIDIA GPUs"
            return True, "Prometheus healthy but no NVIDIA metrics found"

        return False, f"Failed to query NVIDIA metrics: {result.error}"

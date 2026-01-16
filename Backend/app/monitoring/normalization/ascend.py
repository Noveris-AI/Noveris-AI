"""
Huawei Ascend NPU Metrics Normalization Adapter.

This module provides adapter implementations for Huawei Ascend NPU metrics:
- NPU Exporter (for Kubernetes/CCE environments)
- Direct npu-smi based collection

Reference:
- NPU Exporter: https://support.huawei.com/enterprise/en/doc/EDOC1100207063/10cbc9d6/npu-exporter
- Grafana Dashboard: https://grafana.com/grafana/dashboards/20592-ascend-npu-exporter/
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
    ASCEND_NPU_LABEL_MAPPING,
    ASCEND_NPU_MAPPING,
    UnitConversion,
)

logger = structlog.get_logger(__name__)


class AscendNpuExporterAdapter(BaseAcceleratorAdapter):
    """
    Huawei Ascend NPU Exporter adapter.

    Collects NPU metrics from Ascend NPU Exporter's Prometheus endpoint.

    Configuration:
        {
            "exporter_url": "http://localhost:8082",
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
        Initialize Ascend NPU adapter.

        Args:
            config: Adapter configuration
            mapping: Custom metric mappings (defaults to ASCEND_NPU_MAPPING)
            label_mapping: Custom label mappings
            extra_labels: Additional labels
        """
        final_mapping = {}
        source_mapping = mapping or ASCEND_NPU_MAPPING

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
            vendor=AcceleratorVendor.HUAWEI_ASCEND,
            config=config,
            mapping=final_mapping,
            label_mapping=label_mapping or ASCEND_NPU_LABEL_MAPPING,
            extra_labels=extra_labels or {},
        )

        self.exporter_url = config.get("exporter_url", "http://localhost:8082")
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
        """Parse Prometheus text format."""
        metrics = []
        lines = text.strip().split("\n")

        for line in lines:
            if not line or line.startswith("#"):
                continue

            match = re.match(
                r'([a-zA-Z_:][a-zA-Z0-9_:]*)\{([^}]*)\}\s+([0-9.eE+-]+)',
                line
            )

            if match:
                metric_name = match.group(1)
                labels_str = match.group(2)
                value_str = match.group(3)

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

        return metrics

    async def collect_metrics(self) -> List[NormalizedMetric]:
        """
        Collect and normalize metrics from Ascend NPU Exporter.

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

                if metric_name in self.mapping:
                    mapping = self.mapping[metric_name]

                    converted_value = self.convert_unit(raw["value"], mapping.unit_conversion)
                    if mapping.multiplier != 1.0:
                        converted_value *= mapping.multiplier

                    normalized = self.create_metric(
                        name=mapping.target_metric,
                        value=converted_value,
                        labels=raw["labels"],
                    )
                    normalized_metrics.append(normalized)

            # Calculate memory utilization if we have used and total
            memory_data: Dict[str, Dict[str, float]] = {}
            for metric in normalized_metrics:
                device_id = metric.labels.get("device_id", "0")
                if device_id not in memory_data:
                    memory_data[device_id] = {}

                if metric.name == "accelerator_memory_used_bytes":
                    memory_data[device_id]["used"] = metric.value
                elif metric.name == "accelerator_memory_total_bytes":
                    memory_data[device_id]["total"] = metric.value

            for device_id, data in memory_data.items():
                if "used" in data and "total" in data and data["total"] > 0:
                    utilization = data["used"] / data["total"]
                    util_metric = self.create_metric(
                        name="accelerator_memory_utilization_ratio",
                        value=utilization,
                        labels={"device_id": device_id},
                    )
                    normalized_metrics.append(util_metric)

            logger.info(
                "ascend_npu_metrics_collected",
                metric_count=len(normalized_metrics),
            )

        except Exception as e:
            self._last_error = str(e)
            logger.error("ascend_npu_collection_error", error=str(e))

        return normalized_metrics

    async def get_devices(self) -> List[DeviceInfo]:
        """
        Get information about available Ascend NPUs.

        Returns:
            List of device information
        """
        devices = []

        try:
            metrics = await self.collect_metrics()

            device_data: Dict[str, Dict[str, Any]] = {}

            for metric in metrics:
                device_id = metric.labels.get("device_id", "0")
                if device_id not in device_data:
                    device_data[device_id] = {"labels": metric.labels}

                if metric.name == "accelerator_memory_total_bytes":
                    device_data[device_id]["memory_total"] = int(metric.value)

            for device_id, info in device_data.items():
                labels = info.get("labels", {})
                devices.append(DeviceInfo(
                    device_id=device_id,
                    vendor=AcceleratorVendor.HUAWEI_ASCEND,
                    model=labels.get("model", "Ascend NPU"),
                    uuid=labels.get("device_uuid"),
                    memory_total_bytes=info.get("memory_total"),
                ))

        except Exception as e:
            logger.error("ascend_get_devices_error", error=str(e))

        return devices

    async def health_check(self) -> Tuple[bool, str]:
        """
        Check NPU Exporter health.

        Returns:
            Tuple of (is_healthy, message)
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.exporter_url}{self.metrics_path}")

            if response.status_code == 200:
                if "npu_chip_info" in response.text:
                    return True, "Ascend NPU Exporter is healthy and reporting NPU metrics"
                return True, "Ascend NPU Exporter is responding but no NPU metrics found"

            return False, f"Ascend NPU Exporter returned status {response.status_code}"

        except Exception as e:
            return False, f"Ascend NPU Exporter health check failed: {str(e)}"


class AscendPrometheusAdapter(BaseAcceleratorAdapter):
    """
    Ascend adapter that reads from Prometheus.

    This adapter queries a Prometheus server for Ascend NPU metrics.

    Configuration:
        {
            "prometheus_url": "http://localhost:9090",
            "metric_prefix": "npu_"
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
        Initialize Ascend Prometheus adapter.

        Args:
            config: Adapter configuration
            prometheus_client: Prometheus client instance
            mapping: Custom metric mappings
            label_mapping: Custom label mappings
            extra_labels: Additional labels
        """
        final_mapping = {}
        source_mapping = mapping or ASCEND_NPU_MAPPING

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
            vendor=AcceleratorVendor.HUAWEI_ASCEND,
            config=config,
            mapping=final_mapping,
            label_mapping=label_mapping or ASCEND_NPU_LABEL_MAPPING,
            extra_labels=extra_labels or {},
        )

        self.prometheus = prometheus_client
        self.metric_prefix = config.get("metric_prefix", "npu_")

    async def collect_metrics(self) -> List[NormalizedMetric]:
        """
        Collect and normalize Ascend metrics from Prometheus.

        Returns:
            List of normalized metrics
        """
        normalized_metrics = []

        try:
            for source_metric, mapping in self.mapping.items():
                result = await self.prometheus.query(source_metric)

                if result.status == "success" and result.data.get("result"):
                    for item in result.data["result"]:
                        labels = item.get("metric", {})
                        value = float(item["value"][1])

                        converted_value = self.convert_unit(value, mapping.unit_conversion)
                        if mapping.multiplier != 1.0:
                            converted_value *= mapping.multiplier

                        normalized = self.create_metric(
                            name=mapping.target_metric,
                            value=converted_value,
                            labels=labels,
                        )
                        normalized_metrics.append(normalized)

            self._last_collection = datetime.utcnow()
            self._last_error = None

            logger.info(
                "ascend_prometheus_metrics_collected",
                metric_count=len(normalized_metrics),
            )

        except Exception as e:
            self._last_error = str(e)
            logger.error("ascend_prometheus_collection_error", error=str(e))

        return normalized_metrics

    async def get_devices(self) -> List[DeviceInfo]:
        """
        Get device information from Prometheus.

        Returns:
            List of device information
        """
        devices = []

        try:
            result = await self.prometheus.query(f'{self.metric_prefix}chip_info_temperature')

            if result.status == "success" and result.data.get("result"):
                seen_devices = set()

                for item in result.data["result"]:
                    labels = item.get("metric", {})
                    device_id = labels.get("id", "0")

                    if device_id not in seen_devices:
                        seen_devices.add(device_id)
                        devices.append(DeviceInfo(
                            device_id=device_id,
                            vendor=AcceleratorVendor.HUAWEI_ASCEND,
                            model=labels.get("name", "Ascend NPU"),
                            uuid=labels.get("vdie_id"),
                        ))

        except Exception as e:
            logger.error("ascend_prometheus_get_devices_error", error=str(e))

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

        result = await self.prometheus.query(f'{self.metric_prefix}chip_info_temperature')

        if result.status == "success":
            if result.data.get("result"):
                return True, f"Found {len(result.data['result'])} Ascend NPUs"
            return True, "Prometheus healthy but no Ascend metrics found"

        return False, f"Failed to query Ascend metrics: {result.error}"

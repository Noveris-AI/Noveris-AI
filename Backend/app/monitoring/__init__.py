"""
Monitoring Module for Noveris AI Platform.

This module provides comprehensive observability capabilities:
- Metrics collection from Prometheus
- Log aggregation via Loki
- Distributed tracing via Tempo (optional)
- Alerting via Alertmanager
- GPU/NPU metrics normalization (NVIDIA, Huawei Ascend, Aliyun NPU)

Key components:
- clients/: External service clients (Prometheus, Loki, Tempo, Alertmanager)
- normalization/: Metrics normalization adapters for different accelerator vendors
- aggregates/: Business logic for aggregating metrics into dashboard cards
- models.py: Database models for monitoring configuration
- schemas.py: Pydantic schemas for API request/response
- service.py: Main service layer
- routes.py: FastAPI route definitions
"""

# Noveris AI Observability Stack

This directory contains the Docker Compose configuration for the complete observability stack used by the Noveris AI platform.

## Components

| Component | Port | Description |
|-----------|------|-------------|
| Prometheus | 9090 | Metrics collection and alerting |
| Alertmanager | 9093 | Alert management and routing |
| Loki | 3100 | Log aggregation |
| Tempo | 3200 | Distributed tracing |
| Grafana | 3000 | Visualization and dashboards |
| Promtail | 9080 | Log shipper (optional) |

## Quick Start

```bash
# Create the network if it doesn't exist
docker network create noveris-network

# Start the stack
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## Access

- **Grafana**: http://localhost:3000 (default: admin/admin)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093

## Configuration

### Environment Variables

Create a `.env` file or set these environment variables:

```env
# Prometheus
PROMETHEUS_PORT=9090
PROMETHEUS_RETENTION=15d
PROMETHEUS_EXTERNAL_URL=http://localhost:9090

# Alertmanager
ALERTMANAGER_PORT=9093
ALERTMANAGER_EXTERNAL_URL=http://localhost:9093

# Loki
LOKI_PORT=3100

# Tempo
TEMPO_PORT=3200
TEMPO_OTLP_GRPC=4317
TEMPO_OTLP_HTTP=4318
TEMPO_ZIPKIN=9411

# Grafana
GRAFANA_PORT=3000
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
GRAFANA_ROOT_URL=http://localhost:3000
GRAFANA_ANONYMOUS_ENABLED=false
```

### Adding Scrape Targets

Edit the target files in `config/prometheus/targets/`:

- `nodes.yml` - Node Exporter targets
- `dcgm.yml` - NVIDIA DCGM Exporter targets
- `ascend.yml` - Huawei Ascend NPU Exporter targets
- `vllm.yml` - vLLM model service targets
- `sglang.yml` - SGLang model service targets
- `nginx.yml` - NGINX gateway targets

Example:
```yaml
- targets:
    - "gpu-node-01:9400"
    - "gpu-node-02:9400"
  labels:
    vendor: "nvidia"
    env: "production"
```

Prometheus reloads these files automatically every 30 seconds.

### Alerting

Alert rules are defined in `config/prometheus/rules/alerts.yml`. Available alert categories:

- **GPU Alerts**: Temperature, memory, power, availability
- **NPU Alerts**: Temperature, health status
- **Node Alerts**: CPU, memory, disk, availability
- **Model Service Alerts**: Latency, error rate, queue depth

Configure notification channels in `config/alertmanager/alertmanager.yml`.

## Enabling Promtail (Log Collection)

Promtail is disabled by default. To enable:

```bash
docker-compose --profile logging up -d promtail
```

## Grafana Dashboards

Pre-configured dashboards are available in `config/grafana/dashboards/`:

- `gpu-nvidia-dcgm.json` - NVIDIA GPU monitoring

Additional dashboards can be added to this directory and will be auto-loaded.

## Integration with Noveris Platform

The observability stack integrates with the Noveris backend through:

1. **Prometheus API**: Metrics queries via `/monitoring/prometheus/*`
2. **Loki API**: Log queries via `/monitoring/logs/*`
3. **Alertmanager Webhooks**: Alerts forwarded to `/api/v1/monitoring/alerts/webhook`

## Troubleshooting

### Check component health

```bash
# Prometheus
curl http://localhost:9090/-/healthy

# Alertmanager
curl http://localhost:9093/-/healthy

# Loki
curl http://localhost:3100/ready

# Tempo
curl http://localhost:3200/ready

# Grafana
curl http://localhost:3000/api/health
```

### View component logs

```bash
docker-compose logs prometheus
docker-compose logs alertmanager
docker-compose logs loki
docker-compose logs tempo
docker-compose logs grafana
```

### Reload Prometheus configuration

```bash
curl -X POST http://localhost:9090/-/reload
```

## Data Retention

Default retention periods:
- Prometheus: 15 days
- Loki: 7 days
- Tempo: 7 days

Adjust in respective configuration files or via environment variables.

## Security Considerations

For production deployments:

1. Change default Grafana credentials
2. Enable TLS for all endpoints
3. Configure proper authentication for Prometheus/Alertmanager
4. Use secrets management for sensitive configuration
5. Restrict network access to observability ports

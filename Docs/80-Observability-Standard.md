# 可观测性规范

## 目的
建立全面的可观测性体系，确保系统运行状态透明可见，涵盖日志、指标、链路追踪等关键领域，支持快速故障定位和性能优化。

## 适用范围
- **强制**: Backend (Python+FastAPI), Frontend (React) - 所有可观测性相关实现
- **验证**: 可观测性配置自动检查，运行时监控数据收集

## 核心原则

### MUST - 强制规则
1. **结构化日志**: 所有日志必须结构化，便于搜索和分析
2. **关键指标**: 收集核心业务指标和系统指标
3. **链路追踪**: 所有请求必须有完整的链路追踪
4. **告警规则**: 建立基于指标的告警规则和响应流程
5. **错误追踪**: 实施错误收集和分析机制

### SHOULD - 建议规则
1. 实施分布式追踪
2. 建立监控仪表板
3. 实施日志聚合分析
4. 建立事故复盘机制

## 结构化日志规范

### 日志级别与格式
```python
import logging
import json
from datetime import datetime
from typing import Dict, Any

class StructuredLogger:
    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # 创建结构化格式化器
        formatter = StructuredFormatter()
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def log(self, level: int, message: str, **kwargs):
        """记录结构化日志"""
        extra = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": logging.getLevelName(level),
            "message": message,
            **kwargs
        }
        self.logger.log(level, message, extra=extra)

    def info(self, message: str, **kwargs):
        self.log(logging.INFO, message, **kwargs)

    def error(self, message: str, **kwargs):
        self.log(logging.ERROR, message, **kwargs)

    def warning(self, message: str, **kwargs):
        self.log(logging.WARNING, message, **kwargs)

    def debug(self, message: str, **kwargs):
        self.log(logging.DEBUG, message, **kwargs)

class StructuredFormatter(logging.Formatter):
    def format(self, record):
        # 提取结构化数据
        log_data = {
            "timestamp": getattr(record, "timestamp", datetime.utcnow().isoformat()),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 添加额外字段
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "levelname", "levelno", "pathname",
                          "filename", "module", "exc_info", "exc_text", "stack_info",
                          "lineno", "funcName", "created", "msecs", "relativeCreated",
                          "thread", "threadName", "processName", "process", "message"]:
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False)

# 使用示例
logger = StructuredLogger(__name__)

# 记录用户登录事件
logger.info(
    "User login successful",
    user_id=123,
    email="user@example.com",
    ip_address="192.168.1.1",
    user_agent="Mozilla/5.0...",
    login_method="password"
)

# 记录API请求
logger.info(
    "API request completed",
    method="GET",
    path="/api/v1/users",
    status_code=200,
    response_time=0.145,
    user_id=123,
    request_id="req_abc123"
)

# 记录错误
logger.error(
    "Database connection failed",
    error="Connection timeout",
    database_host="db.example.com",
    connection_attempts=3,
    stack_trace="..."
)
```

### 日志上下文管理
```python
import contextvars
from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware

# 上下文变量
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('request_id', default=None)
user_id_var: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar('user_id', default=None)
session_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('session_id', default=None)

class LoggingContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 生成请求ID
        request_id = generate_request_id()

        # 设置上下文
        request_id_var.set(request_id)

        # 尝试从会话中获取用户信息
        session_id = request.cookies.get("session_id")
        if session_id:
            session_id_var.set(session_id)
            # 从session获取user_id（这里需要实现）
            # user_id_var.set(get_user_id_from_session(session_id))

        # 添加请求ID到响应头
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        return response

def get_structured_logger(name: str) -> StructuredLogger:
    """获取带有上下文的结构化日志器"""
    logger = StructuredLogger(name)

    # 保存原始log方法
    original_log = logger.log

    def contextual_log(level: int, message: str, **kwargs):
        # 添加上下文信息
        context_data = {}

        request_id = request_id_var.get()
        if request_id:
            context_data["request_id"] = request_id

        user_id = user_id_var.get()
        if user_id:
            context_data["user_id"] = user_id

        session_id = session_id_var.get()
        if session_id:
            context_data["session_id"] = session_id

        # 合并上下文和额外数据
        all_kwargs = {**context_data, **kwargs}

        original_log(level, message, **all_kwargs)

    logger.log = contextual_log
    return logger

# 使用示例
logger = get_structured_logger(__name__)

@app.get("/api/v1/users/{user_id}")
async def get_user(user_id: int):
    logger.info(
        "Fetching user data",
        user_id=user_id,
        operation="get_user"
    )

    try:
        user = await get_user_from_db(user_id)
        logger.info(
            "User data retrieved successfully",
            user_id=user_id,
            operation="get_user"
        )
        return user
    except Exception as e:
        logger.error(
            "Failed to retrieve user data",
            user_id=user_id,
            operation="get_user",
            error=str(e)
        )
        raise
```

## 指标收集规范

### Prometheus指标定义
```python
from prometheus_client import Counter, Histogram, Gauge, Summary
import time

class MetricsCollector:
    def __init__(self):
        # HTTP请求指标
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total number of HTTP requests',
            ['method', 'endpoint', 'status_code']
        )

        self.http_request_duration_seconds = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )

        # 业务指标
        self.user_registrations_total = Counter(
            'user_registrations_total',
            'Total number of user registrations'
        )

        self.active_sessions = Gauge(
            'active_sessions',
            'Number of active user sessions'
        )

        # 数据库指标
        self.db_connections_active = Gauge(
            'db_connections_active',
            'Number of active database connections'
        )

        self.db_query_duration_seconds = Histogram(
            'db_query_duration_seconds',
            'Database query duration in seconds',
            ['query_type'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0]
        )

        # 缓存指标
        self.cache_hits_total = Counter(
            'cache_hits_total',
            'Total number of cache hits'
        )

        self.cache_misses_total = Counter(
            'cache_misses_total',
            'Total number of cache misses'
        )

        # 业务特定指标
        self.posts_created_total = Counter(
            'posts_created_total',
            'Total number of posts created',
            ['category']
        )

        self.file_uploads_total = Counter(
            'file_uploads_total',
            'Total number of file uploads',
            ['file_type']
        )

# 全局指标收集器
metrics = MetricsCollector()

# FastAPI指标中间件
class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        try:
            response = await call_next(request)

            # 记录请求指标
            metrics.http_requests_total.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code
            ).inc()

            # 记录响应时间
            duration = time.time() - start_time
            metrics.http_request_duration_seconds.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)

            return response

        except Exception as e:
            # 记录错误请求
            metrics.http_requests_total.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=500
            ).inc()

            raise

# 业务逻辑中的指标收集
async def create_user(user_data: dict):
    start_time = time.time()

    try:
        user = await create_user_in_db(user_data)

        # 记录用户注册指标
        metrics.user_registrations_total.inc()

        # 记录数据库操作耗时
        duration = time.time() - start_time
        metrics.db_query_duration_seconds.labels(
            query_type="insert"
        ).observe(duration)

        logger.info(
            "User created successfully",
            user_id=user.id,
            duration=duration
        )

        return user

    except Exception as e:
        # 记录失败的数据库操作
        duration = time.time() - start_time
        metrics.db_query_duration_seconds.labels(
            query_type="insert_failed"
        ).observe(duration)

        logger.error(
            "Failed to create user",
            error=str(e),
            duration=duration
        )
        raise

# 缓存指标收集
async def get_cached_data(key: str):
    # 尝试从缓存获取
    cached_data = await cache.get(key)

    if cached_data:
        metrics.cache_hits_total.inc()
        return cached_data
    else:
        metrics.cache_misses_total.inc()

        # 从数据库获取
        data = await get_data_from_db(key)

        # 写入缓存
        await cache.set(key, data)

        return data
```

### 自定义业务指标
```python
from enum import Enum

class BusinessMetrics:
    class EventType(Enum):
        USER_SIGNUP = "user_signup"
        POST_CREATED = "post_created"
        COMMENT_ADDED = "comment_added"
        FILE_UPLOADED = "file_uploaded"

    @staticmethod
    def record_event(event_type: EventType, **kwargs):
        """记录业务事件"""
        if event_type == BusinessMetrics.EventType.USER_SIGNUP:
            metrics.user_registrations_total.inc()

        elif event_type == BusinessMetrics.EventType.POST_CREATED:
            category = kwargs.get('category', 'general')
            metrics.posts_created_total.labels(category=category).inc()

        elif event_type == BusinessMetrics.EventType.FILE_UPLOADED:
            file_type = kwargs.get('file_type', 'unknown')
            metrics.file_uploads_total.labels(file_type=file_type).inc()

        # 记录到日志
        logger.info(
            f"Business event: {event_type.value}",
            event_type=event_type.value,
            **kwargs
        )

# 使用示例
@app.post("/api/v1/users")
async def register_user(user_data: UserCreateRequest):
    user = await create_user(user_data)

    # 记录业务指标
    BusinessMetrics.record_event(
        BusinessMetrics.EventType.USER_SIGNUP,
        user_id=user.id,
        registration_method="api"
    )

    return user

@app.post("/api/v1/posts")
async def create_post(post_data: PostCreateRequest, current_user: User = Depends(get_current_user)):
    post = await create_post_in_db(post_data, current_user.id)

    # 记录业务指标
    BusinessMetrics.record_event(
        BusinessMetrics.EventType.POST_CREATED,
        post_id=post.id,
        user_id=current_user.id,
        category=post_data.category or 'general'
    )

    return post
```

## 链路追踪规范

### OpenTelemetry集成
```python
from opentelemetry import trace
from opentelemetry.exporter.jaeger import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

def setup_tracing(service_name: str, jaeger_host: str = "localhost", jaeger_port: int = 14268):
    """设置OpenTelemetry链路追踪"""

    # 创建TracerProvider
    trace.set_tracer_provider(TracerProvider())

    # 配置Jaeger导出器
    jaeger_exporter = JaegerExporter(
        agent_host_name=jaeger_host,
        agent_port=jaeger_port,
    )

    # 添加批量span处理器
    span_processor = BatchSpanProcessor(jaeger_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)

    # 自动检测FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # 自动检测SQLAlchemy
    SQLAlchemyInstrumentor().instrument()

    # 自动检测Redis
    RedisInstrumentor().instrument()

    return trace.get_tracer(service_name)

# 初始化追踪
tracer = setup_tracing("noveris-backend")

# 手动创建span
@app.get("/api/v1/users/{user_id}")
async def get_user(user_id: int):
    with tracer.start_as_current_span("get_user") as span:
        # 添加span属性
        span.set_attribute("user.id", user_id)
        span.set_attribute("operation", "fetch_user")

        # 添加事件
        span.add_event("Starting database query")

        try:
            user = await get_user_from_db(user_id)

            span.add_event("Database query completed")
            span.set_attribute("db.rows_returned", 1 if user else 0)

            return user

        except Exception as e:
            # 记录异常
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise

# 跨服务调用追踪
async def call_external_service(url: str, data: dict):
    with tracer.start_as_current_span("external_api_call") as span:
        span.set_attribute("http.url", url)
        span.set_attribute("http.method", "POST")

        # 注入追踪头
        headers = {}
        trace.get_current_span().get_span_context().inject_headers(headers)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, headers=headers)

            span.set_attribute("http.status_code", response.status_code)
            span.add_event("External API call completed")

            return response.json()

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise
```

## 告警与监控

### Prometheus告警规则
```yaml
# prometheus/alerts.yml
groups:
  - name: novaris.rules
    rules:
      # API响应时间告警
      - alert: HighApiLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API latency detected"
          description: "95th percentile API response time > 1s for 5 minutes"

      # API错误率告警
      - alert: HighApiErrorRate
        expr: rate(http_requests_total{status_code=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High API error rate detected"
          description: "API error rate > 5% for 5 minutes"

      # 数据库连接池告警
      - alert: HighDbConnectionUsage
        expr: db_connections_active / db_connections_max > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High database connection pool usage"
          description: "Database connection pool usage > 90%"

      # 缓存命中率告警
      - alert: LowCacheHitRate
        expr: rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m])) < 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low cache hit rate"
          description: "Cache hit rate < 80% for 10 minutes"
```

### Grafana仪表板配置
```json
{
  "dashboard": {
    "title": "Noveris AI Observability",
    "tags": ["noveris", "observability"],
    "timezone": "UTC",
    "panels": [
      {
        "title": "API Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "P95"
          },
          {
            "expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "P50"
          }
        ]
      },
      {
        "title": "API Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total{status_code=~\"5..\"}[5m]) / rate(http_requests_total[5m]) * 100",
            "legendFormat": "Error Rate %"
          }
        ]
      },
      {
        "title": "Database Connections",
        "type": "graph",
        "targets": [
          {
            "expr": "db_connections_active",
            "legendFormat": "Active"
          }
        ]
      },
      {
        "title": "Cache Performance",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m])) * 100",
            "legendFormat": "Hit Rate %"
          }
        ]
      }
    ]
  }
}
```

## 错误追踪与分析

### Sentry错误收集
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastAPIIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

def setup_sentry(dsn: str, environment: str):
    """设置Sentry错误追踪"""
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        integrations=[
            FastAPIIntegration(),
            SqlalchemyIntegration(),
        ],
        # 性能监控
        traces_sample_rate=0.1,  # 10%的请求进行性能追踪
        # 错误监控
        send_default_pii=False,  # 不发送个人身份信息
        # 自定义配置
        before_send=before_send_filter,
    )

def before_send_filter(event, hint):
    """错误事件过滤器"""
    # 过滤掉一些不重要的错误
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        if isinstance(exc_value, KeyboardInterrupt):
            return None  # 忽略键盘中断

    # 添加自定义上下文
    if 'request' in event:
        # 添加用户信息（脱敏）
        user_id = get_current_user_id()
        if user_id:
            event['user'] = {'id': str(user_id)}

    return event

# 初始化Sentry
setup_sentry(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("APP_ENV", "development")
)

# 自定义错误追踪
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # 记录到Sentry
    sentry_sdk.capture_exception(exc)

    # 记录到结构化日志
    logger.error(
        "Unhandled exception",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        url=str(request.url),
        method=request.method,
        user_agent=request.headers.get("user-agent"),
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error"
            }
        }
    )
```

## 检查清单

### 日志规范检查
- [ ] 所有日志使用结构化格式
- [ ] 包含请求ID和用户上下文
- [ ] 敏感信息已脱敏
- [ ] 日志级别使用正确

### 指标收集检查
- [ ] 定义了核心业务指标
- [ ] 配置了系统性能指标
- [ ] 实施了指标收集中间件
- [ ] 建立了告警规则

### 链路追踪检查
- [ ] 配置了分布式追踪
- [ ] 所有请求都有追踪ID
- [ ] 跨服务调用正确传递追踪头
- [ ] 异常情况正确记录

### 监控告警检查
- [ ] 建立了Grafana仪表板
- [ ] 配置了Prometheus告警
- [ ] 实施了错误追踪系统
- [ ] 建立了事故响应流程

## 示例配置

### ELK Stack配置
```yaml
# docker-compose.monitoring.yml
version: '3.8'
services:
  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"

  logstash:
    image: logstash:8.11.0
    volumes:
      - ./monitoring/logstash.conf:/usr/share/logstash/pipeline/logstash.conf
    ports:
      - "5044:5044"
    depends_on:
      - elasticsearch

  kibana:
    image: kibana:8.11.0
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch

volumes:
  es_data:
```

## 相关文档
- [配置规范](10-Config-Standard.md) - 可观测性配置管理
- [安全规范](60-Security-Standard.md) - 安全监控要求
- [性能规范](70-Performance-Standard.md) - 性能监控指标
- [部署规范](50-Deployment-Standard.md) - 监控基础设施部署

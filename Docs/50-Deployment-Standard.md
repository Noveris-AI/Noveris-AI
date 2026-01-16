# 部署规范

## 目的
建立标准化的部署流程，确保应用能够安全、可靠、高效地部署到各个环境，实现自动化、可回滚、可观测的部署策略。

## 适用范围
- **强制**: Frontend (React) - 所有部署活动
- **验证**: CI/CD流水线自动执行，部署后进行验证

## 核心原则

### MUST - 强制规则
1. **环境变量驱动**: 所有配置通过环境变量注入，禁止硬编码
2. **Docker标准化**: 所有服务必须容器化，使用官方镜像
3. **版本管理**: 镜像打tag策略遵循语义化版本 + Git SHA
4. **回滚策略**: 必须支持一键回滚到上一版本
5. **健康检查**: 所有服务必须实现健康检查端点
6. **环境隔离**: 开发、测试、生产环境严格隔离

### SHOULD - 建议规则
1. 实施蓝绿部署或金丝雀发布
2. 使用基础设施即代码 (IaC)
3. 实施自动化测试门禁
4. 建立部署后监控告警

## Docker镜像构建规范

### Dockerfile最佳实践
```dockerfile
# Backend Dockerfile
FROM python:3.11-slim

# 元数据
LABEL maintainer="Noveris AI Team <team@noveris.ai>"
LABEL version="1.0.0"
LABEL description="Noveris AI Backend API"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建非root用户
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# Frontend Dockerfile
FROM node:18-alpine

# 元数据
LABEL maintainer="Noveris AI Team <team@noveris.ai>"
LABEL version="1.0.0"
LABEL description="Noveris AI Frontend"

WORKDIR /app

# 复制package文件
COPY package*.json ./

# 安装依赖
RUN npm ci --only=production

# 复制源代码
COPY . .

# 构建应用
RUN npm run build

# 生产环境使用nginx
FROM nginx:alpine

# 复制nginx配置
COPY nginx.conf /etc/nginx/nginx.conf

# 复制构建产物
COPY --from=0 /app/dist /usr/share/nginx/html

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/health || exit 1
```

### 镜像tag策略
```bash
# 版本tag格式
# 格式: {版本号}-{git-sha}-{构建时间}
# 示例: v1.0.0-abc1234-20240101

# 构建脚本
#!/bin/bash
set -e

# 获取版本信息
VERSION=${APP_VERSION:-"v1.0.0"}
GIT_SHA=$(git rev-parse --short HEAD)
BUILD_TIME=$(date +%Y%m%d_%H%M%S)

# 构建tag
IMAGE_TAG="${VERSION}-${GIT_SHA}-${BUILD_TIME}"

# 构建镜像
docker build -t novaris-ai/backend:${IMAGE_TAG} ./backend
docker build -t novaris-ai/frontend:${IMAGE_TAG} ./frontend

# 推送镜像
docker push novaris-ai/backend:${IMAGE_TAG}
docker push novaris-ai/frontend:${IMAGE_TAG}

# 为最新版本添加latest标签
if [ "$GIT_BRANCH" = "main" ]; then
    docker tag novaris-ai/backend:${IMAGE_TAG} novaris-ai/backend:latest
    docker tag novaris-ai/frontend:${IMAGE_TAG} novaris-ai/frontend:latest
    docker push novaris-ai/backend:latest
    docker push novaris-ai/frontend:latest
fi

echo "Built and pushed images with tag: ${IMAGE_TAG}"
```

## Docker Compose编排

### docker-compose.yml配置
```yaml
version: '3.8'

services:
  # PostgreSQL数据库
  postgres:
    image: postgres:15-alpine
    container_name: novaris-postgres
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/db/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "${DB_PORT:-5432}:5432"
    networks:
      - novaris-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis缓存
  redis:
    image: redis:7-alpine
    container_name: novaris-redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "${REDIS_PORT:-6379}:6379"
    networks:
      - novaris-network
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # MinIO对象存储
  minio:
    image: minio/minio:latest
    container_name: novaris-minio
    environment:
      MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY}
      MINIO_SECRET_KEY: ${MINIO_SECRET_KEY}
    volumes:
      - minio_data:/data
    ports:
      - "${MINIO_PORT:-9000}:9000"
    networks:
      - novaris-network
    command: server /data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  # Elasticsearch
  elasticsearch:
    image: elasticsearch:8.11.0
    container_name: novaris-elasticsearch
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - ELASTIC_PASSWORD=${ES_PASSWORD}
    volumes:
      - es_data:/usr/share/elasticsearch/data
    ports:
      - "${ES_PORT:-9200}:9200"
    networks:
      - novaris-network
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  # Backend API
  backend:
    image: novaris-ai/backend:${IMAGE_TAG:-latest}
    container_name: novaris-backend
    environment:
      - APP_ENV=${APP_ENV:-development}
      - APP_PORT=8000
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - MINIO_ENDPOINT=http://minio:9000
      - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
      - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
      - ES_HOST=elasticsearch
      - ES_PORT=9200
      - ES_PASSWORD=${ES_PASSWORD}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy
      elasticsearch:
        condition: service_healthy
    networks:
      - novaris-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      start_period: 40s
      retries: 3
    restart: unless-stopped

  # Frontend
  frontend:
    image: novaris-ai/frontend:${IMAGE_TAG:-latest}
    container_name: novaris-frontend
    environment:
      - VITE_API_BASE_URL=http://localhost:8000
      - VITE_APP_ENV=${APP_ENV:-development}
    ports:
      - "3000:80"
    depends_on:
      - backend
    networks:
      - novaris-network
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  minio_data:
  es_data:

networks:
  novaris-network:
    driver: bridge
```

### compose.override.yml本地覆盖
```yaml
version: '3.8'

services:
  # 本地开发覆盖配置
  backend:
    volumes:
      - ./backend:/app
      - /app/__pycache__
    environment:
      - APP_ENV=development
      - APP_DEBUG=true
    command: uvicorn main:app --reload --host 0.0.0.0 --port 8000

  frontend:
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: npm run dev
    ports:
      - "3000:3000"

  # 本地开发数据库（持久化数据）
  postgres:
    ports:
      - "5432:5432"

  redis:
    ports:
      - "6379:6379"

  minio:
    ports:
      - "9000:9000"
      - "9001:9001"  # Console port
    command: server /data --console-address ":9001"
```

## Kubernetes部署规范

### 部署清单结构
```
Deploy/k8s/
├── base/                    # 基础配置
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   └── service-account.yaml
├── backend/                 # Backend服务
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── hpa.yaml
├── frontend/                # Frontend服务
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── configmap.yaml
├── postgres/                # PostgreSQL
│   ├── statefulset.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── pvc.yaml
├── redis/                   # Redis
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── pvc.yaml
├── minio/                   # MinIO
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── pvc.yaml
├── elasticsearch/           # Elasticsearch
│   ├── statefulset.yaml
│   ├── service.yaml
│   └── configmap.yaml
└── policies/                # 策略配置
    ├── network-policy.yaml
    └── pod-security-policy.yaml
```

### Backend Deployment配置
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: novaris-backend
  namespace: novaris-ai
  labels:
    app: novaris-backend
    version: v1.0.0
spec:
  replicas: 3
  selector:
    matchLabels:
      app: novaris-backend
  template:
    metadata:
      labels:
        app: novaris-backend
        version: v1.0.0
    spec:
      containers:
      - name: backend
        image: novaris-ai/backend:v1.0.0-abc1234-20240101
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: APP_ENV
          valueFrom:
            configMapKeyRef:
              name: novaris-config
              key: APP_ENV
        - name: DB_HOST
          valueFrom:
            configMapKeyRef:
              name: novaris-config
              key: DB_HOST
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: novaris-secrets
              key: DB_PASSWORD
        # ... 其他环境变量
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: http
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: http
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: tmp-volume
          mountPath: /tmp
      volumes:
      - name: tmp-volume
        emptyDir: {}
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      serviceAccountName: novaris-service-account
```

### Service配置
```yaml
apiVersion: v1
kind: Service
metadata:
  name: novaris-backend
  namespace: novaris-ai
  labels:
    app: novaris-backend
spec:
  type: ClusterIP
  ports:
  - port: 8000
    targetPort: http
    protocol: TCP
    name: http
  selector:
    app: novaris-backend
```

### Ingress配置
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: novaris-backend
  namespace: novaris-ai
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.noveris.ai
    secretName: novaris-tls
  rules:
  - host: api.noveris.ai
    http:
      paths:
      - path: /api/v1/
        pathType: Prefix
        backend:
          service:
            name: novaris-backend
            port:
              number: 8000
```

### HPA配置
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: novaris-backend-hpa
  namespace: novaris-ai
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: novaris-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
```

### ConfigMap和Secret管理
```yaml
# ConfigMap - 非敏感配置
apiVersion: v1
kind: ConfigMap
metadata:
  name: novaris-config
  namespace: novaris-ai
data:
  APP_ENV: "production"
  APP_PORT: "8000"
  DB_HOST: "novaris-postgres"
  DB_PORT: "5432"
  DB_NAME: "noveris_db"
  REDIS_HOST: "novaris-redis"
  REDIS_PORT: "6379"
  MINIO_ENDPOINT: "http://novaris-minio:9000"
  ES_HOST: "novaris-elasticsearch"
  ES_PORT: "9200"

---
# Secret - 敏感配置
apiVersion: v1
kind: Secret
metadata:
  name: novaris-secrets
  namespace: novaris-ai
type: Opaque
data:
  # base64编码的值
  DB_PASSWORD: <base64-encoded-password>
  REDIS_PASSWORD: <base64-encoded-password>
  MINIO_ACCESS_KEY: <base64-encoded-key>
  MINIO_SECRET_KEY: <base64-encoded-key>
  ES_PASSWORD: <base64-encoded-password>
  JWT_SECRET: <base64-encoded-secret>
```

## Helm Chart规范

### Chart目录结构
```
Deploy/k8s/helm/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── backend-deployment.yaml
│   ├── backend-service.yaml
│   ├── backend-ingress.yaml
│   ├── frontend-deployment.yaml
│   ├── frontend-service.yaml
│   ├── frontend-ingress.yaml
│   ├── postgres-statefulset.yaml
│   ├── postgres-service.yaml
│   ├── redis-deployment.yaml
│   ├── redis-service.yaml
│   ├── minio-deployment.yaml
│   ├── minio-service.yaml
│   ├── elasticsearch-statefulset.yaml
│   ├── elasticsearch-service.yaml
│   └── tests/
│       └── test-connection.yaml
└── charts/  # 子chart目录
```

### values.yaml配置
```yaml
# Global配置
global:
  appName: novaris-ai
  imageRegistry: novaris-ai
  imageTag: v1.0.0-abc1234-20240101
  env: production

# Backend配置
backend:
  replicaCount: 3
  image:
    repository: backend
    tag: ""
  service:
    type: ClusterIP
    port: 8000
  resources:
    requests:
      memory: "256Mi"
      cpu: "100m"
    limits:
      memory: "512Mi"
      cpu: "500m"
  env:
    APP_ENV: production
    APP_PORT: 8000

# Database配置
postgresql:
  enabled: true
  image:
    tag: "15"
  auth:
    postgresPassword: ""
    username: novaris_user
    password: ""
    database: novaris_db
  persistence:
    enabled: true
    size: 10Gi

# Redis配置
redis:
  enabled: true
  image:
    tag: "7"
  auth:
    password: ""
  persistence:
    enabled: true
    size: 5Gi

# MinIO配置
minio:
  enabled: true
  image:
    tag: "latest"
  auth:
    rootUser: ""
    rootPassword: ""
  persistence:
    enabled: true
    size: 20Gi

# Elasticsearch配置
elasticsearch:
  enabled: true
  image:
    tag: "8.11.0"
  auth:
    password: ""
  persistence:
    enabled: true
    size: 30Gi
```

## 环境隔离与发布流程

### 环境配置差异
```yaml
# 开发环境values-dev.yaml
global:
  env: development
  imageTag: latest

backend:
  replicaCount: 1
  resources:
    requests:
      memory: "128Mi"
      cpu: "50m"
    limits:
      memory: "256Mi"
      cpu: "200m"

# 测试环境values-staging.yaml
global:
  env: staging
  imageTag: v1.0.0-rc.1-abc1234-20240101

backend:
  replicaCount: 2

# 生产环境values-prod.yaml
global:
  env: production
  imageTag: v1.0.0-abc1234-20240101

backend:
  replicaCount: 5
  resources:
    requests:
      memory: "512Mi"
      cpu: "200m"
    limits:
      memory: "1Gi"
      cpu: "1000m"
```

### CI/CD发布流程
```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    tags:
      - 'v*'

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Log in to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=tag
          type=sha

    - name: Build and push Backend
      uses: docker/build-push-action@v5
      with:
        context: ./backend
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}

    - name: Build and push Frontend
      uses: docker/build-push-action@v5
      with:
        context: ./frontend
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}

  deploy-staging:
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: staging
    if: startsWith(github.ref, 'refs/tags/v') && contains(github.ref, '-rc.')

    steps:
    - name: Deploy to Staging
      run: |
        helm upgrade --install novaris-staging ./Deploy/k8s/helm \
          --namespace staging \
          --values Deploy/k8s/helm/values-staging.yaml \
          --set global.imageTag=${GITHUB_SHA::7}

  deploy-production:
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: production
    if: startsWith(github.ref, 'refs/tags/v') && !contains(github.ref, '-rc.')

    steps:
    - name: Deploy to Production
      run: |
        helm upgrade --install novaris-prod ./Deploy/k8s/helm \
          --namespace production \
          --values Deploy/k8s/helm/values-prod.yaml \
          --set global.imageTag=${GITHUB_SHA::7} \
          --wait \
          --timeout 10m
```

## 检查清单

### Docker构建检查
- [ ] 使用多阶段构建优化镜像大小
- [ ] 设置适当的健康检查
- [ ] 使用非root用户运行
- [ ] 正确设置镜像标签和元数据

### 容器编排检查
- [ ] 所有服务定义健康检查
- [ ] 配置正确的依赖关系
- [ ] 设置资源限制
- [ ] 配置持久化存储

### K8s部署检查
- [ ] 使用ConfigMap管理非敏感配置
- [ ] 使用Secret管理敏感信息
- [ ] 配置适当的资源限制
- [ ] 设置就绪探针和存活探针

### 发布流程检查
- [ ] 实施环境隔离策略
- [ ] 配置自动回滚机制
- [ ] 建立部署后验证
- [ ] 设置监控和告警

## 示例部署命令

### 本地开发
```bash
# 启动本地开发环境
docker-compose -f docker-compose.yml -f compose.override.yml up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend

# 停止服务
docker-compose down
```

### Kubernetes部署
```bash
# 创建命名空间
kubectl create namespace novaris-ai

# 部署到开发环境
helm upgrade --install novaris-dev ./Deploy/k8s/helm \
  --namespace novaris-ai \
  --values Deploy/k8s/helm/values-dev.yaml \
  --create-namespace

# 查看部署状态
kubectl get pods -n novaris-ai

# 查看服务日志
kubectl logs -f deployment/novaris-backend -n novaris-ai

# 回滚部署
helm rollback novaris-dev 1 -n novaris-ai
```

## 相关文档
- [配置规范](10-Config-Standard.md) - 环境变量配置
- [测试规范](40-Testing-Standard.md) - CI/CD测试集成
- [安全规范](60-Security-Standard.md) - 部署安全要求
- [可观测性规范](80-Observability-Standard.md) - 部署监控要求

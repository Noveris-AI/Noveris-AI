# Noveris AI

企业级AI应用平台，采用前后端分离架构，提供完整的AI服务解决方案。

## 📋 项目概述

- **版本**: v1.0.0 (开发阶段)
- **前端**: React + TypeScript
- **前端**: React + TypeScript
- **数据库**: PostgreSQL
- **缓存**: Redis
- **对象存储**: MinIO
- **搜索引擎**: Elasticsearch
- **认证方式**: Session + Cookie
- **前端配色**: Teal & Stone (静谧海洋)

## 🚀 快速开始

### 环境要求

- Docker & Docker Compose
- Node.js 18+ (前端开发)
- Git

### 初始化项目

```bash
# 1. 克隆项目
git clone <repository-url>
cd novaris-ai

# 2. 运行初始化脚本 (Linux/macOS)
./Scripts/bootstrap/init.sh

# 或者 Windows PowerShell
.\Scripts\bootstrap\init.ps1

# 3. 配置环境变量
cp env-example-template.txt .env
# 编辑 .env 文件，设置数据库密码等敏感信息

# 4. 启动开发环境
cd Deploy/Build/Deploy
./create-network.sh
./deploy.sh deploy dev

# 5. 运行数据库迁移
./Scripts/db/migrate.sh up

# 6. 运行种子数据 (可选)
./Scripts/db/seed.sh run
```

### 本地开发

```bash
# 启动所有服务
make up

# 或者分别启动
# 后端 (在 Backend/ 目录)
cd Backend
pip install -r requirements.txt
uvicorn main:app --reload

# 前端 (在 Frontend/ 目录)
cd Frontend
npm install

# 配置前端环境变量 (可选)
# 创建 .env.local 文件并添加以下配置:
echo "# 认证配置
VITE_AUTH_API_MODE=mock
VITE_SSO_ENABLED=false
VITE_AUTH_REDIRECT_AFTER_LOGIN=/" > .env.local

npm run dev

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
```

## 📁 项目结构

```
Noveris-AI/
├── Backend/                 # Python FastAPI 后端
├── Frontend/               # React 前端应用
├── Deploy/                 # 部署配置
│   ├── Postgres/          # PostgreSQL 部署配置
│   ├── Redis/             # Redis 部署配置
│   ├── Minio/             # MinIO 部署配置
│   ├── Elastic/           # Elasticsearch 部署配置
│   └── Build/             # 构建配置 (待开发)
├── Docs/                   # 项目文档
│   ├── 00-INDEX.md        # 文档索引
│   ├── 10-Config-Standard.md     # 配置规范
│   ├── 20-Database-Standard.md   # 数据库规范
│   ├── 30-API-Standard.md        # API 规范
│   ├── 40-Testing-Standard.md    # 测试规范
│   ├── 50-Deployment-Standard.md # 部署规范
│   ├── 60-Security-Standard.md   # 安全规范
│   ├── 70-Performance-Standard.md # 性能规范
│   ├── 80-Observability-Standard.md # 可观测性规范
│   └── 90-Git-Release-Standard.md  # 发布规范
├── Scripts/                # 自动化脚本
│   ├── bootstrap/          # 初始化脚本
│   ├── db/                 # 数据库脚本
│   ├── ci/                 # CI/CD 脚本
│   └── ops/                # 运维脚本
├── env-example-template.txt # 环境变量模板
└── README.md              # 项目说明
```

## 🔧 开发工作流

### 常用命令

```bash
# 环境管理
make up                    # 启动所有服务
make down                  # 停止所有服务
make restart               # 重启所有服务
make logs                  # 查看日志
make clean                 # 清理数据卷

# 代码质量
make lint                  # 代码检查
make test                  # 运行测试
make format                # 格式化代码

# 数据库
make db-migrate            # 运行迁移
make db-seed               # 运行种子数据
make db-reset              # 重置数据库

# 部署
make build                 # 构建镜像
make deploy-dev            # 部署到开发环境
make deploy-prod           # 部署到生产环境
```

### 提交代码

```bash
# 1. 创建功能分支
git checkout -b feature/user-authentication

# 2. 提交更改 (遵循Conventional Commits)
git commit -m "feat: implement user authentication"

# 3. 推送分支
git push origin feature/user-authentication

# 4. 创建Pull Request
# 在GitHub上创建PR，等待审查
```

## 📚 规范文档

请务必阅读以下规范文档：

1. **[00-INDEX.md](Docs/00-INDEX.md)** - 文档总览和阅读顺序
2. **[10-Config-Standard.md](Docs/10-Config-Standard.md)** - 配置与环境变量规范 ⭐
3. **[20-Database-Standard.md](Docs/20-Database-Standard.md)** - 数据库设计规范
4. **[30-API-Standard.md](Docs/30-API-Standard.md)** - API 接口规范
5. **[40-Testing-Standard.md](Docs/40-Testing-Standard.md)** - 测试规范
6. **[50-Deployment-Standard.md](Docs/50-Deployment-Standard.md)** - 部署规范
7. **[60-Security-Standard.md](Docs/60-Security-Standard.md)** - 安全规范
8. **[70-Performance-Standard.md](Docs/70-Performance-Standard.md)** - 性能优化规范
9. **[80-Observability-Standard.md](Docs/80-Observability-Standard.md)** - 可观测性规范
10. **[90-Git-Release-Standard.md](Docs/90-Git-Release-Standard.md)** - 版本控制与发布规范

## ✨ 功能特性

### 🔐 认证系统
- **完整的用户认证流程**: 登录、注册、忘记密码、重置密码
- **企业级UI设计**: 现代化界面，支持明暗主题切换
- **国际化支持**: 中英文双语切换
- **SSO集成**: 可配置的SSO登录按钮
- **响应式设计**: 支持桌面和移动设备

### 🎨 前端特性
- **现代化UI**: 基于Tailwind CSS的企业级设计
- **主题系统**: 自动检测系统偏好，支持手动切换
- **无障碍设计**: 键盘导航、屏幕阅读器支持
- **性能优化**: 代码分割、懒加载、优化的打包

### 🛠️ 开发特性
- **TypeScript**: 完整的类型安全
- **ESLint + Prettier**: 代码质量保证
- **Vitest**: 现代化的测试框架
- **热重载**: 开发时实时更新

#### SSO配置
```bash
# 启用SSO登录按钮
echo "VITE_SSO_ENABLED=true" >> Frontend/.env.local
```

## 🔐 安全注意事项

- 所有敏感信息通过环境变量配置，禁止硬编码
- 生产环境使用强密码和安全配置
- 定期更新依赖包，修复安全漏洞
- 遵循最小权限原则
- 启用所有安全头和防护措施

## 🚢 部署说明

### 开发环境

```bash
# 使用Docker Compose启动
docker-compose -f Deploy/Postgres/docker-compose.yml up -d
docker-compose -f Deploy/Redis/docker-compose.yml up -d
# ... 启动其他服务

# 或者使用统一的docker-compose.yml (待创建)
docker-compose up -d
```

### 生产环境

```bash
# 使用Kubernetes部署
helm upgrade --install novaris-prod ./Deploy/k8s/helm \
  --namespace production \
  --values Deploy/k8s/helm/values-prod.yaml

# 或者使用Docker Compose (简化部署)
docker-compose -f docker-compose.prod.yml up -d
```

## 🤝 贡献指南

1. 阅读[规范文档](Docs/)，理解项目约定
2. 创建功能分支，遵循[提交规范](Docs/90-Git-Release-Standard.md)
3. 编写测试，确保代码质量
4. 提交Pull Request，等待审查
5. 通过CI/CD检查后合并

### 分支策略

- `main`: 主分支，保持可部署状态
- `feature/*`: 功能开发分支
- `hotfix/*`: 紧急修复分支
- `release/*`: 发布准备分支

### 提交规范

```
feat: 新功能
fix: 缺陷修复
docs: 文档变更
style: 代码格式调整
refactor: 代码重构
perf: 性能优化
test: 测试相关
chore: 构建工具变更
```

## 📊 监控与可观测性

- **日志**: 结构化JSON日志，支持多级别
- **指标**: Prometheus指标收集，Grafana可视化
- **链路追踪**: Jaeger分布式链路追踪
- **健康检查**: 自动化的服务健康监控
- **告警**: 基于指标的智能告警

## 🔍 故障排除

### 常见问题

**服务启动失败**
```bash
# 检查端口占用
netstat -tulpn | grep :8000

# 检查Docker服务状态
docker-compose ps

# 查看详细日志
docker-compose logs backend
```

**数据库连接失败**
```bash
# 检查数据库服务
docker-compose ps postgres

# 测试连接
psql -h localhost -U novaris_user -d novaris_db

# 检查环境变量
echo $DB_PASSWORD
```

**前端构建失败**
```bash
# 清理缓存
cd Frontend
rm -rf node_modules package-lock.json
npm install

# 检查Node.js版本
node --version
npm --version
```

### 获取帮助

- 查看[文档](Docs/)获取详细信息
- 检查[Issues](../../issues)了解已知问题
- 提交新Issue描述遇到的问题

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 👥 贡献者

感谢所有为本项目做出贡献的开发者！

## 📞 联系我们

- 项目维护者: Noveris AI Team
- 邮箱: team@noveris.ai
- 文档: [规范文档](Docs/)

---

**最后更新**: 2026年1月13日 | **版本**: v1.0.0

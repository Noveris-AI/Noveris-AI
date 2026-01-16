# Git版本控制与发布规范

## 目的
建立标准化的版本控制流程，确保代码质量、发布可追溯性，并支持高效的团队协作和持续交付。

## 适用范围
- **强制**: 所有团队成员 - Git操作、代码提交、分支管理
- **验证**: CI/CD流水线自动检查，代码审查时验证

## 核心原则

### MUST - 强制规则
1. **提交规范**: 所有提交必须遵循Conventional Commits格式
2. **分支策略**: 使用Git Flow或Trunk-based分支策略
3. **代码审查**: 所有代码变更必须通过Pull Request审查
4. **版本号**: 遵循语义化版本控制 (Semantic Versioning)
5. **发布标签**: 所有发布必须有Git标签和发布说明

### SHOULD - 建议规则
1. 使用Git钩子自动化检查
2. 实施自动版本号生成
3. 建立发布候选流程
4. 实施发布后监控

## 分支策略

### Trunk-based分支策略（推荐）
```
main (主分支)
├── feature/* (功能分支)
├── hotfix/* (热修复分支)
└── release/* (发布分支)
```

#### 分支职责
- **main**: 主分支，始终保持可部署状态
- **feature/**: 功能开发分支，从main创建，开发完成后合并回main
- **hotfix/**: 紧急修复分支，从main创建，修复完成后合并回main
- **release/**: 发布准备分支，从main创建，用于发布前的最终测试

#### 工作流程
```bash
# 1. 创建功能分支
git checkout -b feature/user-authentication main

# 2. 开发功能
git add .
git commit -m "feat: implement user login functionality"

# 3. 推送分支
git push origin feature/user-authentication

# 4. 创建Pull Request进行代码审查

# 5. 合并到main（通过PR合并）
git checkout main
git pull origin main
```

### 合并策略
```bash
# 使用Squash合并保持main分支整洁
git merge --squash feature/user-authentication

# 或者使用Merge Commit保留完整历史
git merge feature/user-authentication --no-ff

# 删除已合并的分支
git branch -d feature/user-authentication
git push origin --delete feature/user-authentication
```

## 提交规范

### Conventional Commits格式
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

#### 提交类型
- **feat**: 新功能
- **fix**: 缺陷修复
- **docs**: 文档变更
- **style**: 代码格式调整（不影响逻辑）
- **refactor**: 代码重构
- **perf**: 性能优化
- **test**: 测试相关变更
- **chore**: 构建工具或辅助工具变更

#### 示例提交
```bash
# 功能提交
feat: add user registration endpoint
feat(auth): implement JWT token validation

# 修复提交
fix: resolve memory leak in user service
fix(api): handle null pointer exception in login

# 文档提交
docs: update API documentation for v2.0
docs(readme): add installation instructions

# 重构提交
refactor: simplify user authentication logic
refactor(db): migrate to SQLAlchemy 2.0

# 性能优化
perf: optimize database query for user list
perf(cache): implement Redis caching for user data

# 测试提交
test: add unit tests for user service
test(e2e): add end-to-end tests for registration flow

# 构建工具变更
chore: update dependencies to latest versions
chore(ci): add automated testing pipeline
```

### 提交消息检查
```bash
#!/bin/bash
# .git/hooks/commit-msg

COMMIT_MSG_FILE=$1
COMMIT_MSG=$(cat $COMMIT_MSG_FILE)

# 检查提交消息格式
if ! echo "$COMMIT_MSG" | grep -qE "^(feat|fix|docs|style|refactor|perf|test|chore)(\(.+\))?: .{1,}"; then
    echo "错误: 提交消息不符合Conventional Commits格式"
    echo "正确格式: type(scope): description"
    echo "示例: feat(auth): add user login functionality"
    exit 1
fi

# 检查提交消息长度
if [ ${#COMMIT_MSG} -gt 100 ]; then
    echo "警告: 提交消息过长（超过100字符）"
fi

exit 0
```

## 版本号管理

### 语义化版本控制
```
MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]

示例:
1.0.0        # 初始版本
1.0.1        # 向后兼容的缺陷修复
1.1.0        # 向后兼容的新功能
2.0.0        # 不向后兼容的变更
1.0.0-alpha  # 预发布版本
1.0.0-rc.1   # 发布候选版本
```

### 版本号递增规则
- **MAJOR**: 不向后兼容的API变更
- **MINOR**: 向后兼容的新功能
- **PATCH**: 向后兼容的缺陷修复

### 自动版本号生成
```python
# scripts/version.py
import subprocess
import re
from typing import Tuple

def get_git_info() -> dict:
    """获取Git信息"""
    try:
        # 获取最新标签
        latest_tag = subprocess.check_output(
            ["git", "describe", "--tags", "--abbrev=0"],
            stderr=subprocess.DEVNULL
        ).decode().strip()

        # 获取提交数
        commit_count = subprocess.check_output(
            ["git", "rev-list", "--count", f"{latest_tag}..HEAD"]
        ).decode().strip()

        # 获取短SHA
        short_sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"]
        ).decode().strip()

        return {
            "latest_tag": latest_tag,
            "commit_count": int(commit_count),
            "short_sha": short_sha
        }
    except subprocess.CalledProcessError:
        return {
            "latest_tag": "v0.0.0",
            "commit_count": 0,
            "short_sha": "0000000"
        }

def calculate_next_version() -> str:
    """计算下一个版本号"""
    git_info = get_git_info()
    latest_tag = git_info["latest_tag"].lstrip("v")
    commit_count = git_info["commit_count"]

    # 解析当前版本
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", latest_tag)
    if not match:
        return "1.0.0"

    major, minor, patch = map(int, match.groups())

    # 根据提交类型确定版本递增
    commit_types = get_commit_types_since_tag(git_info["latest_tag"])

    if "BREAKING CHANGE" in commit_types or any(t.startswith("feat!:") for t in commit_types):
        major += 1
        minor = 0
        patch = 0
    elif any(t.startswith("feat") for t in commit_types):
        minor += 1
        patch = 0
    else:
        patch += 1

    version = f"{major}.{minor}.{patch}"

    # 如果有未发布的提交，添加构建元数据
    if commit_count > 0:
        version += f"-dev.{commit_count}+{git_info['short_sha']}"

    return version

def get_commit_types_since_tag(tag: str) -> list:
    """获取自上次标签以来的提交类型"""
    try:
        commits = subprocess.check_output(
            ["git", "log", f"{tag}..HEAD", "--oneline"]
        ).decode().strip().split("\n")

        types = []
        for commit in commits:
            if ": " in commit:
                commit_type = commit.split(": ")[0].split("(")[0]
                types.append(commit_type)

        return types
    except subprocess.CalledProcessError:
        return []

if __name__ == "__main__":
    version = calculate_next_version()
    print(version)
```

## 代码审查规范

### Pull Request模板
```markdown
<!-- .github/PULL_REQUEST_TEMPLATE.md -->

## 描述
简要描述这个PR的目的和变更内容

## 类型
- [ ] 🐛 缺陷修复 (fix)
- [ ] ✨ 新功能 (feat)
- [ ] 📚 文档更新 (docs)
- [ ] 🎨 代码样式 (style)
- [ ] 🔄 重构 (refactor)
- [ ] ⚡ 性能优化 (perf)
- [ ] 🧪 测试 (test)
- [ ] 🔧 构建工具 (chore)

## 范围
- [ ] 前端 (frontend)
- [ ] 后端 (backend)
- [ ] 部署 (deploy)
- [ ] 文档 (docs)
- [ ] 其他

## 检查清单
- [ ] 代码遵循项目规范
- [ ] 添加了相应的测试
- [ ] 更新了相关文档
- [ ] 通过了所有测试
- [ ] 性能测试通过

## 测试
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] E2E测试通过

## 关联Issue
Closes #123

## 其他信息
任何其他需要注意的信息
```

### 代码审查要点
```markdown
### 🔍 必须检查项
- [ ] **功能完整性**: 代码实现是否完整解决需求
- [ ] **代码质量**: 遵循编码规范，无明显代码异味
- [ ] **测试覆盖**: 有足够的单元测试和集成测试
- [ ] **文档更新**: API变更是否有相应文档更新
- [ ] **性能影响**: 新代码是否有性能问题
- [ ] **安全检查**: 无安全漏洞，遵循安全规范

### ⚠️ 重点关注项
- [ ] **硬编码检查**: 无硬编码的配置、URL、密钥
- [ ] **错误处理**: 适当的异常处理和错误消息
- [ ] **日志记录**: 重要的操作有适当的日志记录
- [ ] **数据库变更**: 迁移脚本正确，回滚计划完整
- [ ] **API兼容性**: 变更是否向后兼容
- [ ] **依赖更新**: 新依赖是否有安全风险

### 📋 审查流程
1. **自动检查**: CI流水线运行lint、test、安全扫描
2. **初步审查**: 审查者检查代码结构和逻辑
3. **详细审查**: 检查业务逻辑、性能、安全性
4. **测试验证**: 在测试环境验证功能
5. **批准合并**: 满足所有要求后批准合并
```

## 发布流程

### 发布准备
```bash
# 1. 创建发布分支
git checkout -b release/v1.0.0 main

# 2. 更新版本号
echo "1.0.0" > VERSION
git add VERSION
git commit -m "chore: bump version to 1.0.0"

# 3. 更新CHANGELOG
# 使用conventional-changelog生成
npm install -g conventional-changelog-cli
conventional-changelog -p angular -i CHANGELOG.md -s

git add CHANGELOG.md
git commit -m "docs: update changelog for v1.0.0"

# 4. 推送发布分支
git push origin release/v1.0.0
```

### 发布执行
```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    branches:
      - release/v*

jobs:
  release:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Extract version
      id: version
      run: |
        VERSION=$(echo ${{ github.ref_name }} | sed 's/release\/v//')
        echo "version=$VERSION" >> $GITHUB_OUTPUT

    - name: Build and test
      run: |
        # 运行完整测试套件
        npm test
        npm run e2e

    - name: Create GitHub release
      uses: actions/create-release@v1
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      with:
        tag_name: v${{ steps.version.outputs.version }}
        release_name: Release v${{ steps.version.outputs.version }}
        body: |
          ## What's Changed

          ### Features
          - New feature description

          ### Bug Fixes
          - Bug fix description

          ### Other Changes
          - Documentation updates
          - Dependency updates

        draft: false
        prerelease: false

    - name: Deploy to production
      run: |
        # 触发生产部署
        # 这里可以调用部署API或触发其他workflow
```

### 发布后验证
```bash
# 1. 验证部署成功
curl -f https://api.noveris.ai/health

# 2. 验证版本信息
curl https://api.noveris.ai/version

# 3. 监控告警检查
# 检查是否有新的错误告警

# 4. 功能验证
# 运行冒烟测试验证关键功能

# 5. 性能监控
# 检查响应时间和错误率是否正常

# 6. 回滚准备
# 确保有回滚计划和快速回滚能力
```

## CI/CD集成

### GitHub Actions配置
```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Setup Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '18'

    - name: Install dependencies
      run: npm ci

    - name: Run ESLint
      run: npm run lint

    - name: Run Prettier check
      run: npm run format:check

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v4

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Run tests
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test
      run: |
        pytest --cov=src --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  security:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Run security scan
      uses: securecodewarrior/github-actions-gitleaks@master
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

    - name: Dependency check
      uses: dependency-check/Dependency-Check_Action@main
      with:
        project: 'Noveris AI'
        path: '.'
        format: 'ALL'

  build:
    needs: [lint, test, security]
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Build Docker image
      run: |
        docker build -t novaris-ai/app:${{ github.sha }} .

    - name: Push to registry
      run: |
        echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
        docker push novaris-ai/app:${{ github.sha }}
```

## 检查清单

### 分支管理检查
- [ ] 使用正确的分支命名规范
- [ ] 功能分支及时合并和清理
- [ ] 主分支始终保持可部署状态
- [ ] 紧急修复使用专用分支

### 提交规范检查
- [ ] 所有提交遵循Conventional Commits格式
- [ ] 提交消息清晰描述变更内容
- [ ] 大变更拆分为多个小提交
- [ ] 提交前运行必要的检查

### 代码审查检查
- [ ] 所有变更通过Pull Request
- [ ] 至少一人审查代码
- [ ] 审查意见得到妥善处理
- [ ] 审查通过后才能合并

### 发布流程检查
- [ ] 版本号遵循语义化版本控制
- [ ] 发布前进行充分测试
- [ ] 发布后进行验证监控
- [ ] 有完整的回滚计划

### CI/CD检查
- [ ] 自动化流水线覆盖所有检查
- [ ] 失败时阻止代码合并
- [ ] 构建产物正确存储
- [ ] 部署过程自动化

## 示例工具配置

### Commitizen配置
```json
// .czrc
{
  "path": "cz-conventional-changelog",
  "types": [
    {
      "value": "feat",
      "name": "feat:     新功能"
    },
    {
      "value": "fix",
      "name": "fix:      缺陷修复"
    },
    {
      "value": "docs",
      "name": "docs:     文档变更"
    },
    {
      "value": "style",
      "name": "style:    代码格式"
    },
    {
      "value": "refactor",
      "name": "refactor: 代码重构"
    },
    {
      "value": "perf",
      "name": "perf:     性能优化"
    },
    {
      "value": "test",
      "name": "test:      测试相关"
    },
    {
      "value": "chore",
      "name": "chore:    构建工具"
    }
  ]
}
```

## 相关文档
- [配置规范](10-Config-Standard.md) - CI/CD配置管理
- [测试规范](40-Testing-Standard.md) - 测试流程集成
- [部署规范](50-Deployment-Standard.md) - 部署流程规范
- [可观测性规范](80-Observability-Standard.md) - 发布监控要求

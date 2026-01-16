# 测试规范

## 目的
建立全面的测试策略，确保代码质量和系统稳定性，涵盖单元测试、集成测试、端到端测试等多个层次。

## 适用范围
- **强制**: Backend (Python+FastAPI), Frontend (React) - 所有代码
- **验证**: CI/CD流水线中自动执行，代码审查时检查

## 核心原则

### MUST - 强制规则
1. **测试金字塔**: 遵循单元测试 > 集成测试 > E2E测试的比例分配
2. **覆盖率要求**: 单元测试覆盖率不低于80%，关键路径不低于90%
3. **测试隔离**: 每个测试用例必须独立运行，无副作用
4. **测试命名**: 使用描述性命名，说明测试的目的和预期结果
5. **Mock外部依赖**: 外部服务、数据库、文件系统等必须使用Mock

### SHOULD - 建议规则
1. 使用测试驱动开发 (TDD)
2. 实施契约测试确保服务间兼容性
3. 定期执行突变测试评估测试质量
4. 建立性能回归测试基线

## 测试金字塔

### 测试层次分布
```
     ┌─────────────────┐  少量 (5-10%)
     │   E2E Tests     │  用户视角的完整流程测试
     │                 │  测试完整的用户旅程
     └─────────────────┘

     ┌─────────────────┐  中等 (15-20%)
     │Integration Tests│  服务间集成测试
     │                 │  API接口测试、数据库集成
     └─────────────────┘

     ┌─────────────────┐  大量 (70-80%)
     │  Unit Tests     │  单元测试
     │                 │  函数/方法级测试
     └─────────────────┘
```

### 各层测试职责
```python
# 单元测试 - 测试单个函数/方法
def test_user_creation():
    """测试用户创建逻辑"""
    user_service = UserService()
    user_data = {"email": "test@example.com", "name": "Test User"}

    user = user_service.create_user(user_data)

    assert user.email == "test@example.com"
    assert user.name == "Test User"
    assert user.is_active == True

# 集成测试 - 测试组件间协作
def test_user_registration_flow():
    """测试用户注册完整流程"""
    # 模拟完整的注册流程：验证 -> 创建用户 -> 发送邮件
    pass

# E2E测试 - 测试完整用户旅程
def test_complete_user_journey():
    """测试从注册到使用的完整流程"""
    # 注册 -> 登录 -> 创建内容 -> 查看内容
    pass
```

## 单元测试规范

### 测试文件组织
```
Backend/
├── src/
│   ├── users/
│   │   ├── user_service.py
│   │   ├── user_repository.py
│   │   └── user_model.py
│   └── posts/
│       ├── post_service.py
│       └── post_repository.py
└── tests/
    ├── unit/
    │   ├── users/
    │   │   ├── test_user_service.py
    │   │   └── test_user_repository.py
    │   └── posts/
    │       └── test_post_service.py
    ├── integration/
    │   ├── test_user_registration.py
    │   └── test_post_creation.py
    └── e2e/
        ├── test_user_journey.py
        └── test_content_management.py
```

### 单元测试最佳实践
```python
import pytest
from unittest.mock import Mock, patch
from users.user_service import UserService
from users.user_repository import UserRepository

class TestUserService:
    def setup_method(self):
        """每个测试方法前执行"""
        self.user_repository = Mock(spec=UserRepository)
        self.user_service = UserService(self.user_repository)

    def teardown_method(self):
        """每个测试方法后执行"""
        pass

    def test_create_user_success(self):
        """测试成功创建用户"""
        # Arrange
        user_data = {
            "email": "test@example.com",
            "name": "Test User",
            "password": "securepass123"
        }
        expected_user = Mock()
        expected_user.id = 1
        expected_user.email = user_data["email"]

        self.user_repository.create.return_value = expected_user

        # Act
        result = self.user_service.create_user(user_data)

        # Assert
        assert result.id == 1
        assert result.email == "test@example.com"
        self.user_repository.create.assert_called_once_with(user_data)

    def test_create_user_email_exists(self):
        """测试创建用户时邮箱已存在"""
        # Arrange
        user_data = {"email": "existing@example.com", "name": "Test User"}
        self.user_repository.get_by_email.return_value = Mock()  # 模拟邮箱已存在

        # Act & Assert
        with pytest.raises(ValueError, match="Email already exists"):
            self.user_service.create_user(user_data)

    @patch('users.user_service.send_welcome_email')
    def test_create_user_sends_welcome_email(self, mock_send_email):
        """测试创建用户后发送欢迎邮件"""
        # Arrange
        user_data = {"email": "new@example.com", "name": "New User"}
        new_user = Mock()
        new_user.email = user_data["email"]

        self.user_repository.create.return_value = new_user

        # Act
        self.user_service.create_user(user_data)

        # Assert
        mock_send_email.assert_called_once_with(new_user.email)
```

### Mock和Stub使用
```python
from unittest.mock import Mock, MagicMock, patch
import pytest

# 1. Mock外部服务
@patch('users.email_service.EmailService.send_email')
def test_user_notification(mock_send_email):
    mock_send_email.return_value = True  # 模拟发送成功

    user_service = UserService()
    user_service.notify_user_registration("test@example.com")

    mock_send_email.assert_called_once_with("test@example.com", "Welcome!")

# 2. Mock数据库操作
def test_get_user_by_id():
    mock_repo = Mock()
    mock_user = Mock()
    mock_user.id = 1
    mock_user.name = "Test User"
    mock_repo.get_by_id.return_value = mock_user

    user_service = UserService(mock_repo)
    user = user_service.get_user(1)

    assert user.name == "Test User"
    mock_repo.get_by_id.assert_called_once_with(1)

# 3. 使用fixtures复用测试数据
@pytest.fixture
def sample_user_data():
    return {
        "email": "test@example.com",
        "name": "Test User",
        "password": "hashed_password"
    }

@pytest.fixture
def mock_user_repository():
    repo = Mock()
    repo.create.return_value = Mock(id=1, email="test@example.com")
    return repo

def test_create_user_with_fixtures(sample_user_data, mock_user_repository):
    user_service = UserService(mock_user_repository)
    user = user_service.create_user(sample_user_data)

    assert user.id == 1
    assert user.email == sample_user_data["email"]
```

## 集成测试规范

### API集成测试
```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from main import app
from database import get_db_session

@pytest.mark.asyncio
class TestUserAPI:
    @pytest.fixture
    async def client(self):
        """测试客户端fixture"""
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            yield client

    @pytest.fixture
    async def db_session(self):
        """数据库会话fixture"""
        # 使用测试数据库
        session = get_test_db_session()
        yield session
        await session.close()

    async def test_create_user_api(self, client, db_session):
        """测试创建用户API"""
        user_data = {
            "email": "test@example.com",
            "name": "Test User",
            "password": "securepass123"
        }

        response = await client.post("/api/v1/users", json=user_data)

        assert response.status_code == 201
        data = response.json()
        assert data["success"] == True
        assert data["data"]["email"] == user_data["email"]

        # 验证数据库中确实创建了用户
        user_in_db = await db_session.execute(
            select(User).where(User.email == user_data["email"])
        )
        user = user_in_db.scalar_one_or_none()
        assert user is not None
        assert user.name == user_data["name"]

    async def test_get_users_pagination(self, client):
        """测试用户列表分页"""
        # 先创建一些测试用户
        for i in range(5):
            await client.post("/api/v1/users", json={
                "email": f"user{i}@example.com",
                "name": f"User {i}",
                "password": "password123"
            })

        # 测试分页
        response = await client.get("/api/v1/users?page=1&page_size=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 2
```

### 数据库集成测试
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from database import Base

@pytest.fixture
async def test_db():
    """测试数据库fixture"""
    # 使用SQLite内存数据库进行测试
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 创建会话
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    # 清理
    await engine.dispose()

@pytest.mark.asyncio
async def test_user_repository_integration(test_db):
    """测试用户仓库的数据库集成"""
    from users.user_repository import UserRepository

    repo = UserRepository(test_db)

    # 创建用户
    user_data = {
        "tenant_id": 1,
        "email": "test@example.com",
        "password_hash": "hashed_password",
        "name": "Test User"
    }

    user = await repo.create(user_data)
    assert user.id is not None
    assert user.email == user_data["email"]

    # 查询用户
    found_user = await repo.get_by_email("test@example.com")
    assert found_user is not None
    assert found_user.name == user_data["name"]

    # 更新用户
    updated_data = {"name": "Updated Name"}
    updated_user = await repo.update(user.id, updated_data)
    assert updated_user.name == "Updated Name"

    # 删除用户（软删除）
    await repo.delete(user.id)
    deleted_user = await repo.get_by_id(user.id)
    assert deleted_user.deleted_at is not None
```

## 前端测试规范

### React组件测试
```typescript
// src/components/UserProfile.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { UserProfile } from './UserProfile';
import { rest } from 'msw';
import { setupServer } from 'msw/node';

// Mock API服务器
const server = setupServer(
  rest.get('/api/v1/users/profile', (req, res, ctx) => {
    return res(ctx.json({
      success: true,
      data: {
        id: 1,
        name: 'Test User',
        email: 'test@example.com'
      }
    }));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('UserProfile', () => {
  it('renders user profile correctly', async () => {
    render(<UserProfile userId={1} />);

    // 等待数据加载
    await waitFor(() => {
      expect(screen.getByText('Test User')).toBeInTheDocument();
      expect(screen.getByText('test@example.com')).toBeInTheDocument();
    });
  });

  it('handles loading state', () => {
    render(<UserProfile userId={1} />);

    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('handles error state', async () => {
    // Mock错误响应
    server.use(
      rest.get('/api/v1/users/profile', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({
          success: false,
          error: { message: 'Server error' }
        }));
      })
    );

    render(<UserProfile userId={1} />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load profile')).toBeInTheDocument();
    });
  });
});
```

### React Hooks测试
```typescript
// src/hooks/useUser.test.ts
import { renderHook, act, waitFor } from '@testing-library/react';
import { useUser } from './useUser';

// Mock fetch
global.fetch = jest.fn();

describe('useUser', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('fetches user data successfully', async () => {
    const mockUser = { id: 1, name: 'Test User' };
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: mockUser
      })
    });

    const { result } = renderHook(() => useUser(1));

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.user).toEqual(mockUser);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBe(null);
    });
  });

  it('handles fetch error', async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useUser(1));

    await waitFor(() => {
      expect(result.current.user).toBe(null);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBe('Network error');
    });
  });
});
```

## 测试数据管理

### 测试数据隔离
```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_test_db_session

@pytest.fixture
async def clean_db():
    """提供干净的测试数据库"""
    session = get_test_db_session()

    # 清理所有表
    await session.execute(text("DELETE FROM posts"))
    await session.execute(text("DELETE FROM users"))
    await session.commit()

    yield session

    # 测试后清理
    await session.execute(text("DELETE FROM posts"))
    await session.execute(text("DELETE FROM users"))
    await session.commit()
    await session.close()

@pytest.fixture
async def sample_user(clean_db):
    """创建示例用户"""
    from users.user_repository import UserRepository

    repo = UserRepository(clean_db)
    user_data = {
        "tenant_id": 1,
        "email": "test@example.com",
        "password_hash": "hashed",
        "name": "Test User"
    }

    user = await repo.create(user_data)
    return user
```

### 测试容器策略
```yaml
# docker-compose.test.yml
version: '3.8'
services:
  test-db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: test_db
      POSTGRES_USER: test_user
      POSTGRES_PASSWORD: test_password
    ports:
      - "5433:5432"
    volumes:
      - test_db_data:/var/lib/postgresql/data

  test-redis:
    image: redis:7-alpine
    ports:
      - "6380:6379"

volumes:
  test_db_data:
```

## CI/CD中的测试执行

### GitHub Actions测试流程
```yaml
# .github/workflows/test.yml
name: Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
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

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Run linting
      run: |
        flake8 src/ tests/
        mypy src/

    - name: Run tests
      env:
        DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
        REDIS_URL: redis://localhost:6379/0
      run: |
        pytest tests/ --cov=src/ --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### 覆盖率门禁
```python
# pyproject.toml 或 setup.cfg
[tool:pytest]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "--cov=src",
    "--cov-report=term-missing",
    "--cov-report=xml",
    "--cov-fail-under=80"
]

[tool:coverage:run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/venv/*"
]

[tool:coverage:report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError"
]
```

## 检查清单

### 测试设计检查
- [ ] 遵循测试金字塔结构
- [ ] 测试文件与源代码文件对应
- [ ] 使用描述性测试命名
- [ ] 每个测试用例独立运行

### 单元测试检查
- [ ] Mock外部依赖和服务
- [ ] 覆盖正常路径和异常路径
- [ ] 使用fixtures复用测试数据
- [ ] 测试覆盖率达到80%以上

### 集成测试检查
- [ ] 使用真实的数据库连接
- [ ] 测试API的完整流程
- [ ] 验证数据持久化
- [ ] 包含错误场景测试

### 前端测试检查
- [ ] 测试组件渲染和交互
- [ ] Mock API调用和状态管理
- [ ] 覆盖用户事件处理
- [ ] 测试错误边界

### CI/CD检查
- [ ] 测试在CI流水线中自动执行
- [ ] 覆盖率报告自动生成
- [ ] 设置覆盖率门禁
- [ ] 失败时阻止合并

## 示例工具配置

### pytest配置
```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --strict-markers
    --tb=short
    --cov=src
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=80
markers =
    unit: 单元测试
    integration: 集成测试
    e2e: 端到端测试
    slow: 慢速测试
```

### Jest配置（前端）
```javascript
// jest.config.js
module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/src/setupTests.js'],
  testMatch: [
    '<rootDir>/src/**/__tests__/**/*.{js,jsx,ts,tsx}',
    '<rootDir>/src/**/*.{test,spec}.{js,jsx,ts,tsx}'
  ],
  collectCoverageFrom: [
    'src/**/*.{js,jsx,ts,tsx}',
    '!src/index.js',
    '!src/setupTests.js'
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  },
  moduleNameMapping: {
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy'
  }
};
```

## 相关文档
- [配置规范](10-Config-Standard.md) - 测试环境配置
- [API规范](30-API-Standard.md) - API测试接口
- [部署规范](50-Deployment-Standard.md) - CI/CD测试集成
- [安全规范](60-Security-Standard.md) - 安全测试要求

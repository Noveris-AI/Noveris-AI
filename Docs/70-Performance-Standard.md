# 性能优化规范

## 目的
建立系统的性能优化规范，确保应用在高负载情况下保持良好的响应速度和资源利用率，涵盖前端性能、后端优化、数据库调优等关键方面。

## 适用范围
- **强制**: Backend (Python+FastAPI), Frontend (React) - 所有性能相关代码
- **验证**: 性能测试自动执行，代码审查时检查性能问题

## 核心原则

### MUST - 强制规则
1. **性能预算**: 设定明确的性能目标和预算
2. **响应时间**: API响应时间不超过500ms，页面加载不超过3秒
3. **资源监控**: 实施全面的性能监控和告警
4. **缓存策略**: 合理使用缓存减少重复计算
5. **数据库优化**: 避免N+1查询，优化慢查询
6. **前端优化**: 实施代码分割、懒加载等优化

### SHOULD - 建议规则
1. 实施性能回归测试
2. 使用CDN加速静态资源
3. 实施数据库连接池
4. 监控第三方服务性能

## 性能预算与SLO

### 性能指标定义
```python
# config/performance.py
PERFORMANCE_BUDGET = {
    # 响应时间 (毫秒)
    "api_response_time": {
        "p95": 500,    # 95%请求响应时间不超过500ms
        "p99": 1000,   # 99%请求响应时间不超过1s
    },

    # 前端性能
    "page_load_time": {
        "first_contentful_paint": 1500,  # 首次内容绘制
        "largest_contentful_paint": 2500, # 最大内容绘制
        "first_input_delay": 100,         # 首次输入延迟
        "cumulative_layout_shift": 0.1,   # 累积布局偏移
    },

    # 资源使用
    "resource_usage": {
        "cpu_usage": 70,      # CPU使用率不超过70%
        "memory_usage": 80,   # 内存使用率不超过80%
        "disk_io": 1000,      # 磁盘I/O不超过1000 IOPS
    },

    # 错误率
    "error_rate": {
        "api_error_rate": 0.01,  # API错误率不超过1%
        "frontend_error_rate": 0.05, # 前端错误率不超过5%
    }
}
```

### SLO/SLI定义
```yaml
# Service Level Indicators (SLI)
slis:
  - name: api_latency
    description: "API响应时间"
    query: |
      histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
    threshold: 0.5

  - name: api_availability
    description: "API可用性"
    query: |
      1 - (rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]))
    threshold: 0.999

  - name: database_connection_pool_usage
    description: "数据库连接池使用率"
    query: |
      db_connection_pool_used / db_connection_pool_max
    threshold: 0.8

# Service Level Objectives (SLO)
slos:
  - name: api_performance
    description: "API性能SLO"
    sli: api_latency
    target: 0.95  # 95%的请求满足性能要求
    window: 30d

  - name: api_reliability
    description: "API可靠性SLO"
    sli: api_availability
    target: 0.999  # 99.9%可用性
    window: 30d
```

## 后端性能优化

### 数据库查询优化
```python
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload
from fastapi import Depends
from typing import List

# 错误示例：N+1查询问题
@app.get("/api/v1/posts")
async def get_posts_bad(session: AsyncSession = Depends(get_db)):
    posts = await session.execute(select(Post))
    result = []

    for post in posts.scalars():
        # 每次循环都会执行一次查询！
        author = await session.execute(
            select(User).where(User.id == post.user_id)
        )
        result.append({
            "id": post.id,
            "title": post.title,
            "author": author.scalar().name
        })

    return result

# 正确示例：使用join避免N+1查询
@app.get("/api/v1/posts")
async def get_posts_good(session: AsyncSession = Depends(get_db)):
    query = select(Post).options(
        joinedload(Post.author)  # 预加载关联数据
    )

    posts = await session.execute(query)
    result = []

    for post in posts.scalars().unique():
        result.append({
            "id": post.id,
            "title": post.title,
            "author": post.author.name  # 已经加载，无需额外查询
        })

    return result

# 分页查询优化
@app.get("/api/v1/posts")
async def get_posts_paginated(
    page: int = 1,
    page_size: int = 20,
    session: AsyncSession = Depends(get_db)
):
    # 使用OFFSET分页（适合小数据集）
    if page * page_size < 10000:  # 小数据集使用OFFSET
        query = select(Post).options(
            joinedload(Post.author)
        ).offset((page - 1) * page_size).limit(page_size)

    else:  # 大数据集使用游标分页
        # 获取上一页最后一条记录的ID
        last_id = get_last_id_from_cache(page, page_size)
        query = select(Post).options(
            joinedload(Post.author)
        ).where(Post.id > last_id).limit(page_size)

    posts = await session.execute(query)
    return [post.to_dict() for post in posts.scalars().unique()]
```

### 缓存策略
```python
import redis
from functools import wraps
from typing import Any, Optional
import json
import hashlib

class CacheManager:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def _make_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """生成缓存key"""
        key_data = {
            "func": func_name,
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return f"cache:{hashlib.md5(key_str.encode()).hexdigest()}"

    def cached(self, ttl: int = 300):
        """缓存装饰器"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # 生成缓存key
                cache_key = self._make_key(func.__name__, args, kwargs)

                # 尝试从缓存获取
                cached_result = self.redis.get(cache_key)
                if cached_result:
                    return json.loads(cached_result)

                # 执行函数
                result = await func(*args, **kwargs)

                # 写入缓存
                self.redis.setex(cache_key, ttl, json.dumps(result))

                return result

            return wrapper
        return decorator

    def invalidate_pattern(self, pattern: str):
        """按模式清除缓存"""
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)

# 使用缓存
cache_manager = CacheManager(redis_client)

@cache_manager.cached(ttl=600)  # 缓存10分钟
async def get_user_posts(user_id: int, page: int = 1):
    # 复杂的数据库查询
    pass

# 缓存预热
async def warmup_cache():
    """预热热门数据的缓存"""
    popular_users = await get_popular_users()
    for user in popular_users:
        await get_user_posts(user.id)  # 这会触发缓存

# 缓存失效策略
async def create_post(post_data: dict, user_id: int):
    # 创建帖子
    post = await create_post_in_db(post_data, user_id)

    # 清除相关缓存
    cache_manager.invalidate_pattern(f"cache:*get_user_posts*{user_id}*")

    return post
```

### 异步编程优化
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
import aiofiles
import httpx

class AsyncOptimizer:
    @staticmethod
    async def parallel_api_calls(urls: List[str]) -> List[dict]:
        """并行调用多个API"""
        async with httpx.AsyncClient() as client:
            tasks = [client.get(url) for url in urls]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            results = []
            for response in responses:
                if isinstance(response, Exception):
                    results.append({"error": str(response)})
                else:
                    results.append(response.json())

            return results

    @staticmethod
    async def batch_database_operations(operations: List[dict]):
        """批量数据库操作"""
        async with get_db_session() as session:
            # 使用批量插入
            if operations[0].get("type") == "insert":
                await session.execute(
                    insert(User),
                    operations
                )
            # 使用批量更新
            elif operations[0].get("type") == "update":
                for op in operations:
                    await session.execute(
                        update(User).where(User.id == op["id"]).values(**op["data"])
                    )

            await session.commit()

    @staticmethod
    def run_in_threadpool(func, *args, **kwargs):
        """在线程池中运行阻塞操作"""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, func, *args, **kwargs)

# 使用示例
async def process_user_data():
    # 并行处理多个用户的头像上传
    upload_tasks = []
    for user in users:
        task = AsyncOptimizer.run_in_threadpool(
            process_image,
            user.avatar_file
        )
        upload_tasks.append(task)

    # 等待所有上传完成
    await asyncio.gather(*upload_tasks)

    # 批量更新数据库
    update_operations = [
        {"id": user.id, "data": {"avatar_processed": True}}
        for user in users
    ]
    await AsyncOptimizer.batch_database_operations(update_operations)
```

## 前端性能优化

### React性能优化
```typescript
// src/hooks/useMemoExample.tsx
import { useMemo, useCallback } from 'react';

const UserList = ({ users, filter }: UserListProps) => {
  // 使用useMemo缓存过滤结果
  const filteredUsers = useMemo(() => {
    console.log('Filtering users...'); // 只在依赖变化时执行
    return users.filter(user =>
      user.name.toLowerCase().includes(filter.toLowerCase())
    );
  }, [users, filter]);

  // 使用useCallback缓存函数引用
  const handleUserClick = useCallback((userId: number) => {
    console.log('User clicked:', userId);
  }, []);

  return (
    <div>
      {filteredUsers.map(user => (
        <UserItem
          key={user.id}
          user={user}
          onClick={handleUserClick}
        />
      ))}
    </div>
  );
};

// 组件懒加载
import { lazy, Suspense } from 'react';

const LazyUserProfile = lazy(() => import('./UserProfile'));

const App = () => (
  <Suspense fallback={<div>Loading...</div>}>
    <LazyUserProfile />
  </Suspense>
);

// 使用React.memo避免不必要的重渲染
import { memo } from 'react';

const UserItem = memo(({ user, onClick }: UserItemProps) => {
  console.log('UserItem rendered'); // 只在props变化时渲染
  return (
    <div onClick={() => onClick(user.id)}>
      {user.name}
    </div>
  );
});
```

### 代码分割与懒加载
```typescript
// src/App.tsx
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';

// 路由级别的代码分割
const Home = lazy(() => import('./pages/Home'));
const About = lazy(() => import('./pages/About'));
const Dashboard = lazy(() => import('./pages/Dashboard'));

const App = () => (
  <BrowserRouter>
    <Suspense fallback={<div>Loading...</div>}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/about" element={<About />} />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </Suspense>
  </BrowserRouter>
);

// 组件级别的懒加载
const ExpensiveComponent = lazy(() =>
  import('./components/ExpensiveComponent')
);

// 基于用户交互的懒加载
import { useState, useEffect } from 'react';

const LazyLoadOnDemand = () => {
  const [showComponent, setShowComponent] = useState(false);

  return (
    <div>
      <button onClick={() => setShowComponent(true)}>
        Load Component
      </button>
      {showComponent && (
        <Suspense fallback={<div>Loading...</div>}>
          <ExpensiveComponent />
        </Suspense>
      )}
    </div>
  );
};
```

### 资源优化
```typescript
// vite.config.ts - Vite构建优化
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    // 代码分割
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          ui: ['antd', '@ant-design/icons'],
          utils: ['lodash', 'moment'],
        },
      },
    },

    // 压缩
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true, // 生产环境移除console
        drop_debugger: true,
      },
    },

    // 资源大小限制
    chunkSizeWarningLimit: 600,
  },

  // 预加载模块
  optimizeDeps: {
    include: ['react', 'react-dom', 'axios'],
  },
});

// 图片优化
const ImageComponent = ({ src, alt }: ImageProps) => {
  const [imageSrc, setImageSrc] = useState('');

  useEffect(() => {
    // 使用Intersection Observer实现懒加载
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            // 动态生成不同尺寸的图片
            const img = new Image();
            img.src = generateResponsiveImageUrl(src);
            img.onload = () => setImageSrc(img.src);
            observer.disconnect();
          }
        });
      }
    );

    const element = document.getElementById('image-container');
    if (element) observer.observe(element);

    return () => observer.disconnect();
  }, [src]);

  return <img src={imageSrc} alt={alt} loading="lazy" />;
};
```

## 监控与告警

### 性能监控
```python
from prometheus_client import Counter, Histogram, Gauge
import time

# 指标定义
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

DB_CONNECTION_POOL_USAGE = Gauge(
    'db_connection_pool_usage',
    'Database connection pool usage'
)

CACHE_HIT_RATE = Gauge(
    'cache_hit_rate',
    'Cache hit rate'
)

# 监控中间件
class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        try:
            response = await call_next(request)

            # 记录请求指标
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()

            # 记录延迟
            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(time.time() - start_time)

            # 检查性能预算
            if time.time() - start_time > PERFORMANCE_BUDGET["api_response_time"]["p95"]:
                logger.warning(f"Slow request: {request.url.path} took {time.time() - start_time:.2f}s")

            return response

        except Exception as e:
            # 记录错误
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=500
            ).inc()

            raise

# 数据库监控
async def monitor_database():
    """监控数据库性能"""
    while True:
        try:
            # 连接池使用率
            pool_usage = await get_connection_pool_usage()
            DB_CONNECTION_POOL_USAGE.set(pool_usage)

            # 慢查询检测
            slow_queries = await get_slow_queries()
            for query in slow_queries:
                logger.warning(f"Slow query detected: {query['sql']} took {query['duration']}ms")

        except Exception as e:
            logger.error(f"Database monitoring error: {e}")

        await asyncio.sleep(60)  # 每分钟检查一次
```

### 性能测试
```python
# tests/performance/test_api_performance.py
import pytest
import asyncio
import httpx
import time
from statistics import mean, median

class PerformanceTest:
    @pytest.mark.asyncio
    async def test_api_response_time(self):
        """测试API响应时间"""
        async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
            response_times = []

            # 发送100个并发请求
            tasks = []
            for _ in range(100):
                task = self._time_request(client, "/api/v1/posts")
                tasks.append(task)

            start_time = time.time()
            results = await asyncio.gather(*tasks)
            total_time = time.time() - start_time

            response_times = [r for r in results if r is not None]

            # 计算性能指标
            avg_response_time = mean(response_times)
            p95_response_time = sorted(response_times)[int(len(response_times) * 0.95)]
            p99_response_time = sorted(response_times)[int(len(response_times) * 0.99)]

            # 断言性能要求
            assert avg_response_time < 0.5  # 平均响应时间 < 500ms
            assert p95_response_time < 1.0  # 95%响应时间 < 1s
            assert p99_response_time < 2.0  # 99%响应时间 < 2s

            print(f"Performance test results:")
            print(f"  Requests: {len(response_times)}")
            print(f"  Average: {avg_response_time:.3f}s")
            print(f"  P95: {p95_response_time:.3f}s")
            print(f"  P99: {p99_response_time:.3f}s")
            print(f"  Total time: {total_time:.3f}s")

    async def _time_request(self, client: httpx.AsyncClient, url: str) -> float:
        """计时单个请求"""
        try:
            start_time = time.time()
            response = await client.get(url)
            response_time = time.time() - start_time

            assert response.status_code == 200
            return response_time

        except Exception as e:
            print(f"Request failed: {e}")
            return None
```

## 检查清单

### 性能预算检查
- [ ] 设定明确的性能目标和SLO
- [ ] 实施性能监控和告警
- [ ] 定期执行性能测试
- [ ] 监控第三方服务性能

### 后端优化检查
- [ ] 避免N+1查询问题
- [ ] 实施适当的缓存策略
- [ ] 使用异步编程优化并发
- [ ] 监控数据库连接池使用率

### 前端优化检查
- [ ] 实施代码分割和懒加载
- [ ] 优化图片和静态资源
- [ ] 使用memo避免不必要的重渲染
- [ ] 监控前端性能指标

### 监控告警检查
- [ ] 配置Prometheus指标收集
- [ ] 实施性能阈值告警
- [ ] 监控错误率和响应时间
- [ ] 建立性能回归测试

## 示例配置

### Nginx性能优化配置
```nginx
# nginx.conf
worker_processes auto;
worker_rlimit_nofile 65536;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    # 基础设置
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;

    # 缓存设置
    open_file_cache max=1000 inactive=20s;
    open_file_cache_valid 30s;
    open_file_cache_min_uses 2;
    open_file_cache_errors on;

    # Gzip压缩
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/javascript
        application/xml+rss
        application/json;

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API代理
    location /api/ {
        proxy_pass http://backend;
        proxy_buffering off;
        proxy_request_buffering off;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

## 相关文档
- [配置规范](10-Config-Standard.md) - 性能配置管理
- [API规范](30-API-Standard.md) - 接口性能要求
- [部署规范](50-Deployment-Standard.md) - 部署性能优化
- [可观测性规范](80-Observability-Standard.md) - 性能监控要求

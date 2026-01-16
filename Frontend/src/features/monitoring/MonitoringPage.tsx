/**
 * Monitoring Dashboard
 *
 * 企业级AI平台监控面板
 * 9大监控域：节点、GPU、模型服务、网关、任务队列、网络、成本、用户、安全
 */

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Server,
  Cpu,
  Bot,
  Network,
  ListTodo,
  Wifi,
  DollarSign,
  Key,
  Shield,
  X,
  RefreshCw,
  Clock,
  CheckCircle,
  AlertTriangle,
  XCircle,
  ChevronRight,
  Thermometer,
  Zap,
  HardDrive,
  MemoryStick,
  Activity,
  Users,
  Globe,
  Lock,
} from 'lucide-react'

// ============================================================================
// Types
// ============================================================================

interface MetricItem {
  label: string
  value: string | number
  unit?: string
  status?: 'ok' | 'warning' | 'critical'
  trend?: 'up' | 'down' | 'stable'
  sparkline?: number[]
}

interface DetailSection {
  title: string
  metrics: MetricItem[]
}

interface MonitoringDomain {
  id: string
  title: string
  description: string
  icon: React.ElementType
  status: 'ok' | 'warning' | 'critical' | 'unknown'
  summary: MetricItem[]
  details: DetailSection[]
}

// ============================================================================
// Mock Data - 模拟真实监控数据
// ============================================================================

const mockDomains: MonitoringDomain[] = [
  // 1. 机器节点监控（基础层）
  {
    id: 'nodes',
    title: '机器节点',
    description: '服务器运行状态和系统指标',
    icon: Server,
    status: 'ok',
    summary: [
      { label: '在线节点', value: '12/14', status: 'warning' },
      { label: 'CPU 均值', value: 45, unit: '%', status: 'ok' },
    ],
    details: [
      {
        title: '节点清单',
        metrics: [
          { label: '总节点数', value: 14 },
          { label: '在线节点', value: 12, status: 'ok' },
          { label: '离线节点', value: 2, status: 'warning' },
          { label: 'Master 节点', value: 2 },
          { label: 'Worker 节点', value: 12 },
        ],
      },
      {
        title: '系统指标',
        metrics: [
          { label: 'CPU 平均使用率', value: '45%', status: 'ok', sparkline: [30, 35, 42, 45, 48, 45, 42] },
          { label: '内存平均使用率', value: '62%', status: 'ok', sparkline: [55, 58, 60, 62, 64, 62, 61] },
          { label: '磁盘平均使用率', value: '38%', status: 'ok' },
          { label: 'Load Average', value: '2.4' },
        ],
      },
      {
        title: '存活状态',
        metrics: [
          { label: '最近重启', value: '3 天前' },
          { label: '心跳延迟', value: '< 1s', status: 'ok' },
          { label: '系统告警', value: 2, status: 'warning' },
        ],
      },
    ],
  },

  // 2. GPU资源监控（核心）
  {
    id: 'gpu',
    title: 'GPU 资源',
    description: 'GPU/NPU 设备状态和性能',
    icon: Cpu,
    status: 'ok',
    summary: [
      { label: 'GPU 数量', value: '32/32', status: 'ok' },
      { label: '平均温度', value: 68, unit: '°C', status: 'ok' },
    ],
    details: [
      {
        title: 'GPU 拓扑',
        metrics: [
          { label: '总 GPU 数', value: 32 },
          { label: 'A100 80GB', value: 16 },
          { label: 'H100 80GB', value: 8 },
          { label: 'RTX 4090', value: 8 },
          { label: 'NVLink 连接', value: '正常', status: 'ok' },
        ],
      },
      {
        title: '显存监控',
        metrics: [
          { label: '总显存', value: '2.56 TB' },
          { label: '已用显存', value: '1.8 TB' },
          { label: '显存占用率', value: '70%', status: 'ok', sparkline: [65, 68, 72, 70, 68, 70, 71] },
          { label: '显存带宽利用率', value: '45%' },
        ],
      },
      {
        title: '性能指标',
        metrics: [
          { label: '平均温度', value: '68°C', status: 'ok' },
          { label: '最高温度', value: '78°C', status: 'ok' },
          { label: '总功耗', value: '12.8 kW' },
          { label: 'CUDA 利用率', value: '82%' },
          { label: 'ECC 错误', value: 0, status: 'ok' },
        ],
      },
      {
        title: '调度情况',
        metrics: [
          { label: 'MIG 实例', value: 24 },
          { label: 'vGPU 分配', value: 48 },
          { label: 'GPU 任务队列', value: 12 },
        ],
      },
    ],
  },

  // 3. 模型服务监控（按节点）
  {
    id: 'models',
    title: '模型服务',
    description: '推理服务性能和负载',
    icon: Bot,
    status: 'ok',
    summary: [
      { label: '运行实例', value: 18, status: 'ok' },
      { label: 'P99 延迟', value: 1.2, unit: 's', status: 'ok' },
    ],
    details: [
      {
        title: '节点负载',
        metrics: [
          { label: '运行实例数', value: 18 },
          { label: '模型版本分布', value: '8 种' },
          { label: 'Batch Size 均值', value: 32 },
          { label: '冷启动次数 (24h)', value: 3 },
        ],
      },
      {
        title: '推理性能',
        metrics: [
          { label: 'P50 延迟', value: '320ms', status: 'ok' },
          { label: 'P99 延迟', value: '1.2s', status: 'ok', sparkline: [1.1, 1.2, 1.3, 1.2, 1.1, 1.2, 1.2] },
          { label: '吞吐量', value: '2.4k tok/s' },
          { label: 'TTFT', value: '180ms' },
          { label: '成功率', value: '99.8%', status: 'ok' },
        ],
      },
      {
        title: '资源占用',
        metrics: [
          { label: 'GPU 占用', value: '28/32' },
          { label: '显存隔离', value: '已启用', status: 'ok' },
          { label: 'CPU 亲和性', value: '已配置' },
        ],
      },
    ],
  },

  // 4. API网关监控（分布式）
  {
    id: 'gateway',
    title: 'API 网关',
    description: '流量统计和转发效率',
    icon: Network,
    status: 'ok',
    summary: [
      { label: 'QPS', value: 2560, status: 'ok' },
      { label: '错误率', value: '0.12%', status: 'ok' },
    ],
    details: [
      {
        title: '入口流量',
        metrics: [
          { label: '当前 QPS', value: '2,560', sparkline: [2400, 2500, 2600, 2560, 2480, 2520, 2560] },
          { label: '峰值 QPS (24h)', value: '4,200' },
          { label: '总请求数 (24h)', value: '12.8M' },
          { label: '负载均衡效果', value: '均匀', status: 'ok' },
        ],
      },
      {
        title: '转发效率',
        metrics: [
          { label: '平均延迟', value: '45ms', status: 'ok' },
          { label: 'P99 延迟', value: '120ms' },
          { label: '跨节点延迟', value: '8ms' },
          { label: '服务发现成功率', value: '100%', status: 'ok' },
        ],
      },
      {
        title: '错误分布',
        metrics: [
          { label: '错误率', value: '0.12%', status: 'ok' },
          { label: '5xx 错误', value: 156 },
          { label: '超时请求', value: 89 },
          { label: '熔断触发', value: 2 },
        ],
      },
    ],
  },

  // 5. 任务调度与队列监控
  {
    id: 'queue',
    title: '任务队列',
    description: '调度状态和任务生命周期',
    icon: ListTodo,
    status: 'ok',
    summary: [
      { label: '队列深度', value: 128, status: 'ok' },
      { label: '调度延迟', value: '< 1s', status: 'ok' },
    ],
    details: [
      {
        title: '任务队列',
        metrics: [
          { label: '待处理任务', value: 128, sparkline: [100, 110, 120, 128, 125, 130, 128] },
          { label: '平均排队时长', value: '2.3s' },
          { label: '推理任务', value: 98 },
          { label: '训练任务', value: 22 },
          { label: '微调任务', value: 8 },
        ],
      },
      {
        title: '调度器状态',
        metrics: [
          { label: '调度延迟', value: '< 1s', status: 'ok' },
          { label: '调度失败 (24h)', value: 3 },
          { label: '资源碎片化', value: '12%', status: 'ok' },
        ],
      },
      {
        title: '任务生命周期',
        metrics: [
          { label: '提交→完成 P50', value: '4.2s' },
          { label: '提交→完成 P99', value: '12.8s' },
          { label: '任务完成率', value: '99.6%', status: 'ok' },
        ],
      },
    ],
  },

  // 6. Network通信监控
  {
    id: 'network',
    title: '网络通信',
    description: '节点间网络和外部依赖',
    icon: Wifi,
    status: 'ok',
    summary: [
      { label: '带宽使用', value: '45%', status: 'ok' },
      { label: '重传率', value: '0.01%', status: 'ok' },
    ],
    details: [
      {
        title: '节点间网络',
        metrics: [
          { label: 'TCP 连接数', value: '12,480' },
          { label: '带宽占用', value: '45%', sparkline: [40, 42, 45, 48, 45, 43, 45] },
          { label: '重传率', value: '0.01%', status: 'ok' },
          { label: '平均延迟', value: '0.8ms' },
        ],
      },
      {
        title: '存储网络',
        metrics: [
          { label: 'NFS 读取', value: '2.4 GB/s' },
          { label: 'NFS 写入', value: '1.2 GB/s' },
          { label: 'IOPS', value: '45,000' },
          { label: '挂载状态', value: '正常', status: 'ok' },
        ],
      },
      {
        title: '外部依赖',
        metrics: [
          { label: 'HuggingFace', value: '可达', status: 'ok' },
          { label: 'ModelScope', value: '可达', status: 'ok' },
          { label: 'DNS 解析', value: '< 10ms', status: 'ok' },
        ],
      },
    ],
  },

  // 7. Token与成本监控（按节点）
  {
    id: 'cost',
    title: 'Token 与成本',
    description: '资源成本和预算追踪',
    icon: DollarSign,
    status: 'ok',
    summary: [
      { label: '本月支出', value: '$12,450', status: 'ok' },
      { label: '预算剩余', value: '58%', status: 'ok' },
    ],
    details: [
      {
        title: '节点成本核算',
        metrics: [
          { label: '本月支出', value: '$12,450' },
          { label: '预计月支出', value: '$18,200' },
          { label: '能耗成本', value: '$3,200' },
          { label: '云服务成本', value: '$9,250' },
        ],
      },
      {
        title: 'Token 用量',
        metrics: [
          { label: '输入 Token', value: '124M', sparkline: [100, 110, 120, 124, 118, 122, 124] },
          { label: '输出 Token', value: '89M' },
          { label: 'Token 成本', value: '$8,420' },
        ],
      },
      {
        title: '预算预警',
        metrics: [
          { label: '月预算', value: '$30,000' },
          { label: '已使用', value: '42%' },
          { label: '剩余预算', value: '$17,550', status: 'ok' },
          { label: '预算利用率', value: '正常', status: 'ok' },
        ],
      },
      {
        title: 'ROI 分析',
        metrics: [
          { label: '节点利用率', value: '78%' },
          { label: '闲置资源', value: '4 GPU' },
          { label: '成本效益', value: '优良', status: 'ok' },
        ],
      },
    ],
  },

  // 8. API-Key与用户监控
  {
    id: 'users',
    title: 'API-Key 与用户',
    description: '用户行为和访问分析',
    icon: Key,
    status: 'ok',
    summary: [
      { label: '活跃 Key', value: 156, status: 'ok' },
      { label: '今日调用', value: '2.4M', status: 'ok' },
    ],
    details: [
      {
        title: 'API Key 统计',
        metrics: [
          { label: '总 Key 数', value: 248 },
          { label: '活跃 Key', value: 156 },
          { label: '今日调用', value: '2.4M' },
          { label: '配额使用率', value: '45%' },
        ],
      },
      {
        title: '用户地理分布',
        metrics: [
          { label: '国内用户', value: '68%' },
          { label: '海外用户', value: '32%' },
          { label: 'Top 地区', value: '北京' },
        ],
      },
      {
        title: '租户隔离',
        metrics: [
          { label: '租户数', value: 12 },
          { label: 'QoS 保障', value: '已启用', status: 'ok' },
          { label: '资源隔离', value: '正常', status: 'ok' },
        ],
      },
    ],
  },

  // 9. 安全与风控
  {
    id: 'security',
    title: '安全与风控',
    description: '安全事件和威胁检测',
    icon: Shield,
    status: 'ok',
    summary: [
      { label: '安全评分', value: 95, status: 'ok' },
      { label: '威胁事件', value: 0, status: 'ok' },
    ],
    details: [
      {
        title: '节点安全',
        metrics: [
          { label: 'SSH 爆破尝试 (24h)', value: 128 },
          { label: '未授权访问', value: 0, status: 'ok' },
          { label: '封禁 IP 数', value: 23 },
        ],
      },
      {
        title: '数据安全',
        metrics: [
          { label: '模型完整性', value: '通过', status: 'ok' },
          { label: '日志脱敏', value: '已启用', status: 'ok' },
          { label: '合规检查', value: '通过', status: 'ok' },
        ],
      },
      {
        title: '物理安全',
        metrics: [
          { label: '机房温度', value: '22°C', status: 'ok' },
          { label: '机房湿度', value: '45%', status: 'ok' },
          { label: '供电状态', value: '正常', status: 'ok' },
          { label: 'UPS 电量', value: '100%' },
        ],
      },
    ],
  },
]

// ============================================================================
// Helper Functions
// ============================================================================

function getStatusColor(status?: string) {
  switch (status) {
    case 'ok': return 'text-emerald-600 dark:text-emerald-400'
    case 'warning': return 'text-amber-600 dark:text-amber-400'
    case 'critical': return 'text-red-600 dark:text-red-400'
    default: return 'text-stone-600 dark:text-stone-400'
  }
}

function getStatusBg(status: string) {
  switch (status) {
    case 'ok': return 'bg-emerald-500'
    case 'warning': return 'bg-amber-500'
    case 'critical': return 'bg-red-500'
    default: return 'bg-stone-400'
  }
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'ok': return CheckCircle
    case 'warning': return AlertTriangle
    case 'critical': return XCircle
    default: return Activity
  }
}

// Mini Sparkline Component
function Sparkline({ data, color = 'stroke-teal-500' }: { data: number[]; color?: string }) {
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const height = 20
  const width = 60
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((v - min) / range) * height
    return `${x},${y}`
  }).join(' ')

  return (
    <svg width={width} height={height} className="ml-2">
      <polyline
        points={points}
        fill="none"
        className={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// ============================================================================
// Detail Modal Component
// ============================================================================

function DetailModal({
  domain,
  onClose,
}: {
  domain: MonitoringDomain
  onClose: () => void
}) {
  const Icon = domain.icon
  const StatusIcon = getStatusIcon(domain.status)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-2xl max-h-[85vh] bg-white dark:bg-stone-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-900/50">
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-xl ${getStatusBg(domain.status)} bg-opacity-10`}>
              <Icon className={`w-6 h-6 ${getStatusColor(domain.status)}`} />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
                {domain.title}
              </h2>
              <p className="text-sm text-stone-500 dark:text-stone-400">
                {domain.description}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${getStatusBg(domain.status)} bg-opacity-10`}>
              <StatusIcon className={`w-4 h-4 ${getStatusColor(domain.status)}`} />
              <span className={getStatusColor(domain.status)}>
                {domain.status === 'ok' ? '正常' : domain.status === 'warning' ? '警告' : '严重'}
              </span>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-700 transition-colors"
            >
              <X className="w-5 h-5 text-stone-500" />
            </button>
          </div>
        </div>

        {/* Content - Scrollable */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {domain.details.map((section, idx) => (
            <div key={idx} className="space-y-3">
              <h3 className="text-sm font-semibold text-stone-700 dark:text-stone-300 uppercase tracking-wide">
                {section.title}
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {section.metrics.map((metric, mIdx) => (
                  <div
                    key={mIdx}
                    className="p-3 rounded-xl bg-stone-50 dark:bg-stone-900/50 border border-stone-100 dark:border-stone-700"
                  >
                    <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">
                      {metric.label}
                    </div>
                    <div className="flex items-center">
                      <span className={`text-lg font-semibold ${getStatusColor(metric.status)}`}>
                        {metric.value}
                        {metric.unit && <span className="text-sm ml-0.5">{metric.unit}</span>}
                      </span>
                      {metric.sparkline && (
                        <Sparkline data={metric.sparkline} />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center p-4 border-t border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-900/50">
          <span className="text-xs text-stone-400">
            数据每 15 秒自动刷新
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-stone-700 dark:text-stone-300 hover:bg-stone-200 dark:hover:bg-stone-700 rounded-lg transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  )
}

// ============================================================================
// Main Monitoring Page Component
// ============================================================================

export function MonitoringPage() {
  const { t } = useTranslation()
  const [domains] = useState<MonitoringDomain[]>(mockDomains)
  const [selectedDomain, setSelectedDomain] = useState<MonitoringDomain | null>(null)
  const [loading, setLoading] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date())

  const handleRefresh = async () => {
    setLoading(true)
    await new Promise((resolve) => setTimeout(resolve, 800))
    setLastUpdated(new Date())
    setLoading(false)
  }

  // Auto refresh
  useEffect(() => {
    const interval = setInterval(() => {
      setLastUpdated(new Date())
    }, 15000)
    return () => clearInterval(interval)
  }, [])

  // Overall status
  const criticalCount = domains.filter(d => d.status === 'critical').length
  const warningCount = domains.filter(d => d.status === 'warning').length
  const overallStatus = criticalCount > 0 ? 'critical' : warningCount > 0 ? 'warning' : 'ok'

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header - Fixed */}
      <div className="flex-shrink-0 flex items-center justify-between pb-4">
        <div>
          <h1 className="text-xl font-semibold text-stone-900 dark:text-stone-100">
            监控面板
          </h1>
          <p className="text-sm text-stone-500 dark:text-stone-400">
            实时监控集群资源、模型服务和系统健康状态
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Overall status */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${getStatusBg(overallStatus)} bg-opacity-10`}>
            {overallStatus === 'ok' ? (
              <CheckCircle className="w-4 h-4 text-emerald-500" />
            ) : overallStatus === 'warning' ? (
              <AlertTriangle className="w-4 h-4 text-amber-500" />
            ) : (
              <XCircle className="w-4 h-4 text-red-500" />
            )}
            <span className={`text-sm font-medium ${getStatusColor(overallStatus)}`}>
              {overallStatus === 'ok' ? '系统正常' : overallStatus === 'warning' ? `${warningCount} 个警告` : `${criticalCount} 个严重`}
            </span>
          </div>

          {/* Last updated */}
          <span className="text-xs text-stone-400 dark:text-stone-500 flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            {lastUpdated.toLocaleTimeString()}
          </span>

          {/* Refresh button */}
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-stone-700 dark:text-stone-300 bg-stone-100 dark:bg-stone-800 hover:bg-stone-200 dark:hover:bg-stone-700 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>
      </div>

      {/* Cards Grid - 3x3 layout, fills remaining space */}
      <div className="flex-1 min-h-0 grid grid-cols-3 grid-rows-3 gap-3">
        {domains.map((domain) => {
          const Icon = domain.icon
          const StatusIcon = getStatusIcon(domain.status)

          return (
            <button
              key={domain.id}
              onClick={() => setSelectedDomain(domain)}
              className="group text-left p-4 bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 hover:border-teal-400 dark:hover:border-teal-500 hover:shadow-lg transition-all duration-200 flex flex-col overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="flex-shrink-0 p-2 rounded-lg bg-stone-100 dark:bg-stone-700 group-hover:bg-teal-50 dark:group-hover:bg-teal-900/30 transition-colors">
                    <Icon className="w-4 h-4 text-stone-600 dark:text-stone-300 group-hover:text-teal-600 dark:group-hover:text-teal-400 transition-colors" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="font-semibold text-sm text-stone-900 dark:text-stone-100 truncate">
                      {domain.title}
                    </h3>
                    <p className="text-xs text-stone-500 dark:text-stone-400 truncate">
                      {domain.description}
                    </p>
                  </div>
                </div>
                {/* Status indicator */}
                <div className={`flex-shrink-0 flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-medium ${getStatusBg(domain.status)} bg-opacity-10`}>
                  <StatusIcon className={`w-3 h-3 ${getStatusColor(domain.status)}`} />
                </div>
              </div>

              {/* Summary Metrics */}
              <div className="flex-1 grid grid-cols-2 gap-2 min-h-0">
                {domain.summary.map((metric, idx) => (
                  <div key={idx} className="p-2 rounded-lg bg-stone-50 dark:bg-stone-900/50 flex flex-col justify-center">
                    <div className="text-xs text-stone-500 dark:text-stone-400 truncate">
                      {metric.label}
                    </div>
                    <div className={`text-base font-semibold ${getStatusColor(metric.status)} truncate`}>
                      {metric.value}
                      {metric.unit && <span className="text-xs ml-0.5">{metric.unit}</span>}
                    </div>
                  </div>
                ))}
              </div>

              {/* View details hint */}
              <div className="flex-shrink-0 mt-2 flex items-center justify-end text-xs text-stone-400 group-hover:text-teal-500 transition-colors">
                <span>查看详情</span>
                <ChevronRight className="w-3 h-3 ml-0.5 group-hover:translate-x-0.5 transition-transform" />
              </div>
            </button>
          )
        })}
      </div>

      {/* Detail Modal */}
      {selectedDomain && (
        <DetailModal
          domain={selectedDomain}
          onClose={() => setSelectedDomain(null)}
        />
      )}
    </div>
  )
}

import { useNavigate } from 'react-router-dom'
import { Monitor, Server, ShoppingBag, Rocket, GitBranch, MessageSquare, Shield, Settings } from 'lucide-react'

const DashboardPage = () => {
  const navigate = useNavigate()

  const quickActions = [
    {
      id: 'monitoring',
      title: '监控面板',
      description: '查看系统运行状态和性能指标',
      icon: Monitor,
      path: '/dashboard/monitoring',
    },
    {
      id: 'nodes',
      title: '节点管理',
      description: '管理计算节点和资源分配',
      icon: Server,
      path: '/dashboard/nodes',
    },
    {
      id: 'market',
      title: '模型市场',
      description: '浏览和获取各种 AI 模型',
      icon: ShoppingBag,
      path: '/dashboard/market',
    },
    {
      id: 'deployment',
      title: '模型部署',
      description: '部署和管理 AI 模型服务',
      icon: Rocket,
      path: '/dashboard/deployment',
    },
    {
      id: 'forwarding',
      title: '模型转发',
      description: '配置模型请求转发规则',
      icon: GitBranch,
      path: '/dashboard/forwarding',
    },
    {
      id: 'chat',
      title: '聊天',
      description: '与 AI 模型进行对话交互',
      icon: MessageSquare,
      path: '/dashboard/chat',
    },
    {
      id: 'permissions',
      title: '权限管理',
      description: '管理用户和访问权限',
      icon: Shield,
      path: '/dashboard/permissions',
    },
    {
      id: 'settings',
      title: '设置',
      description: '系统配置和个性化设置',
      icon: Settings,
      path: '/dashboard/settings',
    },
  ]

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div className="border-b border-stone-200 dark:border-stone-700 pb-6">
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">
          欢迎使用 Noveris AI
        </h1>
        <p className="mt-1 text-stone-500 dark:text-stone-400">
          选择一个功能模块开始使用
        </p>
      </div>

      {/* Quick Actions Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {quickActions.map((action) => {
          const Icon = action.icon
          return (
            <button
              key={action.id}
              onClick={() => navigate(action.path)}
              className="group flex items-start gap-4 p-4 bg-white dark:bg-stone-800/80 rounded-lg border border-stone-200 dark:border-stone-700 text-left transition-all duration-150 hover:border-stone-300 dark:hover:border-stone-500 hover:shadow-sm dark:hover:shadow-md dark:hover:bg-stone-750"
            >
              {/* Icon */}
              <div className="flex-shrink-0 p-2 bg-stone-100 dark:bg-stone-700/50 rounded-md group-hover:bg-stone-200 dark:group-hover:bg-stone-600 transition-colors">
                <Icon className="w-5 h-5 text-stone-600 dark:text-stone-300" />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-medium text-stone-900 dark:text-white group-hover:text-stone-700 dark:group-hover:text-white transition-colors">
                  {action.title}
                </h3>
                <p className="mt-0.5 text-xs text-stone-500 dark:text-stone-400 line-clamp-2">
                  {action.description}
                </p>
              </div>
            </button>
          )
        })}
      </div>

      {/* Quick Start Section */}
      <div className="bg-stone-50 dark:bg-stone-800/60 rounded-lg p-6 border border-stone-200 dark:border-stone-700">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-medium text-stone-900 dark:text-white">
              快速开始
            </h2>
            <p className="mt-1 text-xs text-stone-500 dark:text-stone-400">
              了解如何使用 Noveris AI 平台快速部署和管理您的 AI 模型
            </p>
          </div>
          <button
            onClick={() => navigate('/dashboard/Docs')}
            className="px-4 py-2 text-sm font-medium text-stone-700 dark:text-stone-200 bg-white dark:bg-stone-700 border border-stone-300 dark:border-stone-600 rounded-md hover:bg-stone-50 dark:hover:bg-stone-600 transition-colors"
          >
            查看文档
          </button>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage

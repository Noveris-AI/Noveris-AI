const DocsPage = () => {
  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-white">
          功能使用文档
        </h1>
        <p className="mt-2 text-stone-500 dark:text-stone-400">
          了解如何使用 Noveris AI 平台的各项功能
        </p>
      </div>

      <div className="space-y-6">
        {/* Monitoring */}
        <div className="bg-white dark:bg-stone-800/80 rounded-lg border border-stone-200 dark:border-stone-700 p-6">
          <h2 className="text-lg font-medium text-stone-900 dark:text-white mb-2">监控面板</h2>
          <p className="text-stone-600 dark:text-stone-400 text-sm">查看系统运行状态和性能指标</p>
        </div>

        {/* Nodes */}
        <div className="bg-white dark:bg-stone-800/80 rounded-lg border border-stone-200 dark:border-stone-700 p-6">
          <h2 className="text-lg font-medium text-stone-900 dark:text-white mb-2">节点管理</h2>
          <p className="text-stone-600 dark:text-stone-400 text-sm">管理计算节点和资源分配</p>
        </div>

        {/* Model Market */}
        <div className="bg-white dark:bg-stone-800/80 rounded-lg border border-stone-200 dark:border-stone-700 p-6">
          <h2 className="text-lg font-medium text-stone-900 dark:text-white mb-2">模型市场</h2>
          <p className="text-stone-600 dark:text-stone-400 text-sm">浏览和获取各种 AI 模型</p>
        </div>

        {/* Deployment */}
        <div className="bg-white dark:bg-stone-800/80 rounded-lg border border-stone-200 dark:border-stone-700 p-6">
          <h2 className="text-lg font-medium text-stone-900 dark:text-white mb-2">模型部署</h2>
          <p className="text-stone-600 dark:text-stone-400 text-sm">部署和管理 AI 模型服务</p>
        </div>

        {/* Forwarding */}
        <div className="bg-white dark:bg-stone-800/80 rounded-lg border border-stone-200 dark:border-stone-700 p-6">
          <h2 className="text-lg font-medium text-stone-900 dark:text-white mb-2">模型转发</h2>
          <p className="text-stone-600 dark:text-stone-400 text-sm">配置模型请求转发规则</p>
        </div>

        {/* Chat */}
        <div className="bg-white dark:bg-stone-800/80 rounded-lg border border-stone-200 dark:border-stone-700 p-6">
          <h2 className="text-lg font-medium text-stone-900 dark:text-white mb-2">聊天</h2>
          <p className="text-stone-600 dark:text-stone-400 text-sm">与 AI 模型进行对话交互</p>
        </div>

        {/* Permissions */}
        <div className="bg-white dark:bg-stone-800/80 rounded-lg border border-stone-200 dark:border-stone-700 p-6">
          <h2 className="text-lg font-medium text-stone-900 dark:text-white mb-2">权限管理</h2>
          <p className="text-stone-600 dark:text-stone-400 text-sm">管理用户和访问权限</p>
        </div>

        {/* Settings */}
        <div className="bg-white dark:bg-stone-800/80 rounded-lg border border-stone-200 dark:border-stone-700 p-6">
          <h2 className="text-lg font-medium text-stone-900 dark:text-white mb-2">设置</h2>
          <p className="text-stone-600 dark:text-stone-400 text-sm">系统配置和个性化设置</p>
        </div>
      </div>
    </div>
  )
}

export default DocsPage

import { useTranslation } from 'react-i18next'

export const AuthIllustration = () => {
  const { t } = useTranslation()

  return (
    <div className="h-full flex flex-col space-y-4">
      {/* 顶部大框 - 平台主叙事 */}
      <div className="text-center space-y-2 flex-shrink-0">
        <h1 className="text-xl lg:text-2xl font-bold text-stone-900 dark:text-stone-100 leading-tight">
          {t('auth.left.headline')}
        </h1>
        <p className="text-sm text-stone-600 dark:text-stone-400 leading-relaxed">
          {t('auth.left.description')}
        </p>
      </div>

      {/* 企业级 SVG 插图 - 治理平台架构图 */}
      <div className="relative flex items-center justify-center flex-shrink-0">
        <svg
          viewBox="0 0 400 200"
          className="w-full h-32"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* 渐变定义 */}
          <defs>
            <linearGradient id="platformGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="currentColor" className="text-stone-300 dark:text-stone-600" />
              <stop offset="50%" stopColor="currentColor" className="text-stone-400 dark:text-stone-500" />
              <stop offset="100%" stopColor="currentColor" className="text-stone-500 dark:text-stone-400" />
            </linearGradient>
            <linearGradient id="accentGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="currentColor" className="text-teal-400 dark:text-teal-500" />
              <stop offset="100%" stopColor="currentColor" className="text-teal-500 dark:text-teal-400" />
            </linearGradient>
          </defs>

          {/* 中央平台架构图 */}
          <g transform="translate(200, 100)">
            {/* 中心节点 - 治理平台 */}
            <circle cx="0" cy="0" r="25" fill="url(#accentGradient)" opacity="0.8" />
            <circle cx="0" cy="0" r="20" fill="url(#platformGradient)" opacity="0.9" />
            <text x="0" y="4" textAnchor="middle" className="fill-stone-800 dark:fill-stone-200 text-xs font-medium">
              治理平台
            </text>

            {/* 四个方向的连接线和模块 */}
            {/* 上方 - 可观测性 */}
            <line x1="0" y1="-25" x2="0" y2="-60" stroke="url(#accentGradient)" strokeWidth="2" opacity="0.6" />
            <circle cx="0" cy="-70" r="12" fill="url(#platformGradient)" opacity="0.7" />
            <text x="0" y="-66" textAnchor="middle" className="fill-stone-700 dark:fill-stone-300 text-xs">
              监控
            </text>

            {/* 右方 - 模型部署 */}
            <line x1="25" y1="0" x2="60" y2="0" stroke="url(#accentGradient)" strokeWidth="2" opacity="0.6" />
            <circle cx="70" cy="0" r="12" fill="url(#platformGradient)" opacity="0.7" />
            <text x="70" y="4" textAnchor="middle" className="fill-stone-700 dark:fill-stone-300 text-xs">
              部署
            </text>

            {/* 下方 - 模型网关 */}
            <line x1="0" y1="25" x2="0" y2="60" stroke="url(#accentGradient)" strokeWidth="2" opacity="0.6" />
            <circle cx="0" cy="70" r="12" fill="url(#platformGradient)" opacity="0.7" />
            <text x="0" y="74" textAnchor="middle" className="fill-stone-700 dark:fill-stone-300 text-xs">
              网关
            </text>

            {/* 左方 - 企业身份 */}
            <line x1="-25" y1="0" x2="-60" y2="0" stroke="url(#accentGradient)" strokeWidth="2" opacity="0.6" />
            <circle cx="-70" cy="0" r="12" fill="url(#platformGradient)" opacity="0.7" />
            <text x="-70" y="4" textAnchor="middle" className="fill-stone-700 dark:fill-stone-300 text-xs">
              身份
            </text>
          </g>

          {/* 背景网格 - 企业级科技感 */}
          <g opacity="0.1" stroke="currentColor" className="text-stone-400 dark:text-stone-500" strokeWidth="0.5">
            <defs>
              <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="currentColor" strokeWidth="0.5"/>
              </pattern>
            </defs>
            <rect width="400" height="200" fill="url(#grid)" />
          </g>

          {/* 装饰性数据流线条 */}
          <g opacity="0.4" stroke="url(#accentGradient)" strokeWidth="1.5" fill="none">
            <path d="M20,40 Q100,20 180,50" strokeDasharray="5,5" />
            <path d="M380,60 Q300,40 220,70" strokeDasharray="5,5" />
            <path d="M50,160 Q150,140 250,170" strokeDasharray="5,5" />
            <path d="M350,140 Q250,120 150,150" strokeDasharray="5,5" />
          </g>
        </svg>
      </div>

      {/* 下方四个能力框 - 四宫格布局 */}
      <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-3 min-h-0">
        {/* 1. 可观测性与成本监控 */}
        <div className="bg-stone-100/50 dark:bg-stone-700/50 p-3 rounded-lg border-0 flex flex-col">
          <h3 className="text-xs font-semibold text-stone-900 dark:text-stone-100 mb-1 flex-shrink-0">
            {t('auth.left.capabilities.observability.title')}
          </h3>
          <p className="text-xs text-stone-600 dark:text-stone-400 leading-tight flex-1">
            {t('auth.left.capabilities.observability.desc')}
          </p>
        </div>

        {/* 2. 模型部署与发布管理 */}
        <div className="bg-stone-100/50 dark:bg-stone-700/50 p-3 rounded-lg border-0 flex flex-col">
          <h3 className="text-xs font-semibold text-stone-900 dark:text-stone-100 mb-1 flex-shrink-0">
            {t('auth.left.capabilities.deployment.title')}
          </h3>
          <p className="text-xs text-stone-600 dark:text-stone-400 leading-tight flex-1">
            {t('auth.left.capabilities.deployment.desc')}
          </p>
        </div>

        {/* 3. 模型网关与智能路由 */}
        <div className="bg-stone-100/50 dark:bg-stone-700/50 p-3 rounded-lg border-0 flex flex-col">
          <h3 className="text-xs font-semibold text-stone-900 dark:text-stone-100 mb-1 flex-shrink-0">
            {t('auth.left.capabilities.gateway.title')}
          </h3>
          <p className="text-xs text-stone-600 dark:text-stone-400 leading-tight flex-1">
            {t('auth.left.capabilities.gateway.desc')}
          </p>
        </div>

        {/* 4. 企业身份与 SSO 配置 */}
        <div className="bg-stone-100/50 dark:bg-stone-700/50 p-3 rounded-lg border-0 flex flex-col">
          <h3 className="text-xs font-semibold text-stone-900 dark:text-stone-100 mb-1 flex-shrink-0">
            {t('auth.left.capabilities.identity.title')}
          </h3>
          <p className="text-xs text-stone-600 dark:text-stone-400 leading-tight flex-1">
            {t('auth.left.capabilities.identity.desc')}
          </p>
        </div>
      </div>
    </div>
  )
}

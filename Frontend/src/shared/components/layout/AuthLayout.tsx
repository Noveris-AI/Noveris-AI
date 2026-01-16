import { Outlet } from 'react-router-dom'
import { BrandMark } from '../branding/BrandMark'
import { ThemeToggle } from '../theme/ThemeToggle'
import { LanguageToggle } from '../i18n/LanguageToggle'
import { AuthIllustration } from './AuthIllustration'

const AuthLayout = () => {
  return (
    <div className="h-screen flex flex-col relative overflow-hidden">
      {/* 底层背景 - 代码生成氛围感 */}
      <div className="absolute inset-0 bg-gradient-to-br from-stone-50 via-stone-50 to-stone-100 dark:from-stone-950 dark:via-stone-950 dark:to-stone-900">
        {/* 渐变叠加 */}
        <div className="absolute inset-0 bg-gradient-to-r from-teal-500/5 via-transparent to-stone-500/5" />

        {/* 噪点纹理 */}
        <div
          className="absolute inset-0 opacity-[0.015]"
          style={{
            backgroundImage: `radial-gradient(circle at 25% 25%, #14b8a6 1px, transparent 1px),
                            radial-gradient(circle at 75% 75%, #0a0a0a 1px, transparent 1px)`,
            backgroundSize: '40px 40px'
          }}
        />

        {/* 模糊光斑 */}
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-teal-400/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-stone-400/10 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-teal-500/5 rounded-full blur-2xl" />
      </div>

      {/* 顶栏 */}
      <header className="relative z-50 flex justify-between items-center px-6 py-4 lg:px-8 flex-shrink-0">
        {/* 左上角品牌 */}
        <BrandMark />

        {/* 右上角控制 */}
        <div className="flex items-center space-x-2">
          <LanguageToggle />
          <ThemeToggle />
        </div>
      </header>

      {/* 主内容区 - 悬浮中框，两层结构 */}
      <main className="relative z-10 flex-1 flex items-center justify-center px-4 py-4">
        <div className="w-full max-w-[1100px] mx-auto">
          <div className="bg-stone-100/80 dark:bg-stone-800/80 backdrop-blur-sm rounded-2xl shadow-2xl border-0 overflow-hidden">
            <div className="grid lg:grid-cols-2 gap-0 h-[600px]">
              {/* 左侧插图区 - 全生命周期治理平台表达 */}
              <div className="hidden lg:block order-2 lg:order-1 bg-stone-200/50 dark:bg-stone-700/50 p-8 lg:p-12 overflow-y-auto">
                <AuthIllustration />
              </div>

              {/* 右侧表单区 - 唯一允许卡片感的区域 */}
              <div className="order-1 lg:order-2 bg-stone-50 dark:bg-stone-900 p-7 flex flex-col justify-center overflow-visible">
                <div className="w-full max-w-[520px] mx-auto flex flex-col min-h-0">
                  <Outlet /> {/* Renders the specific auth page (Login, Register, etc.) */}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default AuthLayout

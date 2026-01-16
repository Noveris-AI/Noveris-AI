import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class', // 使用class策略
  theme: {
    extend: {
      colors: {
        // 严格按照60-30-10法则和Teal & Stone配色方案
        // 主色（60%）：Stone系列作为整体背景基调
        'stone-50': '#fafaf9',
        'stone-100': '#f5f5f4',
        'stone-200': '#e7e5e4',
        'stone-900': '#1c1917',
        'stone-950': '#0a0a0a',

        // 次色（30%）：用于卡片填充、分区、次级文字
        'stone-800': '#292524',

        // 强调色（10%）：Teal系列用于按钮/链接/焦点态/关键操作
        'teal-400': '#2dd4bf',
        'teal-500': '#14b8a6',

        // 语义化颜色
        'success': 'var(--color-success)',
        'warning': 'var(--color-warning)',
        'error': 'var(--color-error)',
        'info': 'var(--color-info)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-in': 'slideIn 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        },
      },
    },
  },
  plugins: [],
}

export default config

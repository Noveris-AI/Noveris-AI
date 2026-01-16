export interface MenuItem {
  id: string
  label: string
  labelKey: string
  icon: string
  path: string
  badge?: number
}

export interface Notification {
  id: string
  title: string
  message: string
  time: string
  read: boolean
  type: 'info' | 'warning' | 'error' | 'success'
}

export interface User {
  id: string
  name: string
  email: string
  avatar?: string
  role: string
}

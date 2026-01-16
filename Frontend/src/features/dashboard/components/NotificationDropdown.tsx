import { useState } from 'react'
import { Notification } from '../types'
import { cn } from '@/shared/lib/utils'

interface NotificationDropdownProps {
  notifications: Notification[]
  onMarkRead?: (id: string) => void
  onMarkAllRead?: () => void
}

const InfoIcon = () => (
  <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)

const WarningIcon = () => (
  <svg className="w-5 h-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
  </svg>
)

const ErrorIcon = () => (
  <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)

const SuccessIcon = () => (
  <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)

const getTypeIcon = (type: Notification['type']) => {
  switch (type) {
    case 'info': return <InfoIcon />
    case 'warning': return <WarningIcon />
    case 'error': return <ErrorIcon />
    case 'success': return <SuccessIcon />
  }
}

export const NotificationDropdown = ({
  notifications = [],
  onMarkRead,
  onMarkAllRead
}: NotificationDropdownProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const unreadCount = notifications.filter(n => !n.read).length

  const handleMarkRead = (id: string) => {
    onMarkRead?.(id)
  }

  return (
    <div className="relative">
      {/* Notification button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors duration-200 focus-ring"
        aria-label="通知"
      >
        <svg className="w-5 h-5 text-stone-600 dark:text-stone-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>

        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 w-5 h-5 bg-red-500 text-white text-xs font-medium rounded-full flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-[55]"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-2 w-80 bg-white dark:bg-stone-900 rounded-xl shadow-lg border border-stone-200 dark:border-stone-700 z-[60] overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-stone-200 dark:border-stone-700">
              <h3 className="text-sm font-semibold text-stone-900 dark:text-stone-100">通知</h3>
              {unreadCount > 0 && (
                <button
                  onClick={() => {
                    onMarkAllRead?.()
                    setIsOpen(false)
                  }}
                  className="text-xs text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 font-medium"
                >
                  全部已读
                </button>
              )}
            </div>

            {/* Notification list */}
            <div className="max-h-80 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="px-4 py-8 text-center text-stone-500 dark:text-stone-400 text-sm">
                  暂无通知
                </div>
              ) : (
                notifications.map((notification) => (
                  <div
                    key={notification.id}
                    className={cn(
                      'flex items-start gap-3 px-4 py-3 hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors duration-150 border-b border-stone-100 dark:border-stone-800 last:border-b-0',
                      !notification.read && 'bg-teal-50/50 dark:bg-teal-950/20'
                    )}
                  >
                    <div className="flex-shrink-0 mt-0.5">{getTypeIcon(notification.type)}</div>
                    <div className="flex-1 min-w-0">
                      <p className={cn(
                        'text-sm font-medium text-stone-900 dark:text-stone-100',
                        !notification.read && 'font-semibold'
                      )}>
                        {notification.title}
                      </p>
                      <p className="text-sm text-stone-600 dark:text-stone-400 truncate">
                        {notification.message}
                      </p>
                      <p className="text-xs text-stone-500 dark:text-stone-500 mt-1">
                        {notification.time}
                      </p>
                    </div>
                    {!notification.read && (
                      <button
                        onClick={() => handleMarkRead(notification.id)}
                        className="flex-shrink-0 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300"
                      >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                        </svg>
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>

            {/* Footer */}
            <div className="px-4 py-2 border-t border-stone-200 dark:border-stone-700">
              <button
                onClick={() => setIsOpen(false)}
                className="w-full text-center text-sm text-teal-600 hover:text-teal-700 dark:text-teal-400 dark:hover:text-teal-300 font-medium py-1"
              >
                查看全部通知
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

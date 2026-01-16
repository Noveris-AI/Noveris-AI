/**
 * Environment Variable Table Component
 *
 * Provides a dynamic table for editing environment variables with support
 * for sensitive values (masked input).
 */

import { useState } from 'react'
import type { EnvTableEntry } from '../api/deploymentTypes'

interface EnvTableProps {
  entries: EnvTableEntry[]
  onChange: (entries: EnvTableEntry[]) => void
  readOnly?: boolean
}

export function EnvTable({ entries, onChange, readOnly = false }: EnvTableProps) {
  const handleAdd = () => {
    onChange([
      ...entries,
      { name: '', value: '', is_sensitive: false }
    ])
  }

  const handleRemove = (index: number) => {
    const newEntries = entries.filter((_, i) => i !== index)
    onChange(newEntries)
  }

  const handleChange = (index: number, field: keyof EnvTableEntry, value: string | boolean) => {
    const newEntries = [...entries]
    newEntries[index] = { ...newEntries[index], [field]: value }
    onChange(newEntries)
  }

  return (
    <div className="space-y-2">
      {/* Header */}
      {entries.length > 0 && (
        <div className="grid grid-cols-12 gap-2 text-xs font-medium text-stone-500 dark:text-stone-400 px-2">
          <div className="col-span-4">变量名</div>
          <div className="col-span-5">值</div>
          <div className="col-span-2">敏感</div>
          <div className="col-span-1"></div>
        </div>
      )}

      {/* Entries */}
      {entries.map((entry, index) => (
        <div key={index} className="grid grid-cols-12 gap-2 items-center">
          <input
            type="text"
            value={entry.name}
            onChange={(e) => handleChange(index, 'name', e.target.value)}
            placeholder="ENV_VAR_NAME"
            disabled={readOnly}
            className="col-span-4 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed"
          />
          <input
            type={entry.is_sensitive ? 'password' : 'text'}
            value={entry.value}
            onChange={(e) => handleChange(index, 'value', e.target.value)}
            placeholder={entry.is_sensitive ? '••••••••' : '值'}
            disabled={readOnly}
            className="col-span-5 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed"
          />
          <div className="col-span-2 flex items-center justify-center">
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={entry.is_sensitive}
                onChange={(e) => handleChange(index, 'is_sensitive', e.target.checked)}
                disabled={readOnly}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-stone-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-teal-500 dark:peer-focus:ring-teal-600 rounded-full peer dark:bg-stone-600 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-stone-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-stone-600 peer-checked:bg-teal-600 peer-disabled:opacity-60"></div>
            </label>
          </div>
          <div className="col-span-1 flex justify-center">
            {!readOnly && (
              <button
                type="button"
                onClick={() => handleRemove(index)}
                className="p-1.5 text-stone-400 hover:text-red-500 transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            )}
          </div>
        </div>
      ))}

      {/* Empty State */}
      {entries.length === 0 && (
        <div className="text-center py-4 text-sm text-stone-400 dark:text-stone-500">
          暂无环境变量
        </div>
      )}

      {/* Add Button */}
      {!readOnly && (
        <button
          type="button"
          onClick={handleAdd}
          className="w-full px-3 py-2 border border-dashed border-stone-300 dark:border-stone-600 rounded-lg text-sm text-stone-500 dark:text-stone-400 hover:border-teal-500 hover:text-teal-600 dark:hover:text-teal-400 transition-colors flex items-center justify-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          添加环境变量
        </button>
      )}
    </div>
  )
}

// Compact display mode for read-only viewing
interface EnvTableDisplayProps {
  entries: EnvTableEntry[]
}

export function EnvTableDisplay({ entries }: EnvTableDisplayProps) {
  if (entries.length === 0) {
    return <span className="text-stone-400 text-sm">无</span>
  }

  return (
    <div className="space-y-1">
      {entries.map((entry, index) => (
        <div key={index} className="flex items-center gap-2 text-sm font-mono">
          <span className="text-stone-600 dark:text-stone-400">{entry.name}</span>
          <span className="text-stone-400">=</span>
          <span className="text-stone-900 dark:text-stone-100">
            {entry.is_sensitive ? '••••••••' : entry.value || '(empty)'}
          </span>
          {entry.is_sensitive && (
            <svg className="w-3.5 h-3.5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          )}
        </div>
      ))}
    </div>
  )
}

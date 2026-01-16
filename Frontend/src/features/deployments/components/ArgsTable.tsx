/**
 * CLI Arguments Table Component
 *
 * Provides a dynamic table for editing CLI arguments with support
 * for different value types and enable/disable toggles.
 */

import type { ArgsTableEntry } from '../api/deploymentTypes'

interface ArgsTableProps {
  entries: ArgsTableEntry[]
  onChange: (entries: ArgsTableEntry[]) => void
  readOnly?: boolean
}

const argTypes = [
  { value: 'string', label: '字符串' },
  { value: 'int', label: '整数' },
  { value: 'float', label: '浮点数' },
  { value: 'bool', label: '布尔值' },
  { value: 'json', label: 'JSON' },
] as const

export function ArgsTable({ entries, onChange, readOnly = false }: ArgsTableProps) {
  const handleAdd = () => {
    onChange([
      ...entries,
      { key: '', value: '', arg_type: 'string', enabled: true }
    ])
  }

  const handleRemove = (index: number) => {
    const newEntries = entries.filter((_, i) => i !== index)
    onChange(newEntries)
  }

  const handleChange = (index: number, field: keyof ArgsTableEntry, value: string | boolean) => {
    const newEntries = [...entries]
    newEntries[index] = { ...newEntries[index], [field]: value }
    onChange(newEntries)
  }

  return (
    <div className="space-y-2">
      {/* Header */}
      {entries.length > 0 && (
        <div className="grid grid-cols-12 gap-2 text-xs font-medium text-stone-500 dark:text-stone-400 px-2">
          <div className="col-span-1">启用</div>
          <div className="col-span-3">参数名</div>
          <div className="col-span-4">值</div>
          <div className="col-span-3">类型</div>
          <div className="col-span-1"></div>
        </div>
      )}

      {/* Entries */}
      {entries.map((entry, index) => (
        <div key={index} className="grid grid-cols-12 gap-2 items-center">
          {/* Enable Toggle */}
          <div className="col-span-1 flex items-center justify-center">
            <input
              type="checkbox"
              checked={entry.enabled}
              onChange={(e) => handleChange(index, 'enabled', e.target.checked)}
              disabled={readOnly}
              className="w-4 h-4 text-teal-600 bg-stone-100 border-stone-300 rounded focus:ring-teal-500 dark:focus:ring-teal-600 dark:bg-stone-700 dark:border-stone-600 disabled:opacity-60"
            />
          </div>

          {/* Key */}
          <input
            type="text"
            value={entry.key}
            onChange={(e) => handleChange(index, 'key', e.target.value)}
            placeholder="--arg-name"
            disabled={readOnly}
            className={`col-span-3 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed ${
              !entry.enabled ? 'opacity-50' : ''
            }`}
          />

          {/* Value */}
          <input
            type={entry.arg_type === 'int' || entry.arg_type === 'float' ? 'number' : 'text'}
            value={entry.value}
            onChange={(e) => handleChange(index, 'value', e.target.value)}
            placeholder={entry.arg_type === 'bool' ? 'true/false' : '值'}
            disabled={readOnly}
            step={entry.arg_type === 'float' ? 'any' : undefined}
            className={`col-span-4 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed ${
              !entry.enabled ? 'opacity-50' : ''
            }`}
          />

          {/* Type Selector */}
          <select
            value={entry.arg_type}
            onChange={(e) => handleChange(index, 'arg_type', e.target.value)}
            disabled={readOnly}
            className={`col-span-3 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed ${
              !entry.enabled ? 'opacity-50' : ''
            }`}
          >
            {argTypes.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>

          {/* Remove Button */}
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
          暂无启动参数
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
          添加启动参数
        </button>
      )}
    </div>
  )
}

// Compact display mode for read-only viewing
interface ArgsTableDisplayProps {
  entries: ArgsTableEntry[]
}

export function ArgsTableDisplay({ entries }: ArgsTableDisplayProps) {
  const enabledEntries = entries.filter(e => e.enabled)

  if (enabledEntries.length === 0) {
    return <span className="text-stone-400 text-sm">无</span>
  }

  return (
    <div className="flex flex-wrap gap-2">
      {enabledEntries.map((entry, index) => (
        <span
          key={index}
          className="inline-flex items-center px-2 py-1 bg-stone-100 dark:bg-stone-800 rounded text-xs font-mono text-stone-700 dark:text-stone-300"
        >
          <span className="text-stone-500">{entry.key}</span>
          {entry.value && (
            <>
              <span className="text-stone-400 mx-1">=</span>
              <span>{entry.value}</span>
            </>
          )}
        </span>
      ))}
    </div>
  )
}

/**
 * Device Selector Component
 *
 * Allows users to select GPU/NPU devices for model deployment.
 */

import { useState, useEffect } from 'react'
import type { AcceleratorDevice, NodeAccelerators } from '../api/deploymentTypes'
import { deploymentClient } from '../api/deploymentClient'

interface DeviceSelectorProps {
  nodeId: string | null
  selectedDevices: number[]
  onChange: (devices: number[]) => void
  readOnly?: boolean
}

export function DeviceSelector({ nodeId, selectedDevices, onChange, readOnly = false }: DeviceSelectorProps) {
  const [accelerators, setAccelerators] = useState<NodeAccelerators | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!nodeId) {
      setAccelerators(null)
      return
    }

    const fetchAccelerators = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await deploymentClient.getNodeAccelerators(nodeId)
        setAccelerators(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : '获取加速器信息失败')
      } finally {
        setLoading(false)
      }
    }

    fetchAccelerators()
  }, [nodeId])

  const toggleDevice = (index: number) => {
    if (readOnly) return

    if (selectedDevices.includes(index)) {
      onChange(selectedDevices.filter(i => i !== index))
    } else {
      onChange([...selectedDevices, index].sort((a, b) => a - b))
    }
  }

  const selectAll = () => {
    if (!accelerators || readOnly) return
    onChange(accelerators.devices.map(d => d.index))
  }

  const selectNone = () => {
    if (readOnly) return
    onChange([])
  }

  if (!nodeId) {
    return (
      <div className="text-sm text-stone-400 dark:text-stone-500 py-4 text-center">
        请先选择部署节点
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-4">
        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-teal-600"></div>
        <span className="ml-2 text-sm text-stone-500">加载中...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-sm text-red-500 py-4 text-center">
        {error}
      </div>
    )
  }

  if (!accelerators || accelerators.devices.length === 0) {
    return (
      <div className="text-sm text-stone-400 dark:text-stone-500 py-4 text-center">
        该节点无可用加速器设备
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Header with actions */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-stone-600 dark:text-stone-400">
          {accelerators.accelerator_type || '未知类型'} · {accelerators.accelerator_count} 个设备
        </div>
        {!readOnly && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={selectAll}
              className="text-xs text-teal-600 hover:text-teal-700 dark:text-teal-400"
            >
              全选
            </button>
            <span className="text-stone-300">|</span>
            <button
              type="button"
              onClick={selectNone}
              className="text-xs text-stone-500 hover:text-stone-700 dark:text-stone-400"
            >
              取消
            </button>
          </div>
        )}
      </div>

      {/* Device Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        {accelerators.devices.map((device) => {
          const isSelected = selectedDevices.includes(device.index)
          const healthColor = device.health_status === 'healthy'
            ? 'text-green-500'
            : device.health_status === 'unhealthy'
            ? 'text-red-500'
            : 'text-stone-400'

          return (
            <button
              key={device.index}
              type="button"
              onClick={() => toggleDevice(device.index)}
              disabled={readOnly}
              className={`p-3 rounded-lg border-2 transition-all text-left ${
                isSelected
                  ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/20'
                  : 'border-stone-200 dark:border-stone-700 hover:border-stone-300 dark:hover:border-stone-600'
              } ${readOnly ? 'cursor-default' : 'cursor-pointer'}`}
            >
              {/* Device Index Badge */}
              <div className="flex items-center justify-between mb-2">
                <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                  isSelected
                    ? 'bg-teal-500 text-white'
                    : 'bg-stone-200 dark:bg-stone-700 text-stone-700 dark:text-stone-300'
                }`}>
                  GPU {device.index}
                </span>
                <span className={`text-xs ${healthColor}`}>
                  {device.health_status === 'healthy' ? '●' : device.health_status === 'unhealthy' ? '○' : '◌'}
                </span>
              </div>

              {/* Device Info */}
              <div className="text-xs text-stone-600 dark:text-stone-400 space-y-0.5">
                <div className="font-medium text-stone-800 dark:text-stone-200 truncate">
                  {device.model || '未知型号'}
                </div>
                {device.memory_mb && (
                  <div>{Math.round(device.memory_mb / 1024)} GB</div>
                )}
                {device.utilization_percent !== null && device.utilization_percent !== undefined && (
                  <div className="flex items-center gap-1">
                    <div className="flex-1 h-1 bg-stone-200 dark:bg-stone-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${device.utilization_percent > 80 ? 'bg-red-500' : 'bg-teal-500'}`}
                        style={{ width: `${device.utilization_percent}%` }}
                      />
                    </div>
                    <span>{device.utilization_percent}%</span>
                  </div>
                )}
              </div>
            </button>
          )
        })}
      </div>

      {/* Selection summary */}
      <div className="text-sm text-stone-500 dark:text-stone-400">
        已选择 {selectedDevices.length} 个设备
        {selectedDevices.length > 0 && (
          <span className="text-stone-400"> (GPU {selectedDevices.join(', ')})</span>
        )}
      </div>
    </div>
  )
}

// Compact display for read-only viewing
interface DeviceDisplayProps {
  devices: number[] | null
}

export function DeviceDisplay({ devices }: DeviceDisplayProps) {
  if (!devices || devices.length === 0) {
    return <span className="text-stone-400">未指定</span>
  }

  return (
    <div className="flex flex-wrap gap-1">
      {devices.map((index) => (
        <span
          key={index}
          className="inline-flex items-center px-2 py-0.5 bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 rounded text-xs font-medium"
        >
          GPU {index}
        </span>
      ))}
    </div>
  )
}

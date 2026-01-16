/**
 * Create Deployment Page
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { deploymentClient } from '../api/deploymentClient'
import { nodeManagementClient } from '../../nodes/api/nodeManagementClient'
import type {
  DeploymentCreateRequest,
  DeploymentFramework,
  ModelSource,
  EnvTableEntry,
  ArgsTableEntry,
  FrameworkCompatibility,
} from '../api/deploymentTypes'
import type { Node } from '../../nodes/api/nodeManagementTypes'
import { EnvTable } from '../components/EnvTable'
import { ArgsTable } from '../components/ArgsTable'
import { DeviceSelector } from '../components/DeviceSelector'
import { FrameworkBadge } from '../components/StatusBadge'

// Default args for each framework
const defaultArgs: Record<DeploymentFramework, ArgsTableEntry[]> = {
  vllm: [
    { key: '--max-model-len', value: '', arg_type: 'int', enabled: false },
    { key: '--gpu-memory-utilization', value: '0.9', arg_type: 'float', enabled: true },
    { key: '--dtype', value: 'auto', arg_type: 'string', enabled: true },
    { key: '--trust-remote-code', value: '', arg_type: 'bool', enabled: true },
  ],
  sglang: [
    { key: '--mem-fraction-static', value: '0.9', arg_type: 'float', enabled: true },
    { key: '--dtype', value: 'auto', arg_type: 'string', enabled: true },
    { key: '--trust-remote-code', value: '', arg_type: 'bool', enabled: true },
    { key: '--context-length', value: '', arg_type: 'int', enabled: false },
  ],
  xinference: [
    { key: '--n-gpu', value: '1', arg_type: 'int', enabled: true },
    { key: '--max-model-len', value: '', arg_type: 'int', enabled: false },
  ],
}

export function CreateDeploymentPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  // Form state
  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [description, setDescription] = useState('')
  const [framework, setFramework] = useState<DeploymentFramework>('vllm')
  const [nodeId, setNodeId] = useState<string>('')
  const [modelSource, setModelSource] = useState<ModelSource>('huggingface')
  const [modelRepoId, setModelRepoId] = useState('')
  const [modelRevision, setModelRevision] = useState('')
  const [port, setPort] = useState<number | ''>('')
  const [gpuDevices, setGpuDevices] = useState<number[]>([])
  const [tensorParallelSize, setTensorParallelSize] = useState(1)
  const [gpuMemoryUtilization, setGpuMemoryUtilization] = useState(0.9)
  const [envTable, setEnvTable] = useState<EnvTableEntry[]>([])
  const [argsTable, setArgsTable] = useState<ArgsTableEntry[]>(defaultArgs.vllm)

  // UI state
  const [nodes, setNodes] = useState<Node[]>([])
  const [loadingNodes, setLoadingNodes] = useState(true)
  const [compatibility, setCompatibility] = useState<FrameworkCompatibility[]>([])
  const [checkingCompatibility, setCheckingCompatibility] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Step state
  const [currentStep, setCurrentStep] = useState(1)

  // Load nodes on mount
  useEffect(() => {
    const fetchNodes = async () => {
      setLoadingNodes(true)
      try {
        const response = await nodeManagementClient.listNodes({
          page: 1,
          page_size: 100,
          status: 'READY',
        })
        setNodes(response.nodes)
      } catch (err) {
        console.error('Failed to fetch nodes:', err)
      } finally {
        setLoadingNodes(false)
      }
    }
    fetchNodes()
  }, [])

  // Check compatibility when node changes
  useEffect(() => {
    if (!nodeId) {
      setCompatibility([])
      return
    }

    const checkCompatibility = async () => {
      setCheckingCompatibility(true)
      try {
        const result = await deploymentClient.checkCompatibility({
          node_id: nodeId,
        })
        setCompatibility(result.frameworks)
      } catch (err) {
        console.error('Failed to check compatibility:', err)
      } finally {
        setCheckingCompatibility(false)
      }
    }
    checkCompatibility()
  }, [nodeId])

  // Update args when framework changes
  useEffect(() => {
    setArgsTable(defaultArgs[framework])
  }, [framework])

  // Auto-update tensor parallel size
  useEffect(() => {
    if (gpuDevices.length > 0 && tensorParallelSize > gpuDevices.length) {
      setTensorParallelSize(gpuDevices.length)
    }
  }, [gpuDevices])

  // Handle form submission
  const handleSubmit = async () => {
    setError(null)
    setSubmitting(true)

    try {
      const request: DeploymentCreateRequest = {
        name,
        display_name: displayName || undefined,
        description: description || undefined,
        framework,
        node_id: nodeId,
        model_source: modelSource,
        model_repo_id: modelRepoId,
        model_revision: modelRevision || undefined,
        port: port || undefined,
        gpu_devices: gpuDevices.length > 0 ? gpuDevices : undefined,
        tensor_parallel_size: tensorParallelSize,
        gpu_memory_utilization: gpuMemoryUtilization,
        env_table: envTable.filter(e => e.name),
        args_table: argsTable.filter(a => a.key && a.enabled),
      }

      const deployment = await deploymentClient.createDeployment(request)
      navigate(`/dashboard/deployment/${deployment.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建部署失败')
    } finally {
      setSubmitting(false)
    }
  }

  const selectedNode = nodes.find(n => n.id === nodeId)
  const frameworkCompatible = compatibility.find(c => c.framework === framework)?.supported ?? true

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return name && modelRepoId
      case 2:
        return nodeId && frameworkCompatible
      case 3:
        return true
      default:
        return false
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/dashboard/deployment')}
          className="flex items-center text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100 mb-4"
        >
          <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          返回部署列表
        </button>
        <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">新建模型部署</h1>
        <p className="text-stone-600 dark:text-stone-400 mt-1">配置并部署大语言模型推理服务</p>
      </div>

      {/* Steps Progress */}
      <div className="flex items-center mb-8">
        {['基础配置', '节点选择', '高级设置'].map((label, idx) => {
          const step = idx + 1
          const isActive = step === currentStep
          const isComplete = step < currentStep

          return (
            <div key={step} className="flex-1 flex items-center">
              <div className={`flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium ${
                isActive
                  ? 'bg-teal-600 text-white'
                  : isComplete
                  ? 'bg-teal-100 dark:bg-teal-900 text-teal-600 dark:text-teal-400'
                  : 'bg-stone-200 dark:bg-stone-700 text-stone-500'
              }`}>
                {isComplete ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : step}
              </div>
              <span className={`ml-2 text-sm ${isActive ? 'text-teal-600 dark:text-teal-400 font-medium' : 'text-stone-500'}`}>
                {label}
              </span>
              {step < 3 && (
                <div className={`flex-1 h-0.5 mx-4 ${isComplete ? 'bg-teal-600' : 'bg-stone-200 dark:bg-stone-700'}`} />
              )}
            </div>
          )
        })}
      </div>

      {/* Form Content */}
      <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
        {/* Step 1: Basic Configuration */}
        {currentStep === 1 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">基础配置</h2>

            {/* Name */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                部署名称 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))}
                placeholder="my-llm-deployment"
                className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
              <p className="mt-1 text-xs text-stone-500">仅支持小写字母、数字和连字符</p>
            </div>

            {/* Display Name */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                显示名称
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="我的 LLM 部署"
                className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>

            {/* Framework */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                推理框架 <span className="text-red-500">*</span>
              </label>
              <div className="grid grid-cols-3 gap-3">
                {(['vllm', 'sglang', 'xinference'] as DeploymentFramework[]).map((fw) => (
                  <button
                    key={fw}
                    type="button"
                    onClick={() => setFramework(fw)}
                    className={`p-4 rounded-lg border-2 transition-all text-left ${
                      framework === fw
                        ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/20'
                        : 'border-stone-200 dark:border-stone-700 hover:border-stone-300'
                    }`}
                  >
                    <FrameworkBadge framework={fw} />
                    <p className="text-xs text-stone-500 mt-2">
                      {fw === 'vllm' && 'OpenAI 兼容，高吞吐'}
                      {fw === 'sglang' && '结构化生成，高性能'}
                      {fw === 'xinference' && '多模型多后端'}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {/* Model Source */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                模型来源 <span className="text-red-500">*</span>
              </label>
              <div className="flex gap-3">
                {(['huggingface', 'modelscope', 'local'] as ModelSource[]).map((source) => (
                  <button
                    key={source}
                    type="button"
                    onClick={() => setModelSource(source)}
                    className={`px-4 py-2 rounded-lg border transition-all ${
                      modelSource === source
                        ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/20 text-teal-700 dark:text-teal-300'
                        : 'border-stone-200 dark:border-stone-700 text-stone-600 dark:text-stone-400 hover:border-stone-300'
                    }`}
                  >
                    {source === 'huggingface' && 'HuggingFace'}
                    {source === 'modelscope' && 'ModelScope'}
                    {source === 'local' && '本地路径'}
                  </button>
                ))}
              </div>
            </div>

            {/* Model Repo ID */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                模型仓库 ID <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={modelRepoId}
                onChange={(e) => setModelRepoId(e.target.value)}
                placeholder={modelSource === 'local' ? '/data/models/my-model' : 'meta-llama/Llama-2-7b-chat-hf'}
                className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>

            {/* Model Revision */}
            {modelSource !== 'local' && (
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                  模型版本/分支
                </label>
                <input
                  type="text"
                  value={modelRevision}
                  onChange={(e) => setModelRevision(e.target.value)}
                  placeholder="main (默认)"
                  className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>
            )}

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                描述
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="部署描述..."
                rows={3}
                className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>
          </div>
        )}

        {/* Step 2: Node Selection */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">选择部署节点</h2>

            {/* Node Selector */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                目标节点 <span className="text-red-500">*</span>
              </label>
              {loadingNodes ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-teal-600"></div>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-64 overflow-y-auto">
                  {nodes.map((node) => (
                    <button
                      key={node.id}
                      type="button"
                      onClick={() => setNodeId(node.id)}
                      className={`p-4 rounded-lg border-2 transition-all text-left ${
                        nodeId === node.id
                          ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/20'
                          : 'border-stone-200 dark:border-stone-700 hover:border-stone-300'
                      }`}
                    >
                      <div className="font-medium text-stone-900 dark:text-stone-100">
                        {node.display_name || node.name}
                      </div>
                      <div className="text-xs text-stone-500 mt-1">{node.host}</div>
                      {node.accelerator_summary && Object.keys(node.accelerator_summary).length > 0 && (
                        <div className="flex gap-1 mt-2">
                          {Object.entries(node.accelerator_summary).map(([type, count]) => (
                            <span key={type} className="px-2 py-0.5 bg-stone-100 dark:bg-stone-700 rounded text-xs">
                              {type}: {count}
                            </span>
                          ))}
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Compatibility Check */}
            {nodeId && (
              <div className="bg-stone-50 dark:bg-stone-900 rounded-lg p-4">
                <h3 className="text-sm font-medium text-stone-700 dark:text-stone-300 mb-3">框架兼容性</h3>
                {checkingCompatibility ? (
                  <div className="flex items-center gap-2 text-sm text-stone-500">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-teal-600"></div>
                    检查中...
                  </div>
                ) : (
                  <div className="space-y-2">
                    {compatibility.map((c) => (
                      <div key={c.framework} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <FrameworkBadge framework={c.framework as DeploymentFramework} />
                          {c.framework === framework && (
                            <span className="text-xs text-teal-600 dark:text-teal-400">(已选)</span>
                          )}
                        </div>
                        <div className={`flex items-center gap-1 text-sm ${c.supported ? 'text-green-600' : 'text-red-600'}`}>
                          {c.supported ? (
                            <>
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                              支持
                            </>
                          ) : (
                            <>
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                              {c.reason || '不支持'}
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {!frameworkCompatible && (
                  <div className="mt-3 p-2 bg-red-50 dark:bg-red-900/20 rounded text-sm text-red-600 dark:text-red-400">
                    所选框架在此节点上不兼容，请选择其他节点或框架
                  </div>
                )}
              </div>
            )}

            {/* GPU Device Selection */}
            {nodeId && (
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                  GPU 设备
                </label>
                <DeviceSelector
                  nodeId={nodeId}
                  selectedDevices={gpuDevices}
                  onChange={setGpuDevices}
                />
              </div>
            )}

            {/* Tensor Parallel Size */}
            {gpuDevices.length > 1 && (
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                  张量并行度 (TP)
                </label>
                <select
                  value={tensorParallelSize}
                  onChange={(e) => setTensorParallelSize(Number(e.target.value))}
                  className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                >
                  {Array.from({ length: gpuDevices.length }, (_, i) => i + 1).map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-stone-500">
                  将模型切分到多个 GPU 上并行推理
                </p>
              </div>
            )}

            {/* Port */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                服务端口
              </label>
              <input
                type="number"
                value={port}
                onChange={(e) => setPort(e.target.value ? Number(e.target.value) : '')}
                placeholder="自动分配"
                min={1024}
                max={65535}
                className="w-full px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
              <p className="mt-1 text-xs text-stone-500">留空将自动分配可用端口</p>
            </div>
          </div>
        )}

        {/* Step 3: Advanced Settings */}
        {currentStep === 3 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100 mb-4">高级设置</h2>

            {/* GPU Memory Utilization */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                GPU 显存利用率
              </label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  value={gpuMemoryUtilization}
                  onChange={(e) => setGpuMemoryUtilization(Number(e.target.value))}
                  min={0.1}
                  max={1}
                  step={0.05}
                  className="flex-1"
                />
                <span className="text-sm font-mono text-stone-700 dark:text-stone-300 w-16 text-right">
                  {(gpuMemoryUtilization * 100).toFixed(0)}%
                </span>
              </div>
            </div>

            {/* CLI Arguments */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                启动参数
              </label>
              <ArgsTable entries={argsTable} onChange={setArgsTable} />
            </div>

            {/* Environment Variables */}
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                环境变量
              </label>
              <EnvTable entries={envTable} onChange={setEnvTable} />
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 rounded-lg text-sm text-red-600 dark:text-red-400">
            {error}
          </div>
        )}

        {/* Navigation Buttons */}
        <div className="flex items-center justify-between mt-8 pt-6 border-t border-stone-200 dark:border-stone-700">
          <button
            onClick={() => currentStep > 1 ? setCurrentStep(currentStep - 1) : navigate('/dashboard/deployment')}
            className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors"
          >
            {currentStep === 1 ? '取消' : '上一步'}
          </button>
          <button
            onClick={() => currentStep < 3 ? setCurrentStep(currentStep + 1) : handleSubmit()}
            disabled={!canProceed() || submitting}
            className="px-6 py-2 bg-teal-600 hover:bg-teal-700 disabled:bg-stone-300 dark:disabled:bg-stone-600 text-white rounded-lg font-medium transition-colors disabled:cursor-not-allowed flex items-center gap-2"
          >
            {submitting && (
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            )}
            {currentStep === 3 ? '创建部署' : '下一步'}
          </button>
        </div>
      </div>
    </div>
  )
}

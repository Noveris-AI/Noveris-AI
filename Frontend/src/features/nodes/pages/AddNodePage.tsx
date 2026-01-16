/**
 * Add Node Wizard Page
 */

import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { nodeManagementClient } from '../api/nodeManagementClient'
import type { NodeGroup, NodeCreateRequest, ConnectionType } from '../api/nodeManagementTypes'

type Step = 'connection' | 'credentials' | 'groups' | 'review'

export function AddNodePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  // Wizard state
  const [currentStep, setCurrentStep] = useState<Step>('connection')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Form state
  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [host, setHost] = useState('')
  const [port, setPort] = useState(22)
  const [connectionType, setConnectionType] = useState<ConnectionType>('ssh')
  const [sshUser, setSshUser] = useState('root')

  // Credential state
  const [credentialType, setCredentialType] = useState<'ssh_key' | 'password'>('ssh_key')
  const [sshPrivateKey, setSshPrivateKey] = useState('')
  const [sshKeyPassphrase, setSshKeyPassphrase] = useState('')
  const [password, setPassword] = useState('')

  // Bastion state
  const [useBastion, setUseBastion] = useState(false)
  const [bastionHost, setBastionHost] = useState('')
  const [bastionPort, setBastionPort] = useState(22)
  const [bastionUser, setBastionUser] = useState('')
  const [bastionPassword, setBastionPassword] = useState('')
  const [bastionSshKey, setBastionSshKey] = useState('')

  // Groups state
  const [groups, setGroups] = useState<NodeGroup[]>([])
  const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([])
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState('')

  // Fetch groups
  useEffect(() => {
    const fetchGroups = async () => {
      try {
        const response = await nodeManagementClient.listNodeGroups(1, 100)
        setGroups(response.groups)
      } catch (err) {
        console.error('Failed to fetch groups:', err)
      }
    }
    fetchGroups()
  }, [])

  // Auto-generate name from host
  useEffect(() => {
    if (!name && host) {
      setName(host.replace(/[^a-zA-Z0-9-]/g, '-').toLowerCase())
    }
  }, [host, name])

  // Steps configuration
  const steps: Array<{ key: Step; label: string; description: string }> = [
    { key: 'connection', label: '连接信息', description: '配置节点连接' },
    { key: 'credentials', label: '认证凭据', description: '配置 SSH 认证' },
    { key: 'groups', label: '分组标签', description: '分配分组和标签' },
    { key: 'review', label: '确认创建', description: '检查并创建节点' },
  ]

  const currentStepIndex = steps.findIndex((s) => s.key === currentStep)

  // Validation
  const validateConnection = () => {
    if (!name.trim()) return '请输入节点名称'
    if (!host.trim()) return '请输入主机地址'
    if (connectionType === 'ssh' && !sshUser.trim()) return '请输入 SSH 用户名'
    return null
  }

  const validateCredentials = () => {
    if (connectionType === 'local') return null
    if (credentialType === 'ssh_key' && !sshPrivateKey.trim()) return '请输入 SSH 私钥'
    if (credentialType === 'password' && !password.trim()) return '请输入密码'
    if (useBastion && !bastionHost.trim()) return '请输入跳板机地址'
    return null
  }

  // Handle next step
  const handleNext = () => {
    let validationError: string | null = null

    if (currentStep === 'connection') {
      validationError = validateConnection()
      if (!validationError) setCurrentStep('credentials')
    } else if (currentStep === 'credentials') {
      validationError = validateCredentials()
      if (!validationError) setCurrentStep('groups')
    } else if (currentStep === 'groups') {
      setCurrentStep('review')
    }

    if (validationError) {
      setError(validationError)
    } else {
      setError(null)
    }
  }

  // Handle previous step
  const handlePrev = () => {
    if (currentStep === 'credentials') setCurrentStep('connection')
    else if (currentStep === 'groups') setCurrentStep('credentials')
    else if (currentStep === 'review') setCurrentStep('groups')
    setError(null)
  }

  // Handle submit
  const handleSubmit = async () => {
    setLoading(true)
    setError(null)

    try {
      const data: NodeCreateRequest = {
        name: name.trim(),
        display_name: displayName.trim() || undefined,
        host: host.trim(),
        port,
        connection_type: connectionType,
        ssh_user: connectionType === 'ssh' ? (sshUser.trim() || undefined) : undefined,
        credential_type: connectionType === 'local' ? 'ssh_key' : credentialType,
        ssh_private_key: connectionType === 'ssh' && credentialType === 'ssh_key' ? sshPrivateKey : undefined,
        ssh_key_passphrase: connectionType === 'ssh' && sshKeyPassphrase ? sshKeyPassphrase : undefined,
        password: connectionType === 'ssh' && credentialType === 'password' ? password : undefined,
        bastion_host: useBastion ? bastionHost.trim() : undefined,
        bastion_port: useBastion ? bastionPort : undefined,
        bastion_user: useBastion ? bastionUser.trim() : undefined,
        bastion_ssh_key: useBastion && bastionSshKey ? bastionSshKey : undefined,
        bastion_password: useBastion && bastionPassword ? bastionPassword : undefined,
        group_ids: selectedGroupIds.length > 0 ? selectedGroupIds : undefined,
        tags: tags.length > 0 ? tags : undefined,
      }

      const node = await nodeManagementClient.createNode(data)
      navigate(`/dashboard/nodes/${node.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建节点失败')
    } finally {
      setLoading(false)
    }
  }

  // Handle tag input
  const handleAddTag = () => {
    const tag = tagInput.trim()
    if (tag && !tags.includes(tag)) {
      setTags([...tags, tag])
      setTagInput('')
    }
  }

  const handleRemoveTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag))
  }

  // Handle group selection
  const handleGroupToggle = (groupId: string) => {
    if (selectedGroupIds.includes(groupId)) {
      setSelectedGroupIds(selectedGroupIds.filter((id) => id !== groupId))
    } else {
      setSelectedGroupIds([...selectedGroupIds, groupId])
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/dashboard/nodes" className="hover:text-teal-600 dark:hover:text-teal-400">
          节点管理
        </Link>
        <span>/</span>
        <span className="text-stone-900 dark:text-stone-100">添加节点</span>
      </nav>

      {/* Progress */}
      <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
        <div className="flex items-center justify-between">
          {steps.map((step, index) => (
            <div key={step.key} className="flex items-center">
              <div className="flex flex-col items-center">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium ${
                    index < currentStepIndex
                      ? 'bg-teal-600 text-white'
                      : index === currentStepIndex
                      ? 'bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 border-2 border-teal-600'
                      : 'bg-stone-100 dark:bg-stone-700 text-stone-400'
                  }`}
                >
                  {index < currentStepIndex ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    index + 1
                  )}
                </div>
                <span
                  className={`mt-2 text-xs ${
                    index <= currentStepIndex
                      ? 'text-stone-900 dark:text-stone-100'
                      : 'text-stone-400'
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {index < steps.length - 1 && (
                <div
                  className={`w-16 md:w-24 h-0.5 mx-2 ${
                    index < currentStepIndex ? 'bg-teal-600' : 'bg-stone-200 dark:bg-stone-700'
                  }`}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Step Content */}
      <div className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 p-6">
        {/* Step 1: Connection */}
        {currentStep === 'connection' && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
              连接信息
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  主机地址 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  placeholder="192.168.1.100 或 node1.example.com"
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  端口
                </label>
                <input
                  type="number"
                  value={port}
                  onChange={(e) => setPort(parseInt(e.target.value) || 22)}
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  节点名称 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="node-001"
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
                <p className="mt-1 text-xs text-stone-500">Ansible inventory 中使用的名称</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  显示名称
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="GPU 服务器 01"
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                连接方式
              </label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="connectionType"
                    checked={connectionType === 'ssh'}
                    onChange={() => setConnectionType('ssh')}
                    className="w-4 h-4 text-teal-600 focus:ring-teal-500"
                  />
                  <span className="text-stone-700 dark:text-stone-300">SSH 远程连接</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="connectionType"
                    checked={connectionType === 'local'}
                    onChange={() => setConnectionType('local')}
                    className="w-4 h-4 text-teal-600 focus:ring-teal-500"
                  />
                  <span className="text-stone-700 dark:text-stone-300">本地连接</span>
                </label>
              </div>
            </div>

            {connectionType === 'ssh' && (
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  SSH 用户名 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={sshUser}
                  onChange={(e) => setSshUser(e.target.value)}
                  placeholder="root"
                  className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>
            )}
          </div>
        )}

        {/* Step 2: Credentials */}
        {currentStep === 'credentials' && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
              认证凭据
            </h2>

            {connectionType === 'local' ? (
              <div className="bg-stone-50 dark:bg-stone-700/50 rounded-lg p-4 text-stone-600 dark:text-stone-400">
                本地连接模式不需要配置认证凭据
              </div>
            ) : (
              <>
                <div>
                  <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                    认证方式
                  </label>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="credentialType"
                        checked={credentialType === 'ssh_key'}
                        onChange={() => setCredentialType('ssh_key')}
                        className="w-4 h-4 text-teal-600 focus:ring-teal-500"
                      />
                      <span className="text-stone-700 dark:text-stone-300">SSH 密钥</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="credentialType"
                        checked={credentialType === 'password'}
                        onChange={() => setCredentialType('password')}
                        className="w-4 h-4 text-teal-600 focus:ring-teal-500"
                      />
                      <span className="text-stone-700 dark:text-stone-300">密码</span>
                    </label>
                  </div>
                </div>

                {credentialType === 'ssh_key' ? (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                        SSH 私钥 <span className="text-red-500">*</span>
                      </label>
                      <textarea
                        value={sshPrivateKey}
                        onChange={(e) => setSshPrivateKey(e.target.value)}
                        placeholder="-----BEGIN RSA PRIVATE KEY-----&#10;...&#10;-----END RSA PRIVATE KEY-----"
                        rows={6}
                        className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                        密钥密码 (可选)
                      </label>
                      <input
                        type="password"
                        value={sshKeyPassphrase}
                        onChange={(e) => setSshKeyPassphrase(e.target.value)}
                        placeholder="如果私钥有密码保护"
                        className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                      />
                    </div>
                  </div>
                ) : (
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      SSH 密码 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                    />
                  </div>
                )}

                {/* Bastion Host */}
                <div className="border-t border-stone-200 dark:border-stone-700 pt-6">
                  <label className="flex items-center gap-2 cursor-pointer mb-4">
                    <input
                      type="checkbox"
                      checked={useBastion}
                      onChange={(e) => setUseBastion(e.target.checked)}
                      className="w-4 h-4 text-teal-600 focus:ring-teal-500 rounded"
                    />
                    <span className="text-stone-700 dark:text-stone-300">通过跳板机连接</span>
                  </label>

                  {useBastion && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pl-6">
                      <div>
                        <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                          跳板机地址 <span className="text-red-500">*</span>
                        </label>
                        <input
                          type="text"
                          value={bastionHost}
                          onChange={(e) => setBastionHost(e.target.value)}
                          placeholder="bastion.example.com"
                          className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                          跳板机端口
                        </label>
                        <input
                          type="number"
                          value={bastionPort}
                          onChange={(e) => setBastionPort(parseInt(e.target.value) || 22)}
                          className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                          跳板机用户名
                        </label>
                        <input
                          type="text"
                          value={bastionUser}
                          onChange={(e) => setBastionUser(e.target.value)}
                          className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                          跳板机密码
                        </label>
                        <input
                          type="password"
                          value={bastionPassword}
                          onChange={(e) => setBastionPassword(e.target.value)}
                          className="w-full px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {/* Step 3: Groups & Tags */}
        {currentStep === 'groups' && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
              分组与标签
            </h2>

            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                分配到分组
              </label>
              {groups.length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                  {groups.map((group) => (
                    <label
                      key={group.id}
                      className={`flex items-center gap-2 p-3 border rounded-lg cursor-pointer transition-colors ${
                        selectedGroupIds.includes(group.id)
                          ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/20'
                          : 'border-stone-200 dark:border-stone-700 hover:bg-stone-50 dark:hover:bg-stone-700/50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedGroupIds.includes(group.id)}
                        onChange={() => handleGroupToggle(group.id)}
                        className="w-4 h-4 text-teal-600 focus:ring-teal-500 rounded"
                      />
                      <span className="text-stone-700 dark:text-stone-300">{group.display_name || group.name}</span>
                    </label>
                  ))}
                </div>
              ) : (
                <p className="text-stone-500 dark:text-stone-400">暂无可用分组</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                标签
              </label>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                  placeholder="输入标签后按回车"
                  className="flex-1 px-3 py-2 border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-700 text-stone-900 dark:text-stone-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
                <button
                  type="button"
                  onClick={handleAddTag}
                  className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-700"
                >
                  添加
                </button>
              </div>
              {tags.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-3 py-1 bg-stone-100 dark:bg-stone-700 text-stone-700 dark:text-stone-300 rounded-lg text-sm flex items-center gap-2"
                    >
                      {tag}
                      <button
                        type="button"
                        onClick={() => handleRemoveTag(tag)}
                        className="text-stone-400 hover:text-stone-600 dark:hover:text-stone-200"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Step 4: Review */}
        {currentStep === 'review' && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
              确认创建
            </h2>

            <div className="bg-stone-50 dark:bg-stone-700/50 rounded-lg p-4 space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-stone-500 dark:text-stone-400">节点名称</dt>
                  <dd className="font-medium text-stone-900 dark:text-stone-100">{name}</dd>
                </div>
                <div>
                  <dt className="text-stone-500 dark:text-stone-400">显示名称</dt>
                  <dd className="font-medium text-stone-900 dark:text-stone-100">{displayName || '-'}</dd>
                </div>
                <div>
                  <dt className="text-stone-500 dark:text-stone-400">主机地址</dt>
                  <dd className="font-medium text-stone-900 dark:text-stone-100">{host}:{port}</dd>
                </div>
                <div>
                  <dt className="text-stone-500 dark:text-stone-400">连接方式</dt>
                  <dd className="font-medium text-stone-900 dark:text-stone-100">
                    {connectionType === 'local' ? '本地连接' : `SSH (${sshUser})`}
                  </dd>
                </div>
                {connectionType === 'ssh' && (
                  <div>
                    <dt className="text-stone-500 dark:text-stone-400">认证方式</dt>
                    <dd className="font-medium text-stone-900 dark:text-stone-100">
                      {credentialType === 'ssh_key' ? 'SSH 密钥' : '密码'}
                    </dd>
                  </div>
                )}
                {useBastion && (
                  <div>
                    <dt className="text-stone-500 dark:text-stone-400">跳板机</dt>
                    <dd className="font-medium text-stone-900 dark:text-stone-100">
                      {bastionHost}:{bastionPort}
                    </dd>
                  </div>
                )}
              </div>

              {selectedGroupIds.length > 0 && (
                <div>
                  <dt className="text-sm text-stone-500 dark:text-stone-400 mb-1">分组</dt>
                  <dd className="flex flex-wrap gap-2">
                    {groups
                      .filter((g) => selectedGroupIds.includes(g.id))
                      .map((g) => (
                        <span
                          key={g.id}
                          className="px-2 py-1 bg-stone-100 dark:bg-stone-600 rounded text-sm"
                        >
                          {g.display_name || g.name}
                        </span>
                      ))}
                  </dd>
                </div>
              )}

              {tags.length > 0 && (
                <div>
                  <dt className="text-sm text-stone-500 dark:text-stone-400 mb-1">标签</dt>
                  <dd className="flex flex-wrap gap-2">
                    {tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-2 py-1 bg-stone-100 dark:bg-stone-600 rounded text-sm"
                      >
                        {tag}
                      </span>
                    ))}
                  </dd>
                </div>
              )}
            </div>

            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4 text-sm text-amber-700 dark:text-amber-300">
              <strong>提示：</strong>创建节点后，系统会自动收集节点信息（Facts），包括硬件配置和加速器信息。
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex justify-between">
        <button
          type="button"
          onClick={() => currentStep === 'connection' ? navigate('/dashboard/nodes') : handlePrev()}
          className="px-4 py-2 border border-stone-300 dark:border-stone-600 rounded-lg text-stone-700 dark:text-stone-300 hover:bg-stone-50 dark:hover:bg-stone-700 transition-colors"
        >
          {currentStep === 'connection' ? '取消' : '上一步'}
        </button>

        {currentStep === 'review' ? (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={loading}
            className="px-6 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {loading && (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            )}
            创建节点
          </button>
        ) : (
          <button
            type="button"
            onClick={handleNext}
            className="px-6 py-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg font-medium transition-colors"
          >
            下一步
          </button>
        )}
      </div>
    </div>
  )
}

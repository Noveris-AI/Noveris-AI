/**
 * Notifications Settings Page
 *
 * Manages notification channels: SMTP, webhooks, enterprise IM integrations.
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Mail,
  Webhook,
  MessageSquare,
  Plus,
  Trash2,
  Edit2,
  Check,
  X,
  Loader2,
  Send,
  AlertTriangle,
  Eye,
  EyeOff,
} from 'lucide-react';
import { SettingCard } from '../components/SettingCard';
import { SettingRow } from '../components/SettingRow';
import type { NotificationChannelType } from '../types';

// Mock hooks - replace with actual implementation
const useNotificationChannels = () => ({
  data: { channels: [] as any[] },
  isLoading: false,
});

const useCreateNotificationChannel = () => ({
  mutateAsync: async (data: any) => data,
  isPending: false,
});

const useUpdateNotificationChannel = () => ({
  mutateAsync: async (id: string, data: any) => data,
  isPending: false,
});

const useDeleteNotificationChannel = () => ({
  mutateAsync: async (id: string) => {},
  isPending: false,
});

const useTestNotificationChannel = () => ({
  mutateAsync: async (id: string) => ({ success: true }),
  isPending: false,
});

interface NotificationChannel {
  id: string;
  name: string;
  channel_type: NotificationChannelType;
  enabled: boolean;
  config: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export function NotificationsSettingsPage() {
  const { t } = useTranslation();

  const { data: channelsData, isLoading } = useNotificationChannels();
  const createChannel = useCreateNotificationChannel();
  const updateChannel = useUpdateNotificationChannel();
  const deleteChannel = useDeleteNotificationChannel();
  const testChannel = useTestNotificationChannel();

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingChannel, setEditingChannel] = useState<NotificationChannel | null>(null);
  const [channelType, setChannelType] = useState<NotificationChannelType>('smtp');

  // Form state
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [showSecrets, setShowSecrets] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message?: string } | null>(null);

  const channels = channelsData?.channels || [];

  const handleOpenModal = (type: NotificationChannelType, channel?: NotificationChannel) => {
    setChannelType(type);
    setEditingChannel(channel || null);
    setFormData(channel?.config || getDefaultConfig(type));
    setShowModal(true);
    setTestResult(null);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingChannel(null);
    setFormData({});
    setTestResult(null);
    setShowSecrets(false);
  };

  const getDefaultConfig = (type: NotificationChannelType): Record<string, any> => {
    switch (type) {
      case 'smtp':
        return {
          host: '',
          port: 587,
          username: '',
          password: '',
          from_email: '',
          from_name: '',
          use_tls: true,
          use_ssl: false,
        };
      case 'webhook':
        return {
          url: '',
          method: 'POST',
          headers: {},
          secret: '',
        };
      case 'slack':
        return {
          webhook_url: '',
          channel: '',
          username: '',
        };
      case 'dingtalk':
        return {
          webhook_url: '',
          secret: '',
        };
      case 'feishu':
        return {
          webhook_url: '',
          secret: '',
        };
      case 'wechat':
        return {
          corp_id: '',
          agent_id: '',
          secret: '',
        };
      default:
        return {};
    }
  };

  const handleSave = async () => {
    try {
      const payload = {
        name: formData.name || `${channelType.toUpperCase()} Channel`,
        channel_type: channelType,
        enabled: true,
        config: formData,
      };

      if (editingChannel) {
        await updateChannel.mutateAsync(editingChannel.id, payload);
      } else {
        await createChannel.mutateAsync(payload);
      }
      handleCloseModal();
    } catch (error) {
      console.error('Failed to save channel:', error);
    }
  };

  const handleDelete = async (channel: NotificationChannel) => {
    if (!confirm(t('settings.notifications.confirmDelete', `Are you sure you want to delete "${channel.name}"?`))) {
      return;
    }
    try {
      await deleteChannel.mutateAsync(channel.id);
    } catch (error) {
      console.error('Failed to delete channel:', error);
    }
  };

  const handleTest = async () => {
    if (!editingChannel) return;
    try {
      const result = await testChannel.mutateAsync(editingChannel.id);
      setTestResult(result);
    } catch (error: any) {
      setTestResult({
        success: false,
        message: error.response?.data?.detail || 'Test failed',
      });
    }
  };

  const handleToggleEnabled = async (channel: NotificationChannel) => {
    try {
      await updateChannel.mutateAsync(channel.id, {
        enabled: !channel.enabled,
      });
    } catch (error) {
      console.error('Failed to toggle channel:', error);
    }
  };

  const getChannelIcon = (type: NotificationChannelType) => {
    switch (type) {
      case 'smtp':
        return Mail;
      case 'webhook':
        return Webhook;
      default:
        return MessageSquare;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-teal-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* SMTP Email */}
      <SettingCard
        title={t('settings.notifications.smtp', 'Email (SMTP)')}
        description={t('settings.notifications.smtpDesc', 'Configure email notifications via SMTP')}
        action={
          !channels.find((c) => c.channel_type === 'smtp') && (
            <button
              onClick={() => handleOpenModal('smtp')}
              className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors"
            >
              <Plus className="h-4 w-4" />
              {t('settings.notifications.configureSMTP', 'Configure SMTP')}
            </button>
          )
        }
      >
        {channels.filter((c) => c.channel_type === 'smtp').map((channel) => (
          <div
            key={channel.id}
            className="flex items-center justify-between py-3"
          >
            <div className="flex items-center gap-3">
              <Mail className="h-5 w-5 text-stone-400" />
              <div>
                <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                  {channel.name}
                </p>
                <p className="text-sm text-stone-500">
                  {channel.config.host}:{channel.config.port}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleToggleEnabled(channel)}
                className={`px-3 py-1 text-xs font-medium rounded-full ${
                  channel.enabled
                    ? 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                    : 'bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400'
                }`}
              >
                {channel.enabled ? t('common.enabled', 'Enabled') : t('common.disabled', 'Disabled')}
              </button>
              <button
                onClick={() => handleOpenModal('smtp', channel)}
                className="p-2 text-stone-500 hover:text-stone-700 dark:hover:text-stone-300"
              >
                <Edit2 className="h-4 w-4" />
              </button>
              <button
                onClick={() => handleDelete(channel)}
                className="p-2 text-red-500 hover:text-red-700"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
        {!channels.find((c) => c.channel_type === 'smtp') && (
          <div className="py-8 text-center text-stone-500">
            <Mail className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>{t('settings.notifications.noSMTP', 'No SMTP configuration')}</p>
            <p className="text-sm mt-1">
              {t('settings.notifications.noSMTPHint', 'Configure SMTP to enable email notifications')}
            </p>
          </div>
        )}
      </SettingCard>

      {/* Webhooks */}
      <SettingCard
        title={t('settings.notifications.webhooks', 'Webhooks')}
        description={t('settings.notifications.webhooksDesc', 'Send notifications to external services')}
        action={
          <button
            onClick={() => handleOpenModal('webhook')}
            className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors"
          >
            <Plus className="h-4 w-4" />
            {t('settings.notifications.addWebhook', 'Add Webhook')}
          </button>
        }
      >
        {channels.filter((c) => c.channel_type === 'webhook').length > 0 ? (
          <div className="space-y-2">
            {channels.filter((c) => c.channel_type === 'webhook').map((channel) => (
              <div
                key={channel.id}
                className="flex items-center justify-between p-3 bg-stone-50 dark:bg-stone-800 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <Webhook className="h-5 w-5 text-stone-400" />
                  <div>
                    <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                      {channel.name}
                    </p>
                    <p className="text-sm text-stone-500 truncate max-w-xs">
                      {channel.config.url}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleToggleEnabled(channel)}
                    className={`px-3 py-1 text-xs font-medium rounded-full ${
                      channel.enabled
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400'
                        : 'bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400'
                    }`}
                  >
                    {channel.enabled ? t('common.enabled', 'Enabled') : t('common.disabled', 'Disabled')}
                  </button>
                  <button
                    onClick={() => handleOpenModal('webhook', channel)}
                    className="p-2 text-stone-500 hover:text-stone-700 dark:hover:text-stone-300"
                  >
                    <Edit2 className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(channel)}
                    className="p-2 text-red-500 hover:text-red-700"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-8 text-center text-stone-500">
            <Webhook className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>{t('settings.notifications.noWebhooks', 'No webhooks configured')}</p>
          </div>
        )}
      </SettingCard>

      {/* Enterprise IM Integrations */}
      <SettingCard
        title={t('settings.notifications.enterpriseIM', 'Enterprise IM')}
        description={t('settings.notifications.enterpriseIMDesc', 'Slack, DingTalk, Feishu, WeChat Work')}
      >
        <div className="grid grid-cols-2 gap-4 py-4">
          {/* Slack */}
          <button
            onClick={() => handleOpenModal('slack')}
            className="flex items-center gap-3 p-4 border border-stone-200 dark:border-stone-700 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors"
          >
            <div className="h-10 w-10 bg-purple-100 dark:bg-purple-900/20 rounded-lg flex items-center justify-center">
              <MessageSquare className="h-5 w-5 text-purple-600" />
            </div>
            <div className="text-left">
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">Slack</p>
              <p className="text-xs text-stone-500">
                {channels.find((c) => c.channel_type === 'slack')
                  ? t('common.configured', 'Configured')
                  : t('common.notConfigured', 'Not configured')}
              </p>
            </div>
          </button>

          {/* DingTalk */}
          <button
            onClick={() => handleOpenModal('dingtalk')}
            className="flex items-center gap-3 p-4 border border-stone-200 dark:border-stone-700 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors"
          >
            <div className="h-10 w-10 bg-blue-100 dark:bg-blue-900/20 rounded-lg flex items-center justify-center">
              <MessageSquare className="h-5 w-5 text-blue-600" />
            </div>
            <div className="text-left">
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.notifications.dingtalk', 'DingTalk')}
              </p>
              <p className="text-xs text-stone-500">
                {channels.find((c) => c.channel_type === 'dingtalk')
                  ? t('common.configured', 'Configured')
                  : t('common.notConfigured', 'Not configured')}
              </p>
            </div>
          </button>

          {/* Feishu */}
          <button
            onClick={() => handleOpenModal('feishu')}
            className="flex items-center gap-3 p-4 border border-stone-200 dark:border-stone-700 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors"
          >
            <div className="h-10 w-10 bg-indigo-100 dark:bg-indigo-900/20 rounded-lg flex items-center justify-center">
              <MessageSquare className="h-5 w-5 text-indigo-600" />
            </div>
            <div className="text-left">
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.notifications.feishu', 'Feishu / Lark')}
              </p>
              <p className="text-xs text-stone-500">
                {channels.find((c) => c.channel_type === 'feishu')
                  ? t('common.configured', 'Configured')
                  : t('common.notConfigured', 'Not configured')}
              </p>
            </div>
          </button>

          {/* WeChat Work */}
          <button
            onClick={() => handleOpenModal('wechat')}
            className="flex items-center gap-3 p-4 border border-stone-200 dark:border-stone-700 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors"
          >
            <div className="h-10 w-10 bg-green-100 dark:bg-green-900/20 rounded-lg flex items-center justify-center">
              <MessageSquare className="h-5 w-5 text-green-600" />
            </div>
            <div className="text-left">
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.notifications.wechat', 'WeChat Work')}
              </p>
              <p className="text-xs text-stone-500">
                {channels.find((c) => c.channel_type === 'wechat')
                  ? t('common.configured', 'Configured')
                  : t('common.notConfigured', 'Not configured')}
              </p>
            </div>
          </button>
        </div>
      </SettingCard>

      {/* Configuration Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-stone-900 rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-stone-200 dark:border-stone-700 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-stone-900 dark:text-stone-100">
                {editingChannel
                  ? t('settings.notifications.editChannel', 'Edit Channel')
                  : t('settings.notifications.addChannel', 'Add Channel')}
              </h3>
              <button
                onClick={handleCloseModal}
                className="p-2 text-stone-500 hover:text-stone-700 dark:hover:text-stone-300"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Channel Name */}
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  {t('settings.notifications.channelName', 'Channel Name')}
                </label>
                <input
                  type="text"
                  value={formData.name || ''}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder={t('settings.notifications.channelNamePlaceholder', 'My SMTP Server')}
                  className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                />
              </div>

              {/* SMTP Config */}
              {channelType === 'smtp' && (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                        {t('settings.notifications.smtpHost', 'SMTP Host')}
                      </label>
                      <input
                        type="text"
                        value={formData.host || ''}
                        onChange={(e) => setFormData({ ...formData, host: e.target.value })}
                        placeholder="smtp.example.com"
                        className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                        {t('settings.notifications.smtpPort', 'Port')}
                      </label>
                      <input
                        type="number"
                        value={formData.port || 587}
                        onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value, 10) })}
                        className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.notifications.smtpUsername', 'Username')}
                    </label>
                    <input
                      type="text"
                      value={formData.username || ''}
                      onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.notifications.smtpPassword', 'Password')}
                    </label>
                    <div className="relative">
                      <input
                        type={showSecrets ? 'text' : 'password'}
                        value={formData.password || ''}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        className="w-full px-3 py-2 pr-10 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                      />
                      <button
                        type="button"
                        onClick={() => setShowSecrets(!showSecrets)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-500"
                      >
                        {showSecrets ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                        {t('settings.notifications.fromEmail', 'From Email')}
                      </label>
                      <input
                        type="email"
                        value={formData.from_email || ''}
                        onChange={(e) => setFormData({ ...formData, from_email: e.target.value })}
                        placeholder="noreply@example.com"
                        className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                        {t('settings.notifications.fromName', 'From Name')}
                      </label>
                      <input
                        type="text"
                        value={formData.from_name || ''}
                        onChange={(e) => setFormData({ ...formData, from_name: e.target.value })}
                        placeholder="Platform Notifications"
                        className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={formData.use_tls ?? true}
                        onChange={(e) => setFormData({ ...formData, use_tls: e.target.checked })}
                        className="rounded border-stone-300 text-teal-600 focus:ring-teal-500"
                      />
                      <span className="text-sm text-stone-700 dark:text-stone-300">Use TLS</span>
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={formData.use_ssl ?? false}
                        onChange={(e) => setFormData({ ...formData, use_ssl: e.target.checked })}
                        className="rounded border-stone-300 text-teal-600 focus:ring-teal-500"
                      />
                      <span className="text-sm text-stone-700 dark:text-stone-300">Use SSL</span>
                    </label>
                  </div>
                </>
              )}

              {/* Webhook Config */}
              {channelType === 'webhook' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.notifications.webhookUrl', 'Webhook URL')}
                    </label>
                    <input
                      type="url"
                      value={formData.url || ''}
                      onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                      placeholder="https://example.com/webhook"
                      className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.notifications.webhookSecret', 'Secret (optional)')}
                    </label>
                    <input
                      type={showSecrets ? 'text' : 'password'}
                      value={formData.secret || ''}
                      onChange={(e) => setFormData({ ...formData, secret: e.target.value })}
                      placeholder={t('settings.notifications.webhookSecretPlaceholder', 'For HMAC signature verification')}
                      className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                    />
                  </div>
                </>
              )}

              {/* Slack Config */}
              {channelType === 'slack' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.notifications.slackWebhook', 'Webhook URL')}
                    </label>
                    <input
                      type="url"
                      value={formData.webhook_url || ''}
                      onChange={(e) => setFormData({ ...formData, webhook_url: e.target.value })}
                      placeholder="https://hooks.slack.com/services/..."
                      className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.notifications.slackChannel', 'Channel (optional)')}
                    </label>
                    <input
                      type="text"
                      value={formData.channel || ''}
                      onChange={(e) => setFormData({ ...formData, channel: e.target.value })}
                      placeholder="#notifications"
                      className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                    />
                  </div>
                </>
              )}

              {/* DingTalk/Feishu Config */}
              {(channelType === 'dingtalk' || channelType === 'feishu') && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.notifications.webhookUrl', 'Webhook URL')}
                    </label>
                    <input
                      type="url"
                      value={formData.webhook_url || ''}
                      onChange={(e) => setFormData({ ...formData, webhook_url: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.notifications.secret', 'Secret')}
                    </label>
                    <input
                      type={showSecrets ? 'text' : 'password'}
                      value={formData.secret || ''}
                      onChange={(e) => setFormData({ ...formData, secret: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                    />
                  </div>
                </>
              )}

              {/* WeChat Work Config */}
              {channelType === 'wechat' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.notifications.corpId', 'Corp ID')}
                    </label>
                    <input
                      type="text"
                      value={formData.corp_id || ''}
                      onChange={(e) => setFormData({ ...formData, corp_id: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.notifications.agentId', 'Agent ID')}
                    </label>
                    <input
                      type="text"
                      value={formData.agent_id || ''}
                      onChange={(e) => setFormData({ ...formData, agent_id: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                      {t('settings.notifications.secret', 'Secret')}
                    </label>
                    <input
                      type={showSecrets ? 'text' : 'password'}
                      value={formData.secret || ''}
                      onChange={(e) => setFormData({ ...formData, secret: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                    />
                  </div>
                </>
              )}

              {/* Test Result */}
              {testResult && (
                <div
                  className={`p-3 rounded-lg ${
                    testResult.success
                      ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                      : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {testResult.success ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <AlertTriangle className="h-4 w-4" />
                    )}
                    <span className="text-sm">
                      {testResult.success
                        ? t('settings.notifications.testSuccess', 'Test successful!')
                        : testResult.message || t('settings.notifications.testFailed', 'Test failed')}
                    </span>
                  </div>
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-stone-200 dark:border-stone-700 flex items-center justify-between">
              {editingChannel && (
                <button
                  onClick={handleTest}
                  disabled={testChannel.isPending}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-stone-600 hover:text-stone-700 dark:text-stone-400"
                >
                  {testChannel.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                  {t('settings.notifications.testChannel', 'Send Test')}
                </button>
              )}
              <div className="flex items-center gap-3 ml-auto">
                <button
                  onClick={handleCloseModal}
                  className="px-4 py-2 text-sm font-medium text-stone-600 hover:text-stone-700 dark:text-stone-400"
                >
                  {t('common.cancel', 'Cancel')}
                </button>
                <button
                  onClick={handleSave}
                  disabled={createChannel.isPending || updateChannel.isPending}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors disabled:opacity-50"
                >
                  {(createChannel.isPending || updateChannel.isPending) && (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  )}
                  {t('common.save', 'Save')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default NotificationsSettingsPage;

/**
 * Profile Settings Page
 *
 * User profile management: avatar, nickname, locale, timezone, password.
 */

import { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Camera, User, Globe, Clock, Lock, Check, X, Loader2 } from 'lucide-react';
import { useUserProfile, useUpdateUserProfile, useChangePassword } from '../hooks';
import { SettingCard } from '../components/SettingCard';

// Supported locales - should match i18n configuration
const SUPPORTED_LOCALES = [
  { code: 'en', label: 'English' },
  { code: 'zh-CN', label: '简体中文' },
  { code: 'zh-TW', label: '繁體中文' },
  { code: 'ja', label: '日本語' },
  { code: 'ko', label: '한국어' },
  { code: 'de', label: 'Deutsch' },
  { code: 'fr', label: 'Français' },
  { code: 'es', label: 'Español' },
];

// Common timezones
const COMMON_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Tokyo',
  'Asia/Shanghai',
  'Asia/Singapore',
  'Australia/Sydney',
];

export function ProfileSettingsPage() {
  const { t, i18n } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: profile, isLoading } = useUserProfile();
  const updateProfile = useUpdateUserProfile();

  // Local state for editing
  const [nickname, setNickname] = useState<string | null>(null);
  const [isEditingNickname, setIsEditingNickname] = useState(false);

  // Password change state
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const changePassword = useChangePassword();

  const displayNickname = nickname ?? profile?.nickname ?? '';

  const handleAvatarClick = () => {
    fileInputRef.current?.click();
  };

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert(t('settings.profile.invalidImageType', 'Please select an image file'));
      return;
    }

    // Validate file size (max 2MB)
    const maxSize = 2 * 1024 * 1024;
    if (file.size > maxSize) {
      alert(t('settings.profile.imageTooLarge', 'Image must be less than 2MB'));
      return;
    }

    // Upload avatar
    const formData = new FormData();
    formData.append('avatar', file);

    try {
      await updateProfile.mutateAsync({ avatar: formData });
    } catch (error) {
      console.error('Failed to upload avatar:', error);
    }
  };

  const handleNicknameSubmit = async () => {
    if (!nickname || nickname === profile?.nickname) {
      setIsEditingNickname(false);
      return;
    }

    try {
      await updateProfile.mutateAsync({ nickname });
      setIsEditingNickname(false);
    } catch (error) {
      console.error('Failed to update nickname:', error);
    }
  };

  const handleLocaleChange = async (locale: string) => {
    try {
      await updateProfile.mutateAsync({ locale });
      i18n.changeLanguage(locale);
    } catch (error) {
      console.error('Failed to update locale:', error);
    }
  };

  const handleTimezoneChange = async (timezone: string) => {
    try {
      await updateProfile.mutateAsync({ timezone });
    } catch (error) {
      console.error('Failed to update timezone:', error);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);

    // Validate passwords
    if (newPassword.length < 8) {
      setPasswordError(t('settings.profile.passwordTooShort', 'Password must be at least 8 characters'));
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError(t('settings.profile.passwordMismatch', 'Passwords do not match'));
      return;
    }

    try {
      await changePassword.mutateAsync({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setShowPasswordForm(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      alert(t('settings.profile.passwordChanged', 'Password changed successfully'));
    } catch (error: any) {
      setPasswordError(
        error.response?.data?.detail ||
          t('settings.profile.passwordChangeFailed', 'Failed to change password')
      );
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
      {/* Avatar & Basic Info */}
      <SettingCard
        title={t('settings.profile.basicInfo', 'Basic Information')}
        description={t('settings.profile.basicInfoDesc', 'Your profile picture and display name')}
      >
        {/* Avatar */}
        <div className="flex items-center gap-6 py-4">
          <div className="relative group">
            <div className="h-20 w-20 rounded-full bg-stone-200 dark:bg-stone-700 flex items-center justify-center overflow-hidden">
              {profile?.avatar_url ? (
                <img
                  src={profile.avatar_url}
                  alt={profile.nickname || 'Avatar'}
                  className="h-full w-full object-cover"
                />
              ) : (
                <User className="h-10 w-10 text-stone-400" />
              )}
            </div>
            <button
              onClick={handleAvatarClick}
              className="absolute inset-0 rounded-full bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center"
            >
              <Camera className="h-6 w-6 text-white" />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleAvatarChange}
              className="hidden"
            />
          </div>
          <div>
            <p className="text-sm text-stone-500 dark:text-stone-400">
              {t('settings.profile.avatarHint', 'Click to upload a new avatar')}
            </p>
            <p className="text-xs text-stone-400 dark:text-stone-500 mt-1">
              {t('settings.profile.avatarRequirements', 'JPG, PNG or GIF, max 2MB')}
            </p>
          </div>
        </div>

        {/* Nickname */}
        <div className="flex items-center justify-between py-4 border-t border-stone-100 dark:border-stone-800">
          <div>
            <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
              {t('settings.profile.nickname', 'Display Name')}
            </p>
            <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
              {t('settings.profile.nicknameDesc', 'How your name appears to others')}
            </p>
          </div>
          {isEditingNickname ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={displayNickname}
                onChange={(e) => setNickname(e.target.value)}
                className="px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 w-48"
                autoFocus
              />
              <button
                onClick={handleNicknameSubmit}
                disabled={updateProfile.isPending}
                className="p-2 text-green-600 hover:text-green-700"
              >
                <Check className="h-4 w-4" />
              </button>
              <button
                onClick={() => {
                  setIsEditingNickname(false);
                  setNickname(null);
                }}
                className="p-2 text-stone-500 hover:text-stone-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button
              onClick={() => {
                setNickname(profile?.nickname || '');
                setIsEditingNickname(true);
              }}
              className="px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800 text-stone-900 dark:text-stone-100"
            >
              {profile?.nickname || t('settings.profile.setNickname', 'Set display name')}
            </button>
          )}
        </div>

        {/* Email (read-only) */}
        <div className="flex items-center justify-between py-4 border-t border-stone-100 dark:border-stone-800">
          <div>
            <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
              {t('settings.profile.email', 'Email Address')}
            </p>
            <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
              {t('settings.profile.emailDesc', 'Your login email address')}
            </p>
          </div>
          <span className="text-sm text-stone-600 dark:text-stone-400">
            {profile?.email || '-'}
          </span>
        </div>
      </SettingCard>

      {/* Locale & Timezone */}
      <SettingCard
        title={t('settings.profile.regional', 'Regional Settings')}
        description={t('settings.profile.regionalDesc', 'Language and timezone preferences')}
      >
        {/* Language */}
        <div className="flex items-center justify-between py-4">
          <div className="flex items-center gap-3">
            <Globe className="h-5 w-5 text-stone-400" />
            <div>
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.profile.language', 'Language')}
              </p>
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
                {t('settings.profile.languageDesc', 'Interface display language')}
              </p>
            </div>
          </div>
          <select
            value={profile?.locale || i18n.language || 'en'}
            onChange={(e) => handleLocaleChange(e.target.value)}
            disabled={updateProfile.isPending}
            className="px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
          >
            {SUPPORTED_LOCALES.map((locale) => (
              <option key={locale.code} value={locale.code}>
                {locale.label}
              </option>
            ))}
          </select>
        </div>

        {/* Timezone */}
        <div className="flex items-center justify-between py-4 border-t border-stone-100 dark:border-stone-800">
          <div className="flex items-center gap-3">
            <Clock className="h-5 w-5 text-stone-400" />
            <div>
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.profile.timezone', 'Timezone')}
              </p>
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
                {t('settings.profile.timezoneDesc', 'Used for date and time display')}
              </p>
            </div>
          </div>
          <select
            value={profile?.timezone || 'UTC'}
            onChange={(e) => handleTimezoneChange(e.target.value)}
            disabled={updateProfile.isPending}
            className="px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
          >
            {COMMON_TIMEZONES.map((tz) => (
              <option key={tz} value={tz}>
                {tz.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>
      </SettingCard>

      {/* Password */}
      <SettingCard
        title={t('settings.profile.security', 'Account Security')}
        description={t('settings.profile.securityDesc', 'Manage your password')}
      >
        <div className="py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Lock className="h-5 w-5 text-stone-400" />
              <div>
                <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                  {t('settings.profile.password', 'Password')}
                </p>
                <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
                  {t('settings.profile.passwordDesc', 'Change your account password')}
                </p>
              </div>
            </div>
            {!showPasswordForm && (
              <button
                onClick={() => setShowPasswordForm(true)}
                className="px-4 py-2 text-sm font-medium text-teal-600 hover:text-teal-700 border border-teal-600 hover:border-teal-700 rounded-lg transition-colors"
              >
                {t('settings.profile.changePassword', 'Change Password')}
              </button>
            )}
          </div>

          {showPasswordForm && (
            <form onSubmit={handlePasswordChange} className="mt-4 space-y-4">
              {passwordError && (
                <div className="p-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm rounded-lg">
                  {passwordError}
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  {t('settings.profile.currentPassword', 'Current Password')}
                </label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  {t('settings.profile.newPassword', 'New Password')}
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                  className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-1">
                  {t('settings.profile.confirmPassword', 'Confirm New Password')}
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
                />
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="submit"
                  disabled={changePassword.isPending}
                  className="px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors disabled:opacity-50"
                >
                  {changePassword.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    t('settings.profile.updatePassword', 'Update Password')
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowPasswordForm(false);
                    setCurrentPassword('');
                    setNewPassword('');
                    setConfirmPassword('');
                    setPasswordError(null);
                  }}
                  className="px-4 py-2 text-sm font-medium text-stone-600 hover:text-stone-700 dark:text-stone-400"
                >
                  {t('common.cancel', 'Cancel')}
                </button>
              </div>
            </form>
          )}
        </div>
      </SettingCard>
    </div>
  );
}

export default ProfileSettingsPage;

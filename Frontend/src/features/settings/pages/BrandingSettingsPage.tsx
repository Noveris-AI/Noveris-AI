/**
 * Branding Settings Page
 *
 * Manages platform branding: logo, favicon, brand name, colors.
 */

import { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Image, Type, Palette, Upload, Loader2, RotateCcw } from 'lucide-react';
import { useBrandingSettings, useUpdateBrandingSettings } from '../hooks';
import { SettingCard } from '../components/SettingCard';

// Default brand colors
const DEFAULT_PRIMARY_COLOR = '#0d9488'; // Teal-600
const DEFAULT_SECONDARY_COLOR = '#14b8a6'; // Teal-500

// Preset color options
const PRESET_COLORS = [
  { name: 'Teal', primary: '#0d9488', secondary: '#14b8a6' },
  { name: 'Blue', primary: '#2563eb', secondary: '#3b82f6' },
  { name: 'Indigo', primary: '#4f46e5', secondary: '#6366f1' },
  { name: 'Purple', primary: '#7c3aed', secondary: '#8b5cf6' },
  { name: 'Pink', primary: '#db2777', secondary: '#ec4899' },
  { name: 'Red', primary: '#dc2626', secondary: '#ef4444' },
  { name: 'Orange', primary: '#ea580c', secondary: '#f97316' },
  { name: 'Green', primary: '#16a34a', secondary: '#22c55e' },
];

export function BrandingSettingsPage() {
  const { t } = useTranslation();
  const logoInputRef = useRef<HTMLInputElement>(null);
  const faviconInputRef = useRef<HTMLInputElement>(null);

  const { data: branding, isLoading } = useBrandingSettings();
  const updateBranding = useUpdateBrandingSettings();

  // Local state
  const [brandName, setBrandName] = useState<string | null>(null);
  const [loginTitle, setLoginTitle] = useState<string | null>(null);
  const [dashboardTitle, setDashboardTitle] = useState<string | null>(null);
  const [primaryColor, setPrimaryColor] = useState<string | null>(null);
  const [secondaryColor, setSecondaryColor] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  // Initialize local state from branding data
  const displayBrandName = brandName ?? branding?.brand_name ?? '';
  const displayLoginTitle = loginTitle ?? branding?.login_page_title ?? '';
  const displayDashboardTitle = dashboardTitle ?? branding?.dashboard_title ?? '';
  const displayPrimaryColor = primaryColor ?? branding?.primary_color ?? DEFAULT_PRIMARY_COLOR;
  const displaySecondaryColor = secondaryColor ?? branding?.secondary_color ?? DEFAULT_SECONDARY_COLOR;

  const handleImageUpload = async (
    file: File,
    field: 'logo_url' | 'favicon_url'
  ) => {
    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert(t('settings.branding.invalidImageType', 'Please select an image file'));
      return;
    }

    // Validate file size (max 2MB for logo, 512KB for favicon)
    const maxSize = field === 'logo_url' ? 2 * 1024 * 1024 : 512 * 1024;
    if (file.size > maxSize) {
      alert(
        t(
          'settings.branding.imageTooLarge',
          `Image must be less than ${field === 'logo_url' ? '2MB' : '512KB'}`
        )
      );
      return;
    }

    // Upload image
    const formData = new FormData();
    formData.append(field === 'logo_url' ? 'logo' : 'favicon', file);

    try {
      await updateBranding.mutateAsync({ [field]: formData });
    } catch (error) {
      console.error(`Failed to upload ${field}:`, error);
    }
  };

  const handleSaveChanges = async () => {
    const updates: Record<string, string> = {};

    if (brandName !== null && brandName !== branding?.brand_name) {
      updates.brand_name = brandName;
    }
    if (loginTitle !== null && loginTitle !== branding?.login_page_title) {
      updates.login_page_title = loginTitle;
    }
    if (dashboardTitle !== null && dashboardTitle !== branding?.dashboard_title) {
      updates.dashboard_title = dashboardTitle;
    }
    if (primaryColor !== null && primaryColor !== branding?.primary_color) {
      updates.primary_color = primaryColor;
    }
    if (secondaryColor !== null && secondaryColor !== branding?.secondary_color) {
      updates.secondary_color = secondaryColor;
    }

    if (Object.keys(updates).length === 0) return;

    try {
      await updateBranding.mutateAsync(updates);
      setHasChanges(false);
      // Reset local state
      setBrandName(null);
      setLoginTitle(null);
      setDashboardTitle(null);
      setPrimaryColor(null);
      setSecondaryColor(null);
    } catch (error) {
      console.error('Failed to update branding:', error);
    }
  };

  const handleColorPreset = (preset: typeof PRESET_COLORS[0]) => {
    setPrimaryColor(preset.primary);
    setSecondaryColor(preset.secondary);
    setHasChanges(true);
  };

  const handleResetColors = () => {
    setPrimaryColor(DEFAULT_PRIMARY_COLOR);
    setSecondaryColor(DEFAULT_SECONDARY_COLOR);
    setHasChanges(true);
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
      {/* Logo & Favicon */}
      <SettingCard
        title={t('settings.branding.images', 'Brand Images')}
        description={t('settings.branding.imagesDesc', 'Logo and favicon for your platform')}
      >
        {/* Logo */}
        <div className="flex items-center justify-between py-4">
          <div className="flex items-center gap-4">
            <div className="h-16 w-40 bg-stone-100 dark:bg-stone-800 rounded-lg flex items-center justify-center overflow-hidden border border-stone-200 dark:border-stone-700">
              {branding?.logo_url ? (
                <img
                  src={branding.logo_url}
                  alt="Logo"
                  className="max-h-full max-w-full object-contain"
                />
              ) : (
                <Image className="h-8 w-8 text-stone-400" />
              )}
            </div>
            <div>
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.branding.logo', 'Logo')}
              </p>
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
                {t('settings.branding.logoHint', 'Recommended: 200x50px, PNG or SVG')}
              </p>
            </div>
          </div>
          <button
            onClick={() => logoInputRef.current?.click()}
            disabled={updateBranding.isPending}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-teal-600 hover:text-teal-700 border border-teal-600 hover:border-teal-700 rounded-lg transition-colors"
          >
            <Upload className="h-4 w-4" />
            {t('settings.branding.upload', 'Upload')}
          </button>
          <input
            ref={logoInputRef}
            type="file"
            accept="image/*"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleImageUpload(file, 'logo_url');
            }}
            className="hidden"
          />
        </div>

        {/* Favicon */}
        <div className="flex items-center justify-between py-4 border-t border-stone-100 dark:border-stone-800">
          <div className="flex items-center gap-4">
            <div className="h-16 w-16 bg-stone-100 dark:bg-stone-800 rounded-lg flex items-center justify-center overflow-hidden border border-stone-200 dark:border-stone-700">
              {branding?.favicon_url ? (
                <img
                  src={branding.favicon_url}
                  alt="Favicon"
                  className="h-8 w-8 object-contain"
                />
              ) : (
                <Image className="h-6 w-6 text-stone-400" />
              )}
            </div>
            <div>
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.branding.favicon', 'Favicon')}
              </p>
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
                {t('settings.branding.faviconHint', 'Recommended: 32x32px, PNG or ICO')}
              </p>
            </div>
          </div>
          <button
            onClick={() => faviconInputRef.current?.click()}
            disabled={updateBranding.isPending}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-teal-600 hover:text-teal-700 border border-teal-600 hover:border-teal-700 rounded-lg transition-colors"
          >
            <Upload className="h-4 w-4" />
            {t('settings.branding.upload', 'Upload')}
          </button>
          <input
            ref={faviconInputRef}
            type="file"
            accept="image/*,.ico"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleImageUpload(file, 'favicon_url');
            }}
            className="hidden"
          />
        </div>
      </SettingCard>

      {/* Brand Text */}
      <SettingCard
        title={t('settings.branding.text', 'Brand Text')}
        description={t('settings.branding.textDesc', 'Platform name and titles')}
        action={
          hasChanges && (
            <button
              onClick={handleSaveChanges}
              disabled={updateBranding.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {updateBranding.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                t('common.saveChanges', 'Save Changes')
              )}
            </button>
          )
        }
      >
        {/* Brand Name */}
        <div className="flex items-center justify-between py-4">
          <div className="flex items-center gap-3">
            <Type className="h-5 w-5 text-stone-400" />
            <div>
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.branding.brandName', 'Brand Name')}
              </p>
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
                {t('settings.branding.brandNameDesc', 'Platform name shown across the UI')}
              </p>
            </div>
          </div>
          <input
            type="text"
            value={displayBrandName}
            onChange={(e) => {
              setBrandName(e.target.value);
              setHasChanges(true);
            }}
            placeholder={t('settings.branding.brandNamePlaceholder', 'Enter brand name')}
            className="w-64 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
          />
        </div>

        {/* Login Page Title */}
        <div className="flex items-center justify-between py-4 border-t border-stone-100 dark:border-stone-800">
          <div className="flex items-center gap-3">
            <Type className="h-5 w-5 text-stone-400" />
            <div>
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.branding.loginTitle', 'Login Page Title')}
              </p>
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
                {t('settings.branding.loginTitleDesc', 'Title displayed on the login page')}
              </p>
            </div>
          </div>
          <input
            type="text"
            value={displayLoginTitle}
            onChange={(e) => {
              setLoginTitle(e.target.value);
              setHasChanges(true);
            }}
            placeholder={t('settings.branding.loginTitlePlaceholder', 'Welcome to Platform')}
            className="w-64 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
          />
        </div>

        {/* Dashboard Title */}
        <div className="flex items-center justify-between py-4 border-t border-stone-100 dark:border-stone-800">
          <div className="flex items-center gap-3">
            <Type className="h-5 w-5 text-stone-400" />
            <div>
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.branding.dashboardTitle', 'Dashboard Title')}
              </p>
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
                {t('settings.branding.dashboardTitleDesc', 'Title shown in the dashboard header')}
              </p>
            </div>
          </div>
          <input
            type="text"
            value={displayDashboardTitle}
            onChange={(e) => {
              setDashboardTitle(e.target.value);
              setHasChanges(true);
            }}
            placeholder={t('settings.branding.dashboardTitlePlaceholder', 'Dashboard')}
            className="w-64 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100"
          />
        </div>
      </SettingCard>

      {/* Brand Colors */}
      <SettingCard
        title={t('settings.branding.colors', 'Brand Colors')}
        description={t('settings.branding.colorsDesc', 'Primary and accent colors')}
        action={
          <button
            onClick={handleResetColors}
            className="inline-flex items-center gap-2 px-3 py-2 text-sm text-stone-600 hover:text-stone-700 dark:text-stone-400"
          >
            <RotateCcw className="h-4 w-4" />
            {t('settings.branding.resetColors', 'Reset to Default')}
          </button>
        }
      >
        {/* Color Presets */}
        <div className="py-4">
          <p className="text-sm font-medium text-stone-900 dark:text-stone-100 mb-3">
            {t('settings.branding.presets', 'Color Presets')}
          </p>
          <div className="flex flex-wrap gap-2">
            {PRESET_COLORS.map((preset) => (
              <button
                key={preset.name}
                onClick={() => handleColorPreset(preset)}
                className="flex items-center gap-2 px-3 py-2 border border-stone-200 dark:border-stone-700 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800 transition-colors"
              >
                <div
                  className="h-4 w-4 rounded-full"
                  style={{ backgroundColor: preset.primary }}
                />
                <span className="text-sm text-stone-700 dark:text-stone-300">
                  {preset.name}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Custom Colors */}
        <div className="flex items-center justify-between py-4 border-t border-stone-100 dark:border-stone-800">
          <div className="flex items-center gap-3">
            <Palette className="h-5 w-5 text-stone-400" />
            <div>
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.branding.primaryColor', 'Primary Color')}
              </p>
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
                {t('settings.branding.primaryColorDesc', 'Main accent color for buttons and links')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={displayPrimaryColor}
              onChange={(e) => {
                setPrimaryColor(e.target.value);
                setHasChanges(true);
              }}
              className="h-10 w-10 rounded cursor-pointer border border-stone-300 dark:border-stone-600"
            />
            <input
              type="text"
              value={displayPrimaryColor}
              onChange={(e) => {
                setPrimaryColor(e.target.value);
                setHasChanges(true);
              }}
              className="w-24 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 font-mono"
            />
          </div>
        </div>

        <div className="flex items-center justify-between py-4 border-t border-stone-100 dark:border-stone-800">
          <div className="flex items-center gap-3">
            <Palette className="h-5 w-5 text-stone-400" />
            <div>
              <p className="text-sm font-medium text-stone-900 dark:text-stone-100">
                {t('settings.branding.secondaryColor', 'Secondary Color')}
              </p>
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
                {t('settings.branding.secondaryColorDesc', 'Hover states and highlights')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={displaySecondaryColor}
              onChange={(e) => {
                setSecondaryColor(e.target.value);
                setHasChanges(true);
              }}
              className="h-10 w-10 rounded cursor-pointer border border-stone-300 dark:border-stone-600"
            />
            <input
              type="text"
              value={displaySecondaryColor}
              onChange={(e) => {
                setSecondaryColor(e.target.value);
                setHasChanges(true);
              }}
              className="w-24 px-3 py-2 text-sm border border-stone-300 dark:border-stone-600 rounded-lg bg-white dark:bg-stone-800 text-stone-900 dark:text-stone-100 font-mono"
            />
          </div>
        </div>

        {/* Save button for colors */}
        {hasChanges && (
          <div className="py-4 border-t border-stone-100 dark:border-stone-800">
            <button
              onClick={handleSaveChanges}
              disabled={updateBranding.isPending}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {updateBranding.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                t('common.saveChanges', 'Save Changes')
              )}
            </button>
          </div>
        )}

        {/* Preview */}
        <div className="py-4 border-t border-stone-100 dark:border-stone-800">
          <p className="text-sm font-medium text-stone-900 dark:text-stone-100 mb-3">
            {t('settings.branding.preview', 'Preview')}
          </p>
          <div className="flex items-center gap-4">
            <button
              style={{ backgroundColor: displayPrimaryColor }}
              className="px-4 py-2 text-sm font-medium text-white rounded-lg"
            >
              {t('settings.branding.primaryButton', 'Primary Button')}
            </button>
            <button
              style={{
                backgroundColor: 'transparent',
                borderColor: displayPrimaryColor,
                color: displayPrimaryColor,
              }}
              className="px-4 py-2 text-sm font-medium border rounded-lg"
            >
              {t('settings.branding.secondaryButton', 'Secondary Button')}
            </button>
            <a
              href="#"
              style={{ color: displayPrimaryColor }}
              className="text-sm font-medium hover:underline"
              onClick={(e) => e.preventDefault()}
            >
              {t('settings.branding.linkText', 'Link Text')}
            </a>
          </div>
        </div>
      </SettingCard>
    </div>
  );
}

export default BrandingSettingsPage;

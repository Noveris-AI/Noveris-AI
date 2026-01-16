/**
 * Settings Feature Module
 *
 * Comprehensive settings management for the platform:
 * - Authentication settings (email/password, SSO)
 * - Profile management
 * - Branding customization
 * - Security policies
 * - Notification channels
 * - Feature flags
 */

// Pages
export {
  SettingsLayout,
  AuthSettingsPage,
  ProfileSettingsPage,
  BrandingSettingsPage,
  SecuritySettingsPage,
  NotificationsSettingsPage,
  AdvancedSettingsPage,
} from './pages';

// Components
export { SettingCard, SettingRow, SSOProviderModal } from './components';

// Hooks
export * from './hooks';

// Types
export * from './types';

// API
export * from './api';

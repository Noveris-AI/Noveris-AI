import { Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { I18nextProvider } from 'react-i18next'
import i18n from './i18n/config'
import { ThemeProvider } from './shared/components/theme/ThemeProvider'
import { AuthProvider } from './features/auth/contexts/AuthContext'
import { useAuth } from './features/auth/hooks/useAuth'
import { ProtectedRoute } from './shared/components/routing/ProtectedRoute'
import AuthLayout from './shared/components/layout/AuthLayout'
import { DashboardLayout } from './features/dashboard/components'
import LoginPage from './features/auth/pages/LoginPage'
import RegisterPage from './features/auth/pages/RegisterPage'
import ForgotPasswordPage from './features/auth/pages/ForgotPasswordPage'
import ResetPasswordPage from './features/auth/pages/ResetPasswordPage'
import DashboardPage from './features/dashboard/DashboardPage'
import DocsPage from './features/docs/DocsPage'
import { ModelMarketPage } from './features/model-market/ModelMarketPage'
import { NodeListPage, NodeDetailPage, AddNodePage } from './features/nodes/pages'
import { JobListPage, JobDetailPage } from './features/jobs/pages'
import { DeploymentListPage, CreateDeploymentPage, DeploymentDetailPage } from './features/deployments/pages'
import { GatewayLayout } from './features/gateway/components'
import {
  GatewayOverviewPage,
  UpstreamsPage,
  VirtualModelsPage,
  RoutesPage,
  APIKeysPage,
  RequestLogsPage,
} from './features/gateway/pages'
import { ChatPage } from './features/chat'
import { PlaygroundPage } from './features/playground'
import {
  AuthzProvider,
  AuthzLayout,
  PermissionsPage,
  ModulesPage,
  RolesPage,
  UsersPage,
  AuditLogsPage,
} from './features/authz'
import {
  SettingsLayout,
  AuthSettingsPage,
  ProfileSettingsPage,
  BrandingSettingsPage,
  SecuritySettingsPage,
  NotificationsSettingsPage,
  AdvancedSettingsPage,
} from './features/settings'
import {
  MonitoringPage,
} from './features/monitoring'

// Placeholder pages for other menu items
const PlaceholderPage = ({ title }: { title: string }) => (
  <div className="flex items-center justify-center h-96">
    <div className="text-center">
      <h2 className="text-xl font-semibold text-stone-900 dark:text-stone-100">{title}</h2>
      <p className="text-stone-600 dark:text-stone-400 mt-2">功能开发中...</p>
    </div>
  </div>
)

// Loading component for i18n
const LoadingFallback = () => (
  <div className="min-h-screen flex items-center justify-center">
    <div className="text-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600 mx-auto"></div>
      <p className="mt-2 text-stone-600">Loading...</p>
    </div>
  </div>
)

// Root redirect component - redirects based on auth status
const RootRedirect = () => {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <LoadingFallback />
  }

  // Redirect to dashboard if authenticated, otherwise to login
  return <Navigate to={isAuthenticated ? '/dashboard/homepage' : '/auth/login'} replace />
}

function App() {
  return (
    <I18nextProvider i18n={i18n}>
      <Suspense fallback={<LoadingFallback />}>
        <ThemeProvider>
          <AuthProvider>
            <AuthzProvider>
              <Routes>
                {/* Auth routes */}
                <Route path="/auth" element={<AuthLayout />}>
                  <Route path="login" element={<LoginPage />} />
                  <Route path="register" element={<RegisterPage />} />
                  <Route path="forgot" element={<ForgotPasswordPage />} />
                  <Route path="reset" element={<ResetPasswordPage />} />
                </Route>

                {/* Dashboard routes with layout - Protected */}
                <Route
                  path="/dashboard"
                  element={
                    <ProtectedRoute>
                      <DashboardLayout />
                    </ProtectedRoute>
                  }
                >
              <Route path="homepage" element={<DashboardPage />} />
              <Route path="monitoring" element={<MonitoringPage />} />
              <Route path="nodes" element={<NodeListPage />} />
              <Route path="nodes/add" element={<AddNodePage />} />
              <Route path="nodes/:nodeId" element={<NodeDetailPage />} />
              <Route path="jobs" element={<JobListPage />} />
              <Route path="jobs/:jobId" element={<JobDetailPage />} />
              <Route path="market" element={<ModelMarketPage />} />
              <Route path="deployment" element={<DeploymentListPage />} />
              <Route path="deployment/create" element={<CreateDeploymentPage />} />
              <Route path="deployment/:deploymentId" element={<DeploymentDetailPage />} />
              <Route path="forwarding" element={<GatewayLayout />}>
                <Route index element={<GatewayOverviewPage />} />
                <Route path="upstreams" element={<UpstreamsPage />} />
                <Route path="models" element={<VirtualModelsPage />} />
                <Route path="routes" element={<RoutesPage />} />
                <Route path="api-keys" element={<APIKeysPage />} />
                <Route path="logs" element={<RequestLogsPage />} />
              </Route>
              <Route path="chat" element={<ChatPage />} />
              <Route path="playground" element={<PlaygroundPage />} />
              <Route path="permissions" element={<AuthzLayout />}>
                <Route index element={<PermissionsPage />} />
                <Route path="modules" element={<ModulesPage />} />
                <Route path="roles" element={<RolesPage />} />
                <Route path="users" element={<UsersPage />} />
                <Route path="audit" element={<AuditLogsPage />} />
              </Route>
              <Route path="settings" element={<SettingsLayout />}>
                <Route index element={<AuthSettingsPage />} />
                <Route path="profile" element={<ProfileSettingsPage />} />
                <Route path="branding" element={<BrandingSettingsPage />} />
                <Route path="notifications" element={<NotificationsSettingsPage />} />
                <Route path="security" element={<SecuritySettingsPage />} />
                <Route path="advanced" element={<AdvancedSettingsPage />} />
              </Route>
              <Route path="profile" element={<Navigate to="/dashboard/settings/profile" replace />} />
              <Route path="Docs" element={<DocsPage />} />
            </Route>

            {/* Redirect root based on auth status */}
            <Route path="/" element={<RootRedirect />} />

            {/* Redirect unknown routes based on auth status */}
            <Route path="*" element={<RootRedirect />} />
          </Routes>
          </AuthzProvider>
        </AuthProvider>
      </ThemeProvider>
    </Suspense>
  </I18nextProvider>
)
}

export default App

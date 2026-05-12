/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { MainLayout } from './components/layout/MainLayout';
import DashboardPage from './pages/Dashboard';
import ViolationReportsPage from './pages/ViolationReports';
import PolicyCompilerPage from './pages/PolicyCompiler';
import UserManagementPage from './pages/UserManagement';
import AuditLogsPage from './pages/AuditLogs';
import SystemSettingsPage from './pages/SystemSettings';

// Auth Pages
import { RoleSelectionPage } from './pages/auth/RoleSelection';
import { AdminSetupPage } from './pages/auth/AdminSetup';
import { EmployeeSignupPage } from './pages/auth/EmployeeSignup';
import { LoginPage } from './pages/auth/Login';

// User Pages
import { ChatbotPage } from './pages/ChatbotPage';

const ProtectedRoute = ({ children, allowedRoles }: { children: React.ReactNode, allowedRoles?: string[] }) => {
  const { user, isLoading } = useAuth();

  if (isLoading) return <div className="h-screen w-screen flex items-center justify-center font-black text-2xl animate-pulse text-primary">LOADING...</div>;
  if (!user) return <Navigate to="/auth/roles" replace />;
  if (allowedRoles && !allowedRoles.includes(user.role)) return <Navigate to="/" replace />;

  return <>{children}</>;
};

const RootRedirect = () => {
  const { user } = useAuth();
  if (!user) return <Navigate to="/auth/roles" replace />;
  if (user.role === 'ADMIN') return <Navigate to="/admin/dashboard" replace />;
  return <Navigate to="/chat" replace />;
};

function AppContent() {
  return (
    <Router>
      <Routes>
        {/* Auth Routes */}
        <Route path="/auth/roles" element={<RoleSelectionPage />} />
        <Route path="/signup/admin" element={<AdminSetupPage />} />
        <Route path="/signup/employee" element={<EmployeeSignupPage />} />
        <Route path="/login" element={<LoginPage />} />

        {/* Root Redirect Logic */}
        <Route path="/" element={<RootRedirect />} />

        {/* Employee/User Routes */}
        <Route
          path="/chat"
          element={
            <ProtectedRoute allowedRoles={['EMPLOYEE', 'ADMIN']}>
              <ChatbotPage />
            </ProtectedRoute>
          }
        />

        {/* Admin Section */}
        <Route
          path="/admin/*"
          element={
            <ProtectedRoute allowedRoles={['ADMIN']}>
              <MainLayout>
                <Routes>
                  <Route path="dashboard" element={<DashboardPage />} />
                  <Route path="reports" element={<ViolationReportsPage />} />
                  <Route path="policy" element={<PolicyCompilerPage />} />
                  <Route path="users" element={<UserManagementPage />} />
                  <Route path="logs" element={<AuditLogsPage />} />
                  <Route path="settings" element={<SystemSettingsPage />} />
                  <Route path="*" element={<Navigate to="dashboard" replace />} />
                </Routes>
              </MainLayout>
            </ProtectedRoute>
          }
        />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

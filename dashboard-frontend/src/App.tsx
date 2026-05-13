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

// Pages
import RoleSelectionPage from './pages/auth/RoleSelection';
import { ChatbotPage } from './pages/ChatbotPage';

/**
 * simplified routing without backend auth enforcement
 */
const AppContent = () => {
  const { user } = useAuth();

  return (
    <Router>
      <Routes>
        {/* Entry Selection Page */}
        <Route path="/" element={<RoleSelectionPage />} />
        <Route path="/auth/roles" element={<Navigate to="/" replace />} />

        {/* User Path: Chatbot */}
        <Route
          path="/chat"
          element={<ChatbotPage />}
        />

        {/* Admin Path: Dashboard and Management */}
        <Route
          path="/admin/*"
          element={
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

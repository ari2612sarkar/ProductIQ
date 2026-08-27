import { Routes, Route, Navigate } from 'react-router-dom'
import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { DashboardPage } from '@/pages/DashboardPage'
import { MetricsPage } from '@/pages/MetricsPage'
import { AnomaliesPage } from '@/pages/AnomaliesPage'
import { InvestigationsPage } from '@/pages/InvestigationsPage'
import { InvestigationDetailPage } from '@/pages/InvestigationDetailPage'
import { ExperimentsPage } from '@/pages/ExperimentsPage'
import { FeedbackPage } from '@/pages/FeedbackPage'
import { SettingsPage } from '@/pages/SettingsPage'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route element={<DashboardLayout />}>
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="metrics" element={<MetricsPage />} />
        <Route path="anomalies" element={<AnomaliesPage />} />
        <Route path="investigations" element={<InvestigationsPage />} />
        <Route path="investigations/:id" element={<InvestigationDetailPage />} />
        <Route path="experiments" element={<ExperimentsPage />} />
        <Route path="feedback" element={<FeedbackPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
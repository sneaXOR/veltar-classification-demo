import { Route, Routes } from 'react-router-dom'

import { AppLayout } from './components/layout/AppLayout'
import { ClientsPage } from './pages/ClientsPage'
import { DashboardPage } from './pages/DashboardPage'
import { DocumentDetailPage } from './pages/DocumentDetailPage'
import { ReviewPage } from './pages/ReviewPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="upload" element={<DashboardPage />} />
        <Route path="clients" element={<ClientsPage />} />
        <Route path="reviews" element={<ReviewPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="documents/:documentId" element={<DocumentDetailPage />} />
      </Route>
    </Routes>
  )
}

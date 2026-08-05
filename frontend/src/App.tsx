import { Navigate, Route, Routes } from 'react-router-dom'

import { Nav } from './components/Nav'
import { Placeholder } from './components/ui'
import { JobDetailPage } from './pages/JobDetailPage'
import { JobsPage } from './pages/JobsPage'
import { SettingsPage } from './pages/SettingsPage'

export default function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/jobs" replace />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/jobs/:id" element={<JobDetailPage />} />
          <Route
            path="/profile"
            element={
              <Placeholder
                title="Profile"
                step="Master CV upload and the structured, editable profile arrive in step 12."
              />
            }
          />
          <Route
            path="/applications"
            element={
              <Placeholder
                title="Applications"
                step="Generated CVs and cover letters appear here from steps 15–17."
              />
            }
          />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/jobs" replace />} />
        </Routes>
      </main>
    </div>
  )
}

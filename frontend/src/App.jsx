import { useEffect } from 'react'
import { Route, Routes } from 'react-router-dom'
import TopNav from './components/TopNav.jsx'
import BoardPage from './pages/BoardPage.jsx'
import DoctorsPage from './pages/DoctorsPage.jsx'
import PatientsPage from './pages/PatientsPage.jsx'
import SchedulePage from './pages/SchedulePage.jsx'
import { api } from './api/client.js'
import { setClinicTz } from './utils/time.js'

const VERSION = import.meta.env.VITE_APP_VERSION || 'dev'

export default function App() {
  useEffect(() => {
    api.config().then((c) => setClinicTz(c.clinic_tz)).catch(() => {})
  }, [])

  return (
    <div className="shell">
      <TopNav />
      <main className="page">
        <Routes>
          <Route path="/" element={<BoardPage />} />
          <Route path="/schedule" element={<SchedulePage />} />
          <Route path="/patients" element={<PatientsPage />} />
          <Route path="/doctors" element={<DoctorsPage />} />
        </Routes>
      </main>
      <footer className="footer">
        Waiting Room · build <code>{VERSION.slice(0, 7)}</code>
      </footer>
    </div>
  )
}

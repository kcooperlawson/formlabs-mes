import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth/AuthProvider'
import { LoginPage } from './auth/LoginPage'
import { ManagerShell } from './ManagerShell'
import { OperatorFormPage } from './OperatorFormPage'
import { TvDashboardPage } from './tv/TvDashboardPage'

// Mirrors Home.py's own post-login redirect: operators and packers go
// straight to the Operator Form and never see this routing decision at
// all ("if user.role in ['operator','packer']: switch_page(...)");
// everyone else lands on the manager shell.
//
// /tv is the one page in this app that is a real route rather than a
// ManagerShell tab: it is a wall display, deliberately drawn with no top
// nav (see TvDashboardPage's own note), meant to be opened as its own
// browser tab/window on a screen mounted on the floor - not reached by
// clicking through the manager's own tab strip.
export default function App() {
  const { user, isLoading } = useAuth()

  if (isLoading) return null
  if (!user) return <LoginPage />

  return (
    <Routes>
      <Route
        path="/tv"
        element={user.role === 'manager' || user.role === 'admin' ? <TvDashboardPage /> : <Navigate to="/" replace />}
      />
      {/* A real route, not a ManagerShell tab: mirrors ui_shell.py's own
          nav_menu(), which offers "Operator Form" / "Workstation" to every
          role unconditionally, including managers and admins - who reach it
          from the Manager Cockpit sidebar to test or log on an operator's
          behalf (see OperatorFormPage's own Debug Mode bar). */}
      <Route path="/operator-form" element={<OperatorFormPage />} />
      <Route
        path="*"
        element={user.role === 'operator' || user.role === 'packer' ? <OperatorFormPage /> : <ManagerShell />}
      />
    </Routes>
  )
}

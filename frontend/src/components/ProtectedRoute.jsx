import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute({ children }) {
  const { user, loading, mustChangePassword } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-ink">
        <div className="w-8 h-8 border-2 border-leaf border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  if (mustChangePassword && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />
  }

  // A platform-level account (super admin) has no school_id, the entire
  // regular school app (dashboard, students, everything school-scoped)
  // is structurally inapplicable to them, since almost every endpoint
  // requires a school context. Route them to the dedicated platform view
  // instead of letting them land on a school dashboard full of blank/403
  // sections.
  const isPlatformAccount = user.school_id === null || user.school_id === undefined
  if (isPlatformAccount && location.pathname !== '/platform') {
    return <Navigate to="/platform" replace />
  }
  if (!isPlatformAccount && location.pathname === '/platform') {
    return <Navigate to="/" replace />
  }

  return children
}


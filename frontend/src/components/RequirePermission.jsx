import { Link } from 'react-router-dom'
import { Lock } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

/**
 * Gates a route by permission. Previously every nested route under
 * AppShell was reachable by any logged-in user regardless of role, the
 * sidebar just didn't show a link, and individual API calls happened to
 * 403. No data ever actually leaked (every endpoint already checks its
 * own permission correctly), but landing on a page you have no access to
 * showed a half-broken screen with silently-failing widgets instead of a
 * clean, honest "you don't have access to this" message.
 *
 * perm: a single permission string. perms: an array, any one of which is
 * sufficient (mirrors the Sidebar NAV shape exactly). Neither prop means
 * "every authenticated user may see this" (Dashboard, Messages,
 * Announcements, Profile).
 */
export default function RequirePermission({ perm, perms, orClassMaster, children }) {
  const { hasPermission, user } = useAuth()

  const allowed = (orClassMaster && user?.is_class_master) || (perms ? perms.some((p) => hasPermission(p)) : !perm || hasPermission(perm))
  if (allowed) return children

  return (
    <div className="max-w-md mx-auto mt-16 card flex flex-col items-center text-center py-12 px-6 bg-ruled">
      <div className="w-11 h-11 rounded-lg border border-dashed border-white/15 flex items-center justify-center mb-4 bg-ink/40">
        <Lock size={18} className="text-slate" />
      </div>
      <p className="font-display font-medium text-paper mb-1">You don't have access to this page</p>
      <p className="text-sm text-slate max-w-sm mb-5">
        This section isn't part of your role. If you think that's wrong, ask your school administrator.
      </p>
      <Link to="/" className="btn-secondary text-xs">Back to dashboard</Link>
    </div>
  )
}

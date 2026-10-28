import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api } from '../lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [permissions, setPermissions] = useState([])
  const [mustChangePassword, setMustChangePassword] = useState(false)
  const [loading, setLoading] = useState(true)

  const loadMe = useCallback(async () => {
    const { access } = api.getTokens()
    if (!access) {
      setLoading(false)
      return
    }
    try {
      const me = await api.get('/api/auth/me')
      setUser(me)
      // Permissions live in the JWT, not /me, decode the access token payload.
      const payload = JSON.parse(atob(access.split('.')[1]))
      setPermissions(payload.permissions || [])
    } catch {
      api.clearTokens()
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadMe()
  }, [loadMe])

  const login = async (email, password) => {
    const data = await api.post('/api/auth/login', { email, password })
    api.setTokens(data)
    // The login response only has the basics; /me adds the staff link, address and class master duty.
    try { setUser(await api.get('/api/auth/me')) } catch { setUser(data.user) }
    setMustChangePassword(data.must_change_password)
    const payload = JSON.parse(atob(data.access_token.split('.')[1]))
    setPermissions(payload.permissions || [])
    return data
  }

  const logout = async () => {
    try {
      await api.post('/api/auth/logout')
    } catch {
      // best-effort, clear local state regardless
    }
    api.clearTokens()
    // Force a full reload rather than clearing React state in place. This
    // guarantees every component in the tree remounts from scratch for the
    // next login, no per-page fetched data (dashboard stats, lists,
    // notifications) can ever carry over and be shown to the next person
    // who logs in on this device. Found as a real bug during testing: one
    // user's last-seen screen was briefly visible to the next person who
    // logged in.
    window.location.href = '/login'
  }

  const completePasswordChange = () => setMustChangePassword(false)

  const hasPermission = (code) => permissions.includes('*') || permissions.includes(code)
  const hasRole = (name) => user?.roles?.includes(name)

  return (
    <AuthContext.Provider
      value={{ user, permissions, loading, mustChangePassword, login, logout, hasPermission, hasRole, completePasswordChange, refreshMe: loadMe }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

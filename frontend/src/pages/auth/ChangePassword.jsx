import { useState } from 'react'
import { motion } from 'framer-motion'
import { ShieldCheck } from 'lucide-react'
import { api } from '../../lib/api'
import { PasswordInput } from '../../components/ui'
import { useAuth } from '../../context/AuthContext'

export default function ChangePassword() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const { completePasswordChange } = useAuth()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (next !== confirm) {
      setError('New passwords do not match')
      return
    }
    if (next.length < 8) {
      setError('New password must be at least 8 characters')
      return
    }
    setSubmitting(true)
    try {
      const res = await api.post('/api/auth/change-password', { current_password: current, new_password: next })
      // Changing the password signs every old session out, so keep this device signed in with the fresh one.
      if (res?.access_token) api.setTokens(res)
      completePasswordChange()
      // Hard reload, same reasoning as Login, see AuthContext.jsx logout.
      window.location.href = '/'
    } catch (err) {
      setError(err.data?.error || 'Could not change password')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen w-full bg-ink flex items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md card p-7"
      >
        <div className="w-10 h-10 rounded-lg bg-marigold/15 flex items-center justify-center mb-5">
          <ShieldCheck size={20} className="text-marigold" />
        </div>
        <h1 className="font-display text-2xl font-semibold tracking-tight mb-2">Set a new password</h1>
        <p className="text-slate text-sm mb-6">
          For security, you need to change your password before continuing.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Current password</label>
            <PasswordInput required value={current} onChange={(e) => setCurrent(e.target.value)} />
          </div>
          <div>
            <label className="label">New password</label>
            <PasswordInput required value={next} onChange={(e) => setNext(e.target.value)} />
          </div>
          <div>
            <label className="label">Confirm new password</label>
            <PasswordInput required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button type="submit" disabled={submitting} className="btn-primary w-full">
            {submitting ? 'Updating…' : 'Update password'}
          </button>
        </form>
      </motion.div>
    </div>
  )
}

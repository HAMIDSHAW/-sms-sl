import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { GraduationCap, ArrowRight, AlertCircle } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { PasswordInput } from '../../components/ui'
import LoginScene from '../../three/LoginScene'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const data = await login(email, password)
      // Full reload rather than client-side navigation, guarantees no
      // component anywhere in the tree can be carrying fetched data from
      // whoever used this device last (see AuthContext.jsx logout for the
      // matching half of this fix).
      const target = data.must_change_password ? '/change-password' : (location.state?.from || '/')
      window.location.href = target
    } catch (err) {
      setError(err.data?.error || 'Invalid email or password')
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen w-full relative overflow-hidden bg-ink flex items-center justify-center px-6">
      {/* Signature 3D element, sits behind everything, ambient not distracting */}
      <div className="hidden md:block absolute right-0 top-0 bottom-0 w-1/2 opacity-90">
        <LoginScene />
      </div>
      <div className="absolute inset-0 bg-gradient-to-r from-ink via-ink/95 md:via-ink/70 to-transparent pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-10 w-full max-w-md"
      >
        <div className="flex items-center gap-2.5 mb-8">
          <div className="w-9 h-9 rounded-lg bg-leaf flex items-center justify-center">
            <GraduationCap size={20} className="text-ink" strokeWidth={2.5} />
          </div>
          <span className="font-display font-semibold text-lg tracking-tight">SchoolOS</span>
        </div>

        <p className="eyebrow mb-2">Sign in</p>
        <h1 className="font-display text-3xl font-semibold tracking-tight mb-2">Welcome back.</h1>
        <p className="text-slate text-sm mb-8">Enter your details to reach your dashboard.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label" htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              autoFocus
              className="input"
              placeholder="you@school.example.sl"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="password">Password</label>
            <PasswordInput
              id="password"
              required
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="flex items-center gap-2 text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2.5 overflow-hidden"
              >
                <AlertCircle size={16} className="shrink-0" />
                <span>{error}</span>
              </motion.div>
            )}
          </AnimatePresence>

          <button type="submit" disabled={submitting} className="btn-primary w-full mt-2">
            {submitting ? 'Signing in…' : 'Sign in'}
            {!submitting && <ArrowRight size={16} />}
          </button>

          <button
            type="button"
            onClick={() => navigate('/forgot-password')}
            className="w-full text-center text-sm text-slate hover:text-paper transition-colors pt-1"
          >
            Forgot your password?
          </button>
        </form>
      </motion.div>
    </div>
  )
}

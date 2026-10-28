import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { GraduationCap, ArrowLeft, KeyRound } from 'lucide-react'

/**
 * There is no email service connected yet, so nothing can be sent. Rather than promise an email that
 * never arrives, this page says what actually works: the school administrator issues a temporary
 * password, and the user is asked to choose their own at next sign in.
 */
export default function ForgotPassword() {
  return (
    <div className="min-h-screen w-full bg-ink flex items-center justify-center px-6">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <div className="flex items-center gap-2.5 mb-8">
          <div className="w-9 h-9 rounded-lg bg-leaf flex items-center justify-center" aria-hidden="true">
            <GraduationCap size={20} className="text-ink" strokeWidth={2.5} />
          </div>
          <span className="font-display font-semibold text-lg tracking-tight">SchoolOS</span>
        </div>

        <div className="card p-6">
          <KeyRound size={32} className="mb-3 text-leaf" aria-hidden="true" />
          <h1 className="font-display text-xl font-semibold mb-2">Forgot your password?</h1>
          <p className="text-slate text-sm mb-3">
            Password reset by email is not available yet. Please contact your school administrator. They can
            give you a temporary password, and you will be asked to choose your own the next time you sign in.
          </p>
          <Link to="/login" className="btn-secondary w-full mt-4">
            <ArrowLeft size={16} /> Back to sign in
          </Link>
        </div>
      </motion.div>
    </div>
  )
}

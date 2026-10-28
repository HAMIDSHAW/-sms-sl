import { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bell } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'

// Where a notification should take you when you click it.
export function destination(n) {
  const id = n.related_entity_id
  switch (n.related_entity_type) {
    case 'assignment': return id ? `/assignments/${id}` : '/assignments'
    case 'invoice': case 'payment': return '/finance'
    case 'leave_request': case 'payslip': return '/hr'
    case 'message': return '/messages'
    case 'discipline': return '/discipline'
    case 'announcement': return '/announcements'
    case 'result': return '/exams'
    case 'attendance': case 'timetable_reminder': return '/attendance'
    default: return null
  }
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const ref = useRef(null)
  const navigate = useNavigate()
  const location = useLocation()

  // Two things make "mark as read" reliable. A newer request always wins over an older one still in
  // flight, and anything read on this screen stays read here even if a slower, older answer from the
  // server (fetched before the click reached it) arrives afterwards and says it is unread.
  const latest = useRef(0)
  const readHere = useRef(new Set())

  const load = useCallback(() => {
    const ticket = ++latest.current
    return api.get('/api/notifications')
      .then((list) => {
        if (ticket !== latest.current) return
        setNotifications(list.map((n) => (readHere.current.has(n.id) ? { ...n, is_read: true } : n)))
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    load()
    const poll = () => { if (document.visibilityState !== 'hidden') load() }
    const interval = setInterval(poll, 30000)
    return () => clearInterval(interval)
  }, [load])

  // Close whenever the person goes somewhere, presses Escape, or presses anywhere outside it.
  // pointerdown (not mousedown) so a tap on a phone counts, and captured so nothing on the
  // page can swallow it before we see it.
  useEffect(() => { setOpen(false) }, [location.pathname])
  useEffect(() => {
    if (!open) return undefined
    const outside = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', outside, true)
    document.addEventListener('focusin', outside, true)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', outside, true)
      document.removeEventListener('focusin', outside, true)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const unread = notifications.filter((n) => !n.is_read).length

  const markRead = (n) => {
    if (n.is_read) return
    readHere.current.add(n.id)
    setNotifications((list) => list.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)))
    api.patch(`/api/notifications/${n.id}/read`).catch(() => {
      readHere.current.delete(n.id) // the server did not take it, so do not pretend it did
      load()
    })
  }

  const openNotification = (n) => {
    markRead(n)
    setOpen(false) // always closes, whether or not it leads somewhere
    const to = destination(n)
    if (to) navigate(to)
  }

  const markAllRead = () => {
    const ids = notifications.filter((n) => !n.is_read).map((n) => n.id)
    ids.forEach((id) => readHere.current.add(id))
    setNotifications((list) => list.map((n) => ({ ...n, is_read: true })))
    api.post('/api/notifications/read-all').catch(() => {
      ids.forEach((id) => readHere.current.delete(id))
      load()
    })
  }

  const toggle = () => {
    setOpen((o) => {
      if (!o) load() // fresh list every time it opens
      return !o
    })
  }

  return (
    <div className="relative" ref={ref}>
      <button onClick={toggle} aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'} aria-expanded={open} aria-haspopup="true" className="relative w-9 h-9 rounded-lg hover:bg-white/5 flex items-center justify-center transition-colors">
        <Bell size={18} className="text-slate" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-marigold text-ink text-[10px] font-bold flex items-center justify-center">{unread > 9 ? '9+' : unread}</span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            role="region" aria-label="Notifications"
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 mt-2 w-80 max-w-[calc(100vw-2rem)] card p-0 overflow-hidden z-40"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-rule">
              <p className="font-display font-semibold text-sm">Notifications</p>
              {unread > 0 && (
                <button onClick={markAllRead} className="text-xs text-leaf hover:underline">Mark all read</button>
              )}
            </div>
            <div className="max-h-80 overflow-y-auto divide-y divide-rule">
              {notifications.length === 0 ? (
                <p className="text-xs text-slate text-center py-8">No notifications</p>
              ) : (
                notifications.map((n) => (
                  <button
                    key={n.id} onClick={() => openNotification(n)}
                    className={`w-full text-left px-4 py-3 hover:bg-white/[0.04] transition-colors ${!n.is_read ? 'bg-leaf/5' : ''}`}
                  >
                    <p className="text-sm font-medium flex items-center gap-2">
                      {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-marigold shrink-0" />}
                      {n.title}
                    </p>
                    {n.body && <p className="text-xs text-slate mt-0.5">{n.body}</p>}
                    <p className="text-[11px] text-slate mt-1">{new Date(n.created_at).toLocaleString()}</p>
                  </button>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

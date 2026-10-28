import { useEffect, useRef, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Menu } from 'lucide-react'
import Sidebar from './Sidebar'
import NotificationBell from './NotificationBell'
import ErrorBoundary from '../ErrorBoundary'
import { useChildSelection } from '../../context/ChildContext'
import { Avatar } from '../ui'

/** Always tells a parent which child the page is about, and lets them switch from any page. */
function ChildBanner() {
  const ctx = useChildSelection()
  if (!ctx || !ctx.myChildren.length) return null
  const { myChildren, selectedChildId, setSelectedChildId } = ctx
  const current = myChildren.find((c) => c.id === selectedChildId) || myChildren[0]
  return (
    <div className="mb-5 card px-4 py-3 flex flex-wrap items-center gap-3 border-leaf/25 print:hidden">
      <Avatar src={current.photo_url} name={`${current.first_name} ${current.last_name}`} size={34} />
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wider text-slate">You are viewing</p>
        <p className="text-sm font-semibold truncate">
          {current.first_name} {current.last_name}
          {current.class_name ? <span className="text-slate font-normal">, {current.class_name}</span> : null}
        </p>
      </div>
      {myChildren.length > 1 && (
        <div className="ml-auto flex flex-wrap gap-2">
          {myChildren.map((c) => (
            <button
              key={c.id} onClick={() => setSelectedChildId(c.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                c.id === current.id ? 'bg-leaf/15 border-leaf/40 text-leaf' : 'border-rule text-slate hover:text-paper'
              }`}
            >
              {c.first_name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function AppShell() {
  const location = useLocation()
  const child = useChildSelection()
  const [navOpen, setNavOpen] = useState(false)
  const menuButton = useRef(null)
  const drawer = useRef(null)

  // The menu closes whenever you go somewhere, and on Escape; focus goes into it on open and back to the button on close.
  useEffect(() => { setNavOpen(false) }, [location.pathname])
  useEffect(() => {
    if (!navOpen) return undefined
    const button = menuButton.current
    drawer.current?.querySelector('a, button')?.focus()
    const onKey = (e) => { if (e.key === 'Escape') setNavOpen(false) }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); button?.focus() }
  }, [navOpen])

  return (
    <div className="flex min-h-screen bg-ink">
      <a href="#main" className="skip-link">Skip to main content</a>

      {/* Desktop and large tablet: the sidebar is always there. */}
      <div className="hidden lg:block print:hidden"><Sidebar /></div>

      {/* Phones and small tablets: the sidebar slides over the page when asked for. */}
      {navOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex print:hidden" role="dialog" aria-modal="true" aria-label="Main menu">
          <div ref={drawer} className="relative z-50 max-w-[85vw]"><Sidebar /></div>
          <button type="button" className="flex-1 bg-black/60" aria-label="Close menu" onClick={() => setNavOpen(false)} />
        </div>
      )}

      <main id="main" tabIndex={-1} className="flex-1 min-w-0 outline-none">
        <div className="flex items-center justify-between px-4 sm:px-8 pt-5 pb-3 print:hidden">
          <button
            ref={menuButton} type="button" onClick={() => setNavOpen(true)}
            aria-label="Open menu" aria-expanded={navOpen} aria-haspopup="dialog"
            className="lg:hidden p-2.5 -ml-1 rounded-lg border border-rule text-paper hover:bg-white/5 transition-colors"
          >
            <Menu size={20} aria-hidden="true" />
          </button>
          <div className="ml-auto"><NotificationBell /></div>
        </div>
        <div className="max-w-6xl mx-auto px-4 sm:px-8 pb-8 print:p-0 print:max-w-none">
          <ChildBanner />
          {/* Keyed on the page AND the selected child, so switching child reloads the page's data. */}
          <div key={`${location.pathname}:${child?.selectedChildId || ''}`} className="page-fade">
            <ErrorBoundary routeKey={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </div>
      </main>
    </div>
  )
}

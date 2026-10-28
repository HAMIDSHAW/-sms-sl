import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Users, UserSquare2, Contact, BookOpen, CalendarCheck2,
  CalendarClock, ClipboardList, Library, GraduationCap as ExamIcon, Settings, LogOut, DollarSign,
  Mail, Megaphone, ShieldAlert, BookMarked, BarChart3, Boxes, Bus, Briefcase, History,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useSchool } from '../../context/SchoolContext'
import { useChildSelection } from '../../context/ChildContext'

// `section` is purely a rendering/grouping label, it never touches
// visibility. A role only ever sees items it already had permission for;
// grouping just makes a long list (admin, principal) scannable the way a
// school register has dated sections rather than one unbroken column.
// A role with a short list (most staff) renders flat regardless, see the
// grouping logic below.
// Exported so App.jsx's route guards can check the exact same
// perm/perms a nav item requires, one source of truth, so a route can
// never drift out of sync with whether its own sidebar link is shown.
export const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true, section: 'Overview' },
  { to: '/students', label: 'Students', icon: Users, perm: 'students.view', section: 'People' },
  { to: '/staff', label: 'Staff', icon: UserSquare2, perm: 'staff.view', section: 'People' },
  { to: '/guardians', label: 'Parents', icon: Contact, perm: 'parents.view', orClassMaster: true, section: 'People' },
  { to: '/academics', label: 'Academics', icon: BookOpen, perm: 'academics.manage', section: 'Academics' },
  { to: '/attendance', label: 'Attendance', icon: CalendarCheck2, perm: 'attendance.view', section: 'Academics' },
  { to: '/timetable', label: 'Timetable', icon: CalendarClock, perm: 'timetable.view', section: 'Academics' },
  { to: '/assignments', label: 'Assignments', icon: ClipboardList, perm: 'assignments.view', section: 'Academics' },
  { to: '/materials', label: 'Materials', icon: Library, perm: 'materials.view', section: 'Academics' },
  { to: '/exams', label: 'Exams & Results', icon: ExamIcon, perm: 'exams.view', section: 'Academics' },
  { to: '/discipline', label: 'Discipline', icon: ShieldAlert, perm: 'discipline.view', section: 'Academics' },
  { to: '/library', label: 'Library', icon: BookMarked, perm: 'library.view', section: 'Academics' },
  { to: '/finance', label: 'Finance', icon: DollarSign, perm: 'finance.view', section: 'Finance' },
  { to: '/messages', label: 'Messages', icon: Mail, section: 'Communication' },
  { to: '/announcements', label: 'Announcements', icon: Megaphone, section: 'Communication' },
  { to: '/analytics', label: 'Analytics', icon: BarChart3, perm: 'analytics.view', section: 'Operations' },
  { to: '/inventory', label: 'Inventory', icon: Boxes, perm: 'inventory.view', section: 'Operations' },
  { to: '/transport', label: 'Transport', icon: Bus, perm: 'transport.view', section: 'Operations' },
  { to: '/hr', label: 'HR', icon: Briefcase, perms: ['hr.leave.view', 'hr.leave.request', 'hr.payroll.view'], section: 'Operations' },
  { to: '/activity', label: 'Activity log', icon: History, perm: 'audit.view', section: 'Operations' },
  { to: '/settings', label: 'School settings', icon: Settings, perm: 'school.settings.manage', section: 'Operations' },
]

// The signature touch for this component: an active row gets a small
// bookmark-ribbon tab sitting against the sidebar's outer edge, the way a
// tabbed divider marks a section in a physical register, rather than the
// generic flat left-border-highlight every admin template defaults to.
function NavItem({ to, label, icon: Icon, end }) {
  return (
    <NavLink to={to} end={end} className="block">
      {({ isActive }) => (
        <div className="relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors">
          {isActive && (
            <>
              <div className="absolute inset-0 bg-leaf/10 rounded-lg" />
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-5 bg-leaf rounded-r-[3px]" />
            </>
          )}
          <Icon size={17} className={`relative z-10 ${isActive ? 'text-leaf' : 'text-slate'}`} />
          <span className={`relative z-10 font-medium ${isActive ? 'text-paper' : 'text-slate'}`}>{label}</span>
        </div>
      )}
    </NavLink>
  )
}

export default function Sidebar() {
  const { hasPermission, logout, user } = useAuth()
  const { school } = useSchool()
  const { myChildren, selectedChildId, setSelectedChildId } = useChildSelection()
  const items = NAV.filter((item) => {
    if (item.orClassMaster && user?.is_class_master) return true
    if (item.perms) return item.perms.some((p) => hasPermission(p))
    return !item.perm || hasPermission(item.perm)
  })

  const sectionOrder = [...new Set(items.map((i) => i.section))]
  // Grouping only earns its keep on a genuinely long list, a role that
  // already sees four or fewer items (most staff, after the earlier
  // permission audit) gets one clean flat list, not headers for the sake
  // of headers.
  const grouped = items.length > 8 && sectionOrder.length > 1

  return (
    <aside className="w-64 shrink-0 h-screen sticky top-0 bg-inkraised border-r border-rule flex flex-col">
      {/* Notebook-spine header: a stack of tab-like index marks, tying the
          nav to the exercise-book vernacular rather than a generic logo bar. */}
      <div className="px-5 pt-6 pb-5 border-b border-rule">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-leaf flex items-center justify-center shrink-0 overflow-hidden">
            {school?.logo_url ? (
              <img src={school.logo_url} alt="" className="w-full h-full object-cover" />
            ) : (
              <ExamIcon size={18} className="text-ink" strokeWidth={2.5} />
            )}
          </div>
          <div className="min-w-0">
            <p className="font-display font-semibold text-sm leading-tight truncate">
              {school?.short_name || school?.name || 'SchoolOS'}
            </p>
            <p className="text-[11px] text-slate truncate">{school?.motto || 'Student Information System'}</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-2.5 bg-ruled">
        {grouped ? (
          sectionOrder.map((section) => (
            <div key={section} className="mb-1">
              <p className="px-3 pt-3 pb-1 text-[10px] tracking-wide text-slate/70">{section}</p>
              {items.filter((i) => i.section === section).map((item) => <NavItem key={item.to} {...item} />)}
            </div>
          ))
        ) : (
          <div className="space-y-0.5">
            {items.map((item) => <NavItem key={item.to} {...item} />)}
          </div>
        )}
      </nav>

      <div className="px-4 py-4 border-t border-rule">
        {myChildren.length > 1 && (
          <div className="mb-3">
            <p className="text-[10px] uppercase tracking-wide text-slate mb-1.5 px-1">Viewing</p>
            <select
              className="input !py-1.5 !text-xs w-full"
              value={selectedChildId || ''}
              aria-label="Choose which child you are viewing"
              onChange={(e) => setSelectedChildId(e.target.value)}
            >
              {myChildren.map((c) => <option key={c.id} value={c.id}>{c.full_name}</option>)}
            </select>
          </div>
        )}
        <NavLink to="/profile" className="flex items-center gap-2.5 mb-3 px-1 hover:opacity-80 transition-opacity">
          {user?.photo_url ? (
            <img src={user.photo_url} alt="" className="w-8 h-8 rounded-full object-cover shrink-0" />
          ) : (
            <div className="w-8 h-8 rounded-full bg-sky/20 flex items-center justify-center text-xs font-display font-semibold text-sky shrink-0">
              {(user?.first_name?.[0] || '') + (user?.last_name?.[0] || '')}
            </div>
          )}
          <div className="min-w-0">
            <p className="text-sm font-medium truncate">{user?.first_name} {user?.last_name}</p>
            <p className="text-[11px] text-slate truncate">{user?.roles?.join(', ')}</p>
          </div>
        </NavLink>
        <button onClick={logout} className="btn-secondary w-full text-xs !py-2">
          <LogOut size={14} /> Sign out
        </button>
      </div>
    </aside>
  )
}

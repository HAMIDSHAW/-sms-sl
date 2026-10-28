import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Users, UserSquare2, CalendarCheck2, ClipboardList, Layers, CheckCircle2, AlertCircle, ChevronRight } from 'lucide-react'
import { StatCard, Badge } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { useSchool } from '../context/SchoolContext'
import { useChildSelection } from '../context/ChildContext'

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const TONE = { info: 'text-sky', warn: 'text-marigold', danger: 'text-red-400' }

const localDate = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

export default function Dashboard() {
  const { user, hasPermission, hasRole } = useAuth()
  const { school } = useSchool()
  const childCtx = useChildSelection()
  const selfScoped = hasRole('student') || hasRole('parent')
  const isTeacher = hasRole('teacher')
  const isOversight = hasRole('school_administrator') || hasRole('principal')
  const isLearner = hasRole('student') || hasRole('parent')
  // Assignments are private to the teacher who sets them, so staff only count their own.
  const showAssignments = isLearner || hasPermission('assignments.create') || hasRole('principal')

  const [counts, setCounts] = useState({ students: null, staff: null, assignments: null })
  const [attendance, setAttendance] = useState(null)      // real figures from the attendance records
  const [attention, setAttention] = useState(null)        // what this person can act on, from the server
  const [teaching, setTeaching] = useState(null)
  const today = new Date()

  useEffect(() => {
    const date = localDate(today)
    if (hasPermission('students.view')) api.get('/api/students?per_page=1').then((d) => setCounts((c) => ({ ...c, students: d.total }))).catch(() => {})
    if (hasPermission('staff.view')) api.get('/api/staff?per_page=1').then((d) => setCounts((c) => ({ ...c, staff: d.total }))).catch(() => {})
    if (hasPermission('attendance.view')) api.get(`/api/attendance/summary?date=${date}`).then(setAttendance).catch(() => {})
    if (hasPermission('assignments.view') && showAssignments) {
      api.get('/api/assignments').then((list) => {
        const open = list.filter((a) => a.status === 'published' && (!a.due_date || a.due_date >= date))
        setCounts((c) => ({ ...c, assignments: open.length }))
      }).catch(() => {})
    }
    api.get('/api/dashboard/summary').then(setAttention).catch(() => setAttention({ items: [] }))
    if (isTeacher) api.get('/api/timetable/mine/summary').then(setTeaching).catch(() => {})
  }, [hasPermission])

  const items = attention?.items || []
  const childName = hasRole('parent') ? childCtx?.selectedChild?.first_name : null

  return (
    <div>
      <div className="mb-8 pb-6 border-b border-rule">
        <p className="eyebrow mb-1">{school?.name || 'School'}</p>
        <h1 className="font-display text-3xl font-semibold tracking-tight">
          {WEEKDAYS[today.getDay()]}, {MONTHS[today.getMonth()]} {today.getDate()}
        </h1>
        <p className="text-sm text-slate mt-1.5">
          {user?.first_name ? `Good to see you, ${user.first_name}.` : 'Welcome.'}
        </p>
      </div>

      {isOversight && <OversightView counts={counts} attendance={attendance} />}

      <div className="card p-6 max-w-2xl mt-6 first:mt-0">
        <p className="eyebrow mb-1">{childName ? `Today for ${childName}` : isOversight ? 'Needs your attention' : 'Today'}</p>
        <div className="divide-y divide-rule">
          {!isOversight && attendance && <AttendanceLine attendance={attendance} selfScoped={selfScoped} user={user} />}
          {isTeacher && teaching && (
            <AgendaLine icon={Layers} index={1}>
              You teach <span className="font-semibold">{teaching.classes_taught}</span> classes this term, with{' '}
              <span className="font-semibold">{teaching.periods_today}</span> period{teaching.periods_today === 1 ? '' : 's'} on today's timetable.
            </AgendaLine>
          )}
          {items.map((item, i) => <AttentionLine key={item.key} item={item} index={i + 2} />)}
          {attention && items.length === 0 && selfScoped && (
            <AgendaLine icon={CheckCircle2} index={2}>Nothing due right now. All caught up.</AgendaLine>
          )}
          {attention && items.length === 0 && !selfScoped && isOversight && (
            <AgendaLine icon={CheckCircle2} index={2}>Nothing is waiting on you.</AgendaLine>
          )}
        </div>
      </div>
    </div>
  )
}

function OversightView({ counts, attendance }) {
  const navigate = useNavigate()
  const school = attendance?.scope === 'school' ? attendance : null
  const weekend = [0, 6].includes(new Date().getDay())
  const rate = school ? (school.percentage == null ? (weekend ? 'Weekend' : 'Not marked yet') : `${school.percentage}%`) : '...'
  return (
    <div>
      <div className={`grid grid-cols-2 gap-4 ${showAssignments ? 'md:grid-cols-4' : 'md:grid-cols-3'}`}>
        <StatCard label="Total students" value={counts.students ?? '...'} icon={Users} accent="leaf" index={0} />
        <StatCard label="Total staff" value={counts.staff ?? '...'} icon={UserSquare2} accent="sky" index={1} />
        <StatCard
          label={school && school.marked ? `Attendance today, ${school.marked} of ${school.enrolled} marked` : 'Attendance today'}
          value={rate} icon={CalendarCheck2} accent="marigold" index={2}
        />
        {showAssignments && <StatCard label={isLearner || hasRole('principal') ? 'Open assignments' : 'Your open assignments'} value={counts.assignments ?? '...'} icon={ClipboardList} accent="leaf" index={3} />}
      </div>
      {school && school.not_marked > 0 && !(weekend && school.marked === 0) && (
        <button onClick={() => navigate('/attendance')} className="mt-3 text-xs text-marigold hover:underline">
          {school.not_marked} student{school.not_marked === 1 ? ' has' : 's have'} no attendance mark yet today. See which classes.
        </button>
      )}
    </div>
  )
}

function AttendanceLine({ attendance, selfScoped, user }) {
  if (attendance.scope === 'self') {
    const label = attendance.whole_day?.status_label || 'Not marked yet'
    const good = attendance.whole_day?.status_counts_as_present
    return (
      <AgendaLine icon={good ? CheckCircle2 : CalendarCheck2} index={0}>
        Attendance today: <Badge tone={good ? 'leaf' : 'marigold'}>{label}</Badge>
      </AgendaLine>
    )
  }
  // Staff who are not oversight: school figure, plus their own class if they are a class master.
  const own = (user?.class_master_of || []).map((c) => attendance.classes?.find((x) => x.class_id === c.id)).filter(Boolean)
  return (
    <>
      <AgendaLine icon={CalendarCheck2} index={0}>
        School attendance today:{' '}
        <span className="font-semibold">{attendance.percentage == null ? 'not marked yet' : `${attendance.percentage}%`}</span>
        {attendance.marked ? <span className="text-slate"> ({attendance.present} present of {attendance.marked} marked)</span> : null}
      </AgendaLine>
      {own.map((c) => (
        <AgendaLine key={c.class_id} icon={Users} index={1}>
          {c.class_name} today: <span className="font-semibold">{c.percentage == null ? 'not marked yet' : `${c.percentage}%`}</span>
          <span className="text-slate"> ({c.present} present, {c.absent} absent)</span>
        </AgendaLine>
      ))}
    </>
  )
}

function AttentionLine({ item, index }) {
  const navigate = useNavigate()
  return (
    <motion.button
      initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.07 }}
      onClick={() => navigate(item.link)}
      className="w-full text-left flex items-center gap-3 py-3 hover:bg-white/[0.02] transition-colors"
    >
      <div className="w-7 h-7 rounded-lg bg-white/5 flex items-center justify-center shrink-0">
        <AlertCircle size={14} className={TONE[item.tone] || TONE.info} />
      </div>
      <p className="text-sm flex-1">{item.label}</p>
      <ChevronRight size={14} className="text-slate" />
    </motion.button>
  )
}

function AgendaLine({ icon: Icon, children, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.07 }}
      className="flex items-start gap-3 py-3 first:pt-0"
    >
      <div className="w-7 h-7 rounded-lg bg-sky/12 flex items-center justify-center shrink-0 mt-0.5">
        <Icon size={14} className="text-sky" />
      </div>
      <p className="text-sm leading-relaxed">{children}</p>
    </motion.div>
  )
}

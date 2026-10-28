import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { CalendarCheck2, Check, ChevronRight, ShieldCheck } from 'lucide-react'
import { PageHeader, EmptyState, Badge } from '../../components/ui'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'
import AttendanceOverview from './AttendanceOverview'

export default function MarkAttendance() {
  const { hasPermission, hasRole } = useAuth()
  const [view, setView] = useState('mine')
  // Students and parents see the attendance record of the child on screen.
  if (hasRole('student') || hasRole('parent')) return <MyAttendance />
  // Teachers mark their own periods, and can switch to the class reports.
  if (hasRole('teacher') && hasPermission('attendance.create')) {
    return (
      <div>
        <div className="flex gap-1 border-b border-rule mb-6">
          {[['mine', 'Mark my periods'], ['reports', 'Class reports']].map(([key, name]) => (
            <button
              key={key} onClick={() => setView(key)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors ${view === key ? 'text-paper border-b-2 border-leaf' : 'text-slate hover:text-paper'}`}
            >
              {name}
            </button>
          ))}
        </div>
        {view === 'mine' ? <MyPeriodsToday /> : <AttendanceOverview />}
      </div>
    )
  }
  // Principal, admin and other staff: school wide figures and a class by class view.
  return <AttendanceOverview />
}

function MyAttendance() {
  const { hasRole } = useAuth()
  const isParent = hasRole('parent')
  const [records, setRecords] = useState(null)
  // Only relevant for a parent, which child's attendance is on screen.
  // A parent can have more than one child linked to their account, and
  // the API returns every child's records mixed together (each row does
  // carry student_id/student_name), so without this the page just showed
  // an unlabeled pile of dates with no way to tell whose record was whose.
  const [activeChild, setActiveChild] = useState(null)

  useEffect(() => {
    api.get('/api/attendance').then(setRecords)
  }, [])

  const children = records
    ? [...new Map(records.map((r) => [r.student_id, { id: r.student_id, name: r.student_name, photo_url: r.student_photo_url }])).values()]
    : []

  useEffect(() => {
    if (isParent && children.length && !activeChild) setActiveChild(children[0].id)
  }, [records])

  const visibleRecords = isParent && activeChild
    ? (records || []).filter((r) => r.student_id === activeChild)
    : records

  return (
    <div>
      <PageHeader
        eyebrow="Daily attendance"
        title={isParent ? "Children's attendance" : 'Attendance'}
        description={isParent ? "Each child's attendance record, period by period." : 'Your attendance record, period by period.'}
      />

      {isParent && children.length > 1 && (
        <div className="flex gap-2 mb-5">
          {children.map((c) => (
            <button
              key={c.id} onClick={() => setActiveChild(c.id)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                activeChild === c.id ? 'bg-leaf/15 text-leaf border border-leaf/30' : 'text-slate border border-rule hover:text-paper'
              }`}
            >
              {c.photo_url
                ? <img src={c.photo_url} alt="" className="w-5 h-5 rounded-full object-cover" />
                : <span className="w-5 h-5 rounded-full bg-sky/15 flex items-center justify-center text-[10px] font-semibold text-sky">{c.name?.[0]}</span>}
              {c.name}
            </button>
          ))}
        </div>
      )}

      {visibleRecords === null ? null : visibleRecords.length === 0 ? (
        <EmptyState icon={CalendarCheck2} title="No attendance recorded yet" />
      ) : (
        <DayList records={visibleRecords} />
      )}
    </div>
  )
}

/** One card per day: the whole day status first, then each period with its subject. */
function DayList({ records }) {
  const byDate = {}
  records.forEach((r) => { (byDate[r.date] ||= []).push(r) })
  const dates = Object.keys(byDate).sort((a, b) => b.localeCompare(a))
  const wholeDays = dates.map((d) => byDate[d].find((r) => !r.subject_id)).filter(Boolean)
  const presentDays = wholeDays.filter((r) => r.status_counts_as_present).length

  return (
    <div>
      {wholeDays.length > 0 && (
        <p className="text-sm text-slate mb-4">
          Present on <span className="text-paper font-medium">{presentDays}</span> of <span className="text-paper font-medium">{wholeDays.length}</span> recorded days
          {' '}({Math.round((presentDays / wholeDays.length) * 100)}%)
        </p>
      )}
      <div className="space-y-3">
        {dates.map((d) => {
          const day = byDate[d].find((r) => !r.subject_id)
          const periods = byDate[d].filter((r) => r.subject_id)
          return (
            <div key={d} className="card px-4 py-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{new Date(d + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'short' })}</span>
                {day ? <Badge tone={day.status_counts_as_present ? 'leaf' : 'red'}>Whole day: {day.status_label}</Badge> : <span className="text-xs text-slate">Whole day not marked</span>}
              </div>
              {periods.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {periods.map((p) => (
                    <span key={p.id} className={`text-xs px-2 py-1 rounded-md border ${p.status_counts_as_present ? 'border-leaf/30 text-leaf' : 'border-red-400/30 text-red-400'}`}>
                      {p.subject_name || 'Period'}: {p.status_label}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

/**
 * The real teacher workflow: your own timetable periods for today,
 * each one markable separately, so attendance is taken every period
 * you actually teach, not once a day for the whole school day. If
 * you're the class master for a class, you also get a whole-day check
 * for that class (subject_id left blank), which is how the "did this
 * student attend the whole day" question actually gets answered rather
 * than just "were they in one specific class."
 */
function MyPeriodsToday() {
  const [periods, setPeriods] = useState(null)
  const [active, setActive] = useState(null) // { classId, subjectId, subjectName, className, isWholeDay }

  useEffect(() => {
    api.get('/api/timetable/mine').then(setPeriods)
  }, [])

  const masterClasses = periods ? [...new Map(periods.filter((p) => p.is_class_master_here).map((p) => [p.class_id, p])).values()] : []

  if (active) {
    return (
      <RosterMarker
        classId={active.classId}
        subjectId={active.isWholeDay ? null : active.subjectId}
        title={active.isWholeDay ? `Whole day: ${active.className}` : `${active.subjectName}, ${active.className}`}
        onBack={() => setActive(null)}
      />
    )
  }

  return (
    <div>
      <PageHeader eyebrow="Daily attendance" title="Mark attendance" description="Today's periods. Pick one to mark, or do a whole-day check for a class you lead." />

      {periods === null ? null : periods.length === 0 && masterClasses.length === 0 ? (
        <EmptyState icon={CalendarCheck2} title="Nothing on your timetable today" />
      ) : (
        <div className="space-y-2">
          {periods.map((p) => (
            <button
              key={p.id}
              onClick={() => setActive({ classId: p.class_id, subjectId: p.subject_id, subjectName: p.subject_name, className: p.class_name })}
              className="w-full card p-4 flex items-center justify-between hover:border-leaf/40 transition-colors text-left"
            >
              <div>
                <p className="font-medium text-sm">{p.subject_name}, {p.class_name}</p>
                <p className="text-xs text-slate font-mono mt-0.5">{p.start_time}–{p.end_time}</p>
              </div>
              <ChevronRight size={16} className="text-slate" />
            </button>
          ))}

          {masterClasses.length > 0 && (
            <>
              <p className="eyebrow mt-6 mb-2">Whole-day check for classes you lead</p>
              {masterClasses.map((p) => (
                <button
                  key={`master-${p.class_id}`}
                  onClick={() => setActive({ classId: p.class_id, className: p.class_name, isWholeDay: true })}
                  className="w-full card p-4 flex items-center justify-between hover:border-marigold/40 transition-colors text-left"
                >
                  <div className="flex items-center gap-2.5">
                    <ShieldCheck size={16} className="text-marigold" />
                    <p className="font-medium text-sm">{p.class_name}, whole day</p>
                  </div>
                  <ChevronRight size={16} className="text-slate" />
                </button>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function RosterMarker({ classId, subjectId, title, onBack }) {
  const [years, setYears] = useState([])
  const [statuses, setStatuses] = useState([])
  const [students, setStudents] = useState([])
  const [marks, setMarks] = useState({})
  const [saved, setSaved] = useState(false)
  const date = new Date().toISOString().slice(0, 10)

  useEffect(() => {
    api.get('/api/academics/years').then((d) => setYears(asList(d)))
    api.get('/api/attendance/statuses').then((d) => setStatuses(asList(d)))
  }, [])

  useEffect(() => {
    const currentYear = years.find((y) => y.is_current) || years[0]
    if (!currentYear) return
    api.get(`/api/enrollments?class_id=${classId}&academic_year_id=${currentYear.id}`).then(async (enrollments) => {
      const withStudents = await Promise.all(
        enrollments.map((e) => api.get(`/api/students/${e.student_id}`).then((s) => ({ ...s, enrollment: e })))
      )
      setStudents(withStudents)
      setMarks(Object.fromEntries(withStudents.map((s) => [s.id, 'present'])))
    })
  }, [classId, years])

  const submit = async () => {
    const currentYear = years.find((y) => y.is_current) || years[0]
    await api.post('/api/attendance/bulk', {
      class_id: classId,
      subject_id: subjectId || null,
      academic_year_id: currentYear.id,
      date,
      entries: Object.entries(marks).map(([student_id, status_code]) => ({ student_id, status_code })),
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div>
      <button onClick={onBack} className="text-sm text-slate hover:text-paper mb-4 transition-colors">← Back to today's periods</button>
      <PageHeader eyebrow="Daily attendance" title={title} description={`Marking for ${date}.`} />

      {students.length === 0 ? (
        <EmptyState title="No students enrolled in this class yet" />
      ) : (
        <>
          <div className="card divide-y divide-rule">
            {students.map((s, i) => (
              <motion.div
                key={s.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.02 }}
                className="flex items-center justify-between px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-sky/15 flex items-center justify-center text-xs font-display font-semibold text-sky">
                    {s.first_name[0]}{s.last_name[0]}
                  </div>
                  <span className="text-sm font-medium">{s.full_name}</span>
                </div>
                <div className="flex gap-1.5">
                  {statuses.map((st) => (
                    <button
                      key={st.code}
                      onClick={() => setMarks((m) => ({ ...m, [s.id]: st.code }))}
                      className={`px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
                        marks[s.id] === st.code
                          ? st.counts_as_present ? 'bg-leaf text-ink' : 'bg-red-400 text-ink'
                          : 'bg-white/5 text-slate hover:bg-white/10'
                      }`}
                    >
                      {st.label}
                    </button>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>

          <button onClick={submit} className="btn-primary mt-5">
            {saved ? <><Check size={16} /> Saved</> : 'Save attendance'}
          </button>
        </>
      )}
    </div>
  )
}

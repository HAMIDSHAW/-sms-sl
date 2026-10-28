import { useEffect, useMemo, useState } from 'react'
import { CalendarCheck2, Users, UserCheck, UserX, Clock } from 'lucide-react'
import { PageHeader, StatCard, Table, Badge, EmptyState, Avatar } from '../../components/ui'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const today = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
// Start on the most recent school day, so opening this on a weekend shows Friday's register, not an empty page.
const lastSchoolDay = () => {
  const d = new Date()
  while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() - 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const TONE = { Present: 'leaf', Late: 'marigold', Absent: 'red', Excused: 'sky', 'Not marked': 'slate' }
const pct = (v) => (v == null ? 'N/A' : `${v}%`)

/**
 * School wide attendance for any date, then one class at a time. Every number
 * comes from the attendance records themselves, never a fixed figure.
 */
export default function AttendanceOverview() {
  const { user } = useAuth()
  const [date, setDate] = useState(lastSchoolDay())
  const [summary, setSummary] = useState(null)
  const [classId, setClassId] = useState('')
  const [detail, setDetail] = useState(null)
  const [filter, setFilter] = useState('All')

  useEffect(() => {
    setSummary(null)
    api.get(`/api/attendance/summary?date=${date}`).then((d) => {
      setSummary(d)
      setClassId((current) => current || user?.class_master_of?.[0]?.id || d.classes?.[0]?.class_id || '')
    })
  }, [date])

  useEffect(() => {
    if (!classId) return
    setDetail(null)
    setFilter('All')
    api.get(`/api/attendance/overview?class_id=${classId}&date=${date}`).then(setDetail)
  }, [classId, date])

  const rows = useMemo(() => {
    if (!detail) return null
    return filter === 'All' ? detail.students : detail.students.filter((s) => s.whole_day_label === filter)
  }, [detail, filter])

  const school = summary
  return (
    <div>
      <PageHeader
        eyebrow="Attendance"
        title="Attendance overview"
        description="Whole day attendance for the school and for each class, with the period by period detail."
        action={<input type="date" aria-label="Attendance date" className="input !py-1.5 text-sm" value={date} max={today()} onChange={(e) => e.target.value && setDate(e.target.value)} />}
      />

      {school && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard label="Students enrolled" value={school.enrolled} icon={Users} accent="sky" index={0} />
          <StatCard label={`Present${school.late ? ` (${school.late} late)` : ''}`} value={school.present} icon={UserCheck} accent="leaf" index={1} />
          <StatCard label="Absent" value={school.absent} icon={UserX} accent="marigold" index={2} />
          <StatCard label={school.marked ? `Attendance rate, ${school.marked} marked` : 'Not marked yet'} value={pct(school.percentage)} icon={Clock} accent="leaf" index={3} />
        </div>
      )}

      {school?.classes && (
        <div className="mb-8">
          <p className="eyebrow mb-3">By class</p>
          <Table
            rows={school.classes}
            keyField="class_id"
            onRowClick={(r) => setClassId(r.class_id)}
            columns={[
              { key: 'class_name', header: 'Class', render: (r) => <span className={`font-medium ${r.class_id === classId ? 'text-leaf' : ''}`}>{r.class_name}</span> },
              { key: 'enrolled', header: 'Enrolled' },
              { key: 'present', header: 'Present' },
              { key: 'absent', header: 'Absent' },
              { key: 'not_marked', header: 'Not marked', render: (r) => (r.not_marked ? <span className="text-marigold">{r.not_marked}</span> : 0) },
              { key: 'percentage', header: 'Rate', render: (r) => <span className="font-mono text-xs">{pct(r.percentage)}</span> },
            ]}
          />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <p className="eyebrow">Class register</p>
        <select aria-label="Choose class" className="input !py-1.5 text-sm w-40" value={classId} onChange={(e) => setClassId(e.target.value)}>
          {(school?.classes || []).map((c) => <option key={c.class_id} value={c.class_id}>{c.class_name}</option>)}
        </select>
        {detail && (
          <div className="flex flex-wrap gap-1.5 ml-auto">
            {['All', ...Object.keys(detail.counts)].map((k) => (
              <button
                key={k} onClick={() => setFilter(k)}
                className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${filter === k ? 'bg-leaf/15 border-leaf/40 text-leaf' : 'border-rule text-slate hover:text-paper'}`}
              >
                {k}{k !== 'All' ? ` (${detail.counts[k]})` : ` (${detail.students.length})`}
              </button>
            ))}
          </div>
        )}
      </div>

      {!classId ? (
        <EmptyState icon={CalendarCheck2} title="Pick a class" />
      ) : (
        <Table
          emptyLabel="No students in this category"
          rows={rows}
          keyField="student_id"
          columns={[
            { key: 'student', header: 'Student', render: (r) => (
              <span className="flex items-center gap-2.5">
                <Avatar src={r.photo_url} name={r.student_name} size={28} />
                <span><span className="text-sm">{r.student_name}</span><br /><span className="text-[11px] text-slate font-mono">{r.student_number}</span></span>
              </span>
            ) },
            { key: 'day', header: 'Whole day', render: (r) => <Badge tone={TONE[r.whole_day_label] || 'slate'}>{r.whole_day_label}</Badge> },
            { key: 'periods', header: 'Periods', render: (r) => (
              r.periods.length === 0 ? <span className="text-xs text-slate">None recorded</span> : (
                <span className="flex flex-wrap gap-1.5">
                  {r.periods.map((p) => (
                    <span key={p.id} className={`text-[11px] px-1.5 py-0.5 rounded border ${p.status_counts_as_present ? 'border-leaf/30 text-leaf' : 'border-red-400/30 text-red-400'}`}>
                      {p.subject_name}: {p.status_label}
                    </span>
                  ))}
                </span>
              )
            ) },
          ]}
        />
      )}
    </div>
  )
}

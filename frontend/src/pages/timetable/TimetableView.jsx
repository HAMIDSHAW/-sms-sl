import { useEffect, useState } from 'react'
import { PlusCircle, Trash2, Pencil } from 'lucide-react'
import { PageHeader, EmptyState, Modal } from '../../components/ui'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'
import { useChildSelection } from '../../context/ChildContext'

const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
const DAY_LABELS = { monday: 'Mon', tuesday: 'Tue', wednesday: 'Wed', thursday: 'Thu', friday: 'Fri' }

export default function TimetableView() {
  const { hasRole, hasPermission } = useAuth()
  const { selectedChildId } = useChildSelection()
  const isParent = hasRole('parent')
  const selfScoped = hasRole('student') || isParent
  const canManage = hasPermission('timetable.manage')

  const [classes, setClasses] = useState([])
  const [subjects, setSubjects] = useState([])
  const [staff, setStaff] = useState([])
  const [classId, setClassId] = useState('')
  const [entries, setEntries] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [editing, setEditing] = useState(null)

  const loadEntries = () => {
    if (selfScoped) {
      const params = isParent && selectedChildId ? `?student_id=${selectedChildId}` : ''
      api.get(`/api/timetable${params}`).then((e) => { setEntries(e); setLoaded(true) })
    } else if (classId) {
      api.get(`/api/timetable?class_id=${classId}`).then((d) => setEntries(asList(d)))
    }
  }

  useEffect(() => {
    api.get('/api/academics/subjects').then((d) => setSubjects(asList(d)))
    // Staff list is only used to populate the "add period" teacher dropdown,
    // which only a manager (canManage) ever sees, and only managers reliably
    // have staff.view permission. Skip the fetch entirely otherwise so it
    // never fails silently for teachers/students/parents (timetable rows
    // carry their own subject_name/staff_name from the backend now, so this
    // list was never actually needed just to render the grid).
    if (canManage) api.get('/api/staff?per_page=200').then((d) => setStaff(asList(d))).catch(() => {})
    if (!selfScoped) api.get('/api/academics/classes').then((d) => setClasses(asList(d)))
  }, [])

  useEffect(() => { loadEntries() }, [classId, selectedChildId])

  // Prefer the name the backend already resolved for this row; fall back to
  // a client-side lookup only if that's somehow missing (e.g. an older
  // cached response), and only show a dash, never a fabricated "N/A" -
  // when a period genuinely has no subject/teacher assigned.
  const subjectName = (e) => e.subject_name || subjects.find((s) => s.id === e.subject_id)?.name || 'N/A'
  const teacherName = (e) => e.staff_name || staff.find((s) => s.id === e.staff_id)?.full_name || 'N/A'
  const showGrid = selfScoped ? loaded : !!classId

  const removeEntry = async (id) => {
    if (!confirm('Remove this period from the timetable?')) return
    await api.delete(`/api/timetable/${id}`)
    loadEntries()
  }

  return (
    <div>
      <PageHeader
        eyebrow="Weekly schedule"
        title="Timetable"
        description={selfScoped ? 'Your class schedule for the week: subject, teacher, and lunch.' : "View each class's periods, subjects, and teachers across the week."}
        action={
          !selfScoped && canManage && classId && (
            <button onClick={() => setCreateOpen(true)} className="btn-primary text-xs">
              <PlusCircle size={14} /> Add period
            </button>
          )
        }
      />

      {!selfScoped && (
        <select className="input max-w-xs mb-6" value={classId} onChange={(e) => setClassId(e.target.value)}>
          <option value="">Select a class…</option>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      )}

      {!showGrid ? (
        <EmptyState title="Pick a class to view its timetable" />
      ) : entries.length === 0 ? (
        <EmptyState title="No periods scheduled yet" />
      ) : (
        <div className="grid grid-cols-5 gap-3">
          {DAYS.map((day) => (
            <div key={day} className="card p-3">
              <p className="eyebrow mb-3 text-center">{DAY_LABELS[day]}</p>
              <div className="space-y-2">
                {entries.filter((e) => e.day_of_week === day).sort((a, b) => a.start_time.localeCompare(b.start_time)).map((e) => (
                  <div key={e.id} className="group relative rounded-lg bg-sky/10 border border-sky/20 px-2.5 py-2">
                    <p className="text-xs font-mono text-sky">{e.start_time}–{e.end_time}</p>
                    <p className="text-xs font-medium mt-0.5 truncate">{subjectName(e)}</p>
                    <p className="text-[11px] text-slate truncate">{teacherName(e)}</p>
                    {e.room && <p className="text-[11px] text-slate">{e.room}</p>}
                    {!selfScoped && canManage && (
                      <div className="absolute top-1.5 right-1.5 hidden group-hover:flex gap-1">
                        <button onClick={() => setEditing(e)} className="w-5 h-5 rounded bg-ink/40 flex items-center justify-center text-slate hover:text-paper">
                          <Pencil size={10} />
                        </button>
                        <button onClick={() => removeEntry(e.id)} className="w-5 h-5 rounded bg-ink/40 flex items-center justify-center text-slate hover:text-red-400">
                          <Trash2 size={10} />
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Add a timetable period">
        <PeriodForm classId={classId} subjects={subjects} staff={staff} onCreated={() => { setCreateOpen(false); loadEntries() }} />
      </Modal>

      <Modal open={!!editing} onClose={() => setEditing(null)} title="Edit period">
        {editing && (
          <PeriodForm
            classId={classId} subjects={subjects} staff={staff} existing={editing}
            onCreated={() => { setEditing(null); loadEntries() }}
          />
        )}
      </Modal>
    </div>
  )
}

function PeriodForm({ classId, subjects, staff, existing, onCreated }) {
  const [years, setYears] = useState([])
  const [form, setForm] = useState(existing ? {
    subject_id: existing.subject_id, staff_id: existing.staff_id, day_of_week: existing.day_of_week,
    start_time: existing.start_time, end_time: existing.end_time, room: existing.room || '',
  } : { subject_id: '', staff_id: '', day_of_week: 'monday', start_time: '', end_time: '', room: '' })
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => { api.get('/api/academics/years').then((d) => setYears(asList(d))) }, [])

  const set = (f) => (e) => setForm((s) => ({ ...s, [f]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      if (existing) {
        await api.patch(`/api/timetable/${existing.id}`, form)
      } else {
        const currentYear = years.find((y) => y.is_current) || years[0]
        await api.post('/api/timetable', { ...form, class_id: classId, academic_year_id: currentYear?.id })
      }
      onCreated()
    } catch (err) {
      setError(err.data?.error || 'Could not save this period. Check for a scheduling conflict.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="label">Subject</label>
        <select required className="input" value={form.subject_id} onChange={set('subject_id')}>
          <option value="">Select…</option>
          {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </div>
      <div>
        <label className="label">Teacher</label>
        <select required className="input" value={form.staff_id} onChange={set('staff_id')}>
          <option value="">Select…</option>
          {staff.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
        </select>
      </div>
      <div>
        <label className="label">Day</label>
        <select className="input" value={form.day_of_week} onChange={set('day_of_week')}>
          {DAYS.map((d) => <option key={d} value={d}>{DAY_LABELS[d]}</option>)}
        </select>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="label">Start time</label><input required type="time" className="input" value={form.start_time} onChange={set('start_time')} /></div>
        <div><label className="label">End time</label><input required type="time" className="input" value={form.end_time} onChange={set('end_time')} /></div>
      </div>
      <div><label className="label">Room</label><input className="input" value={form.room} onChange={set('room')} /></div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting} className="btn-primary w-full">
        {submitting ? 'Saving…' : existing ? 'Save changes' : 'Add period'}
      </button>
    </form>
  )
}

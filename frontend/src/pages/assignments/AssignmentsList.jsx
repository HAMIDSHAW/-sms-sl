import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PlusCircle, Calendar, Trash2, Lock } from 'lucide-react'
import { PageHeader, Table, Badge, Modal, FileUpload } from '../../components/ui'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'
import { useChildSelection } from '../../context/ChildContext'

const STATUS_TONE = { draft: 'slate', published: 'leaf', closed: 'marigold' }
const SUB_STATUS = {
  not_submitted: { label: 'Not handed in', tone: 'marigold' },
  overdue: { label: 'Overdue', tone: 'red' },
  submitted: { label: 'Handed in', tone: 'sky' },
  late: { label: 'Handed in late', tone: 'marigold' },
  graded: { label: 'Graded', tone: 'leaf' },
}
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }

export default function AssignmentsList() {
  const [assignments, setAssignments] = useState(null)
  const [createOpen, setCreateOpen] = useState(false)
  const { user, hasPermission, hasRole } = useAuth()
  const childCtx = useChildSelection()
  const navigate = useNavigate()
  const isParent = hasRole('parent')
  const isLearner = isParent || hasRole('student')
  const isStaff = !isLearner
  const isOversight = hasRole('principal') // sees every teacher's published assignments, read-only
  const [teacherFilter, setTeacherFilter] = useState('')
  const canCreate = hasPermission('assignments.create')
  const childName = isParent ? childCtx?.selectedChild?.first_name : null

  const load = () => api.get('/api/assignments').then((d) => setAssignments(asList(d)))
  useEffect(() => { load() }, [])

  const deleteAssignment = async (r) => {
    if (!window.confirm(`Delete "${r.title}"? This removes any submissions too and can't be undone.`)) return
    await api.delete(`/api/assignments/${r.id}`)
    load()
  }

  // What this page is for depends on who is looking at it.
  let description
  let emptyLabel
  if (isParent) {
    description = childName ? `Homework and coursework for ${childName}'s class.` : 'Homework and coursework for your child\'s class.'
    emptyLabel = 'No assignments yet'
  } else if (isLearner) {
    description = 'Homework and coursework for your class.'
    emptyLabel = 'No assignments yet'
  } else if (isOversight) {
    description = 'Every teacher\'s published assignments, read only. You can see what was set and how many students have handed in. Only the teacher who set an assignment can see the work itself and grade it.'
    emptyLabel = 'No assignments have been published yet'
  } else if (canCreate) {
    description = 'Assignments you have set. Only you can see the work handed in and grade it.'
    emptyLabel = 'You have not set any assignments yet'
  } else {
    description = 'Each assignment is private to the teacher who set it, so only that teacher can see handed-in work and grade it. Anything you set yourself appears here.'
    emptyLabel = 'You have not set any assignments. Teachers\' assignments are visible only to the teacher who set them.'
  }

  return (
    <div>
      <PageHeader
        eyebrow="Coursework"
        title="Assignments"
        description={description}
        action={
          canCreate && (
            <button onClick={() => setCreateOpen(true)} className="btn-primary text-xs">
              <PlusCircle size={14} /> New assignment
            </button>
          )
        }
      />

      {isOversight && assignments && assignments.length > 0 && (
        <div className="flex items-center gap-2 mb-4">
          <label className="label !mb-0" htmlFor="teacher-filter">Teacher</label>
          <select id="teacher-filter" className="input !w-auto min-w-[12rem]" value={teacherFilter} onChange={(e) => setTeacherFilter(e.target.value)}>
            <option value="">All teachers</option>
            {[...new Map(assignments.map((a) => [a.staff_id, a.teacher_name])).entries()]
              .sort((x, y) => String(x[1]).localeCompare(String(y[1])))
              .map(([sid, name]) => <option key={sid} value={sid}>{name}</option>)}
          </select>
        </div>
      )}

      <Table
        emptyLabel={emptyLabel}
        columns={[
          { key: 'title', header: 'Title', render: (r) => (
            <div>
              <span className="font-medium">{r.title}</span>
              <p className="text-xs text-slate">{[r.subject_name, r.class_name].filter(Boolean).join(', ')}</p>
            </div>
          ) },
          ...((isLearner || isOversight) ? [{ key: 'teacher', header: 'Set by', render: (r) => <span className="text-xs">{r.teacher_name || 'N/A'}</span> }] : []),
          {
            key: 'due_date', header: 'Due', render: (r) => (
              <span className={`text-xs ${r.is_closed ? 'text-slate' : ''}`}>
                <span className="flex items-center gap-1.5 text-slate"><Calendar size={13} /> {r.due_date}</span>
                {r.extended && <span className="text-[11px] text-marigold">Extended from {r.original_due_date}</span>}
              </span>
            ),
          },
          { key: 'max_marks', header: 'Marks', render: (r) => <span className="font-mono text-xs">{r.max_marks}</span> },
          isStaff
            ? { key: 'progress', header: 'Handed in', render: (r) => (
                <span className="text-xs font-mono">{r.submission_count ?? 0}/{r.class_size ?? 0}
                  {r.submission_count > r.graded_count ? <span className="text-marigold ml-1">({r.submission_count - r.graded_count} to grade)</span> : null}
                </span>
              ) }
            : { key: 'mine', header: isParent && childName ? `${childName}'s status` : 'My status', render: (r) => {
                const st = SUB_STATUS[r.my_submission?.status] || SUB_STATUS.not_submitted
                return (
                  <span className="flex items-center gap-2">
                    <Badge tone={st.tone}>{st.label}</Badge>
                    {r.my_submission?.status === 'graded' && <span className="font-mono text-xs text-marigold">{r.my_submission.marks_obtained}/{r.max_marks}</span>}
                  </span>
                )
              } },
          { key: 'status', header: 'Status', render: (r) => (
            r.is_closed && r.status !== 'draft'
              ? <Badge tone="marigold"><span className="inline-flex items-center gap-1"><Lock size={11} /> Closed</span></Badge>
              : <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge>
          ) },
          {
            key: 'actions', header: '', render: (r) => user?.staff_id && r.staff_id === user.staff_id && hasPermission('assignments.delete') && (
              <button
                onClick={(e) => { e.stopPropagation(); deleteAssignment(r) }}
                className="text-slate hover:text-red-400 transition-colors p-1"
                title="Delete your assignment" aria-label={`Delete ${r.title}`}
              >
                <Trash2 size={14} />
              </button>
            ),
          },
        ]}
        rows={assignments && (teacherFilter ? assignments.filter((a) => a.staff_id === teacherFilter) : assignments)}
        onRowClick={(r) => navigate(`/assignments/${r.id}`)}
      />

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New assignment">
        <CreateAssignmentForm onCreated={() => { setCreateOpen(false); load() }} />
      </Modal>
    </div>
  )
}

function CreateAssignmentForm({ onCreated }) {
  const [options, setOptions] = useState(null) // the class and subject pairs the teacher actually teaches
  const [staff, setStaff] = useState([])
  const [years, setYears] = useState([])
  const [form, setForm] = useState({ title: '', subject_id: '', class_id: '', staff_id: '', due_date: '', max_marks: 100, attachment_url: '' })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const { user, hasPermission } = useAuth()
  // A teacher sets work in their own name (the server takes it from their login). Only an
  // account with no staff record of its own, such as an administrator, picks the teacher.
  const picksTeacher = !user?.staff_id && hasPermission('staff.view')

  useEffect(() => {
    api.get('/api/academics/years').then((d) => setYears(asList(d)))
    if (picksTeacher) api.get('/api/staff?per_page=200').then((d) => setStaff(asList(d).filter((s) => s.staff_type === 'teacher' && s.status !== 'terminated'))).catch(() => {})
  }, [])

  useEffect(() => {
    if (picksTeacher && !form.staff_id) { setOptions([]); return }
    setOptions(null)
    api.get(`/api/assignments/options${picksTeacher ? `?staff_id=${form.staff_id}` : ''}`).then((d) => setOptions(asList(d))).catch(() => setOptions([]))
  }, [form.staff_id])

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
  const classes = useMemo(() => {
    const seen = new Map()
    ;(options || []).forEach((o) => seen.set(o.class_id, o.class_name))
    return [...seen].map(([id, name]) => ({ id, name }))
  }, [options])
  const subjects = (options || []).filter((o) => o.class_id === form.class_id)

  const pickClass = (e) => {
    const class_id = e.target.value
    const there = (options || []).filter((o) => o.class_id === class_id)
    // If they teach just one subject in that class there is nothing to choose.
    setForm((f) => ({ ...f, class_id, subject_id: there.length === 1 ? there[0].subject_id : '' }))
  }
  const pickTeacher = (e) => setForm((f) => ({ ...f, staff_id: e.target.value, class_id: '', subject_id: '' }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const currentYear = years.find((y) => y.is_current) || years[0]
      await api.post('/api/assignments', { ...form, max_marks: Number(form.max_marks) || 100, academic_year_id: currentYear?.id, status: 'published' })
      onCreated()
    } catch (err) {
      setError(err.data?.error || err.message || 'Could not create assignment')
    } finally {
      setSubmitting(false)
    }
  }

  const noneTaught = options && options.length === 0 && (!picksTeacher || form.staff_id)

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="label" htmlFor="as-title">Title</label>
        <input id="as-title" required className="input" value={form.title} onChange={set('title')} />
      </div>
      {picksTeacher && (
        <div>
          <label className="label" htmlFor="as-teacher">Teacher</label>
          <select id="as-teacher" required className="input" value={form.staff_id} onChange={pickTeacher}>
            <option value="">Select…</option>
            {staff.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
          </select>
          <p className="text-[11px] text-slate mt-1">You are setting this on the teacher's behalf. They will be able to see it and grade it.</p>
        </div>
      )}
      {noneTaught ? (
        <p className="text-sm text-marigold">{picksTeacher ? 'This teacher is not assigned to teach any class yet.' : 'You are not assigned to teach any class yet.'} Classes and subjects are assigned under Academics.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="as-class">Class</label>
            <select id="as-class" required className="input" value={form.class_id} onChange={pickClass} disabled={!options || (picksTeacher && !form.staff_id)}>
              <option value="">Select…</option>
              {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="as-subject">Subject</label>
            <select id="as-subject" required className="input" value={form.subject_id} onChange={set('subject_id')} disabled={!form.class_id}>
              <option value="">{form.class_id ? 'Select…' : 'Choose a class first'}</option>
              {subjects.map((o) => <option key={o.subject_id} value={o.subject_id}>{o.subject_name}</option>)}
            </select>
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="as-due">Due date</label>
          <input id="as-due" required type="date" className="input" min={today()} value={form.due_date} onChange={set('due_date')} />
        </div>
        <div>
          <label className="label" htmlFor="as-marks">Max marks</label>
          <input id="as-marks" type="number" min="1" className="input" value={form.max_marks} onChange={set('max_marks')} />
        </div>
      </div>
      <p className="text-[11px] text-slate -mt-2">Students can hand in until the end of the due date. After that it closes, and you can extend it from the assignment page.</p>
      <div>
        <label className="label">Attachment (optional)</label>
        <FileUpload
          value={form.attachment_url}
          onChange={(url) => setForm((f) => ({ ...f, attachment_url: url }))}
        />
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting || noneTaught} className="btn-primary w-full">
        {submitting ? 'Creating…' : 'Publish assignment'}
      </button>
    </form>
  )
}

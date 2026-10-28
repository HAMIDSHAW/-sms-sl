import { useEffect, useState } from 'react'
import { PlusCircle, CheckCircle2, BellRing } from 'lucide-react'
import { PageHeader, Table, Badge, Modal, Pagination, Avatar } from '../../components/ui'
import StudentPicker from '../../components/StudentPicker'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const CATEGORY_TONE = { warning: 'marigold', incident: 'red', suspension: 'red', positive_recognition: 'leaf' }
const STATUS_TONE = { open: 'marigold', resolved: 'leaf', follow_up_needed: 'red' }
const label = (s) => (s || 'unknown').replace(/_/g, ' ')
const ACTIONS = [
  'Verbal warning given', 'Written warning issued', 'Parents called in', 'Detention', 'Suspended for a number of days',
  'Referred to counselling', 'Community service assigned', 'Commended at assembly',
]

export default function Discipline() {
  const { hasPermission } = useAuth()
  const [data, setData] = useState({ items: null, page: 1, pages: 1 })
  const [page, setPage] = useState(1)
  const [classes, setClasses] = useState([])
  const [classId, setClassId] = useState('')
  const [status, setStatus] = useState('')
  const [category, setCategory] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [selected, setSelected] = useState(null)

  const load = () => {
    const p = new URLSearchParams({ page, per_page: 20 })
    if (classId) p.set('class_id', classId)
    if (status) p.set('status', status)
    if (category) p.set('category', category)
    return api.get(`/api/discipline?${p}`).then(setData)
  }
  useEffect(() => { load() }, [page, classId, status, category])
  useEffect(() => { api.get('/api/academics/classes').then((d) => setClasses(asList(d))).catch(() => {}) }, [])

  return (
    <div>
      <PageHeader
        eyebrow="Student conduct"
        title="Discipline"
        description="Incidents, warnings, and positive recognition. Open a record to take action on it."
        action={hasPermission('discipline.create') && <button onClick={() => setCreateOpen(true)} className="btn-primary text-xs"><PlusCircle size={14} /> New record</button>}
      />

      <div className="flex flex-wrap gap-3 mb-4">
        <select aria-label="Filter by class" className="input !py-1.5 text-sm w-40" value={classId} onChange={(e) => { setClassId(e.target.value); setPage(1) }}>
          <option value="">All classes</option>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select aria-label="Filter by status" className="input !py-1.5 text-sm w-44" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
          <option value="">Any status</option>
          <option value="open">Open</option>
          <option value="follow_up_needed">Follow up needed</option>
          <option value="resolved">Resolved</option>
        </select>
        <select aria-label="Filter by category" className="input !py-1.5 text-sm w-48" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1) }}>
          <option value="">Any category</option>
          <option value="warning">Warning</option>
          <option value="incident">Incident</option>
          <option value="suspension">Suspension</option>
          <option value="positive_recognition">Positive recognition</option>
        </select>
      </div>

      <Table
        emptyLabel="No discipline records match"
        onRowClick={setSelected}
        columns={[
          { key: 'student_name', header: 'Student', render: (r) => (
            <div className="flex items-center gap-2.5">
              <Avatar src={r.student_photo_url} name={r.student_name || '?'} size={28} />
              <span className="font-medium">{r.student_name || 'N/A'}</span>
            </div>
          ) },
          { key: 'date', header: 'Date', render: (r) => <span className="text-xs text-slate">{r.date}</span> },
          { key: 'category', header: 'Category', render: (r) => <Badge tone={CATEGORY_TONE[r.category]}>{label(r.category)}</Badge> },
          { key: 'description', header: 'Description', render: (r) => <span className="text-sm line-clamp-1 max-w-xs inline-block align-bottom truncate">{r.description}</span> },
          { key: 'action', header: 'Action taken', render: (r) => (r.action_taken ? <span className="text-xs">{r.action_taken}</span> : <span className="text-xs text-marigold">None yet</span>) },
          { key: 'status', header: 'Status', render: (r) => <Badge tone={STATUS_TONE[r.status]}>{label(r.status)}</Badge> },
        ]}
        rows={data.items}
      />
      <Pagination page={data.page} pages={data.pages} onChange={setPage} />

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New discipline record">
        <CreateForm onCreated={() => { setCreateOpen(false); load() }} />
      </Modal>

      <Modal open={!!selected} onClose={() => setSelected(null)} title="Discipline record" wide>
        {selected && <RecordDetail record={selected} onChanged={() => { setSelected(null); load() }} />}
      </Modal>
    </div>
  )
}

function RecordDetail({ record, onChanged }) {
  const { hasPermission } = useAuth()
  const canUpdate = hasPermission('discipline.update')
  const canResolve = hasPermission('discipline.resolve')
  const [action, setAction] = useState(record.action_taken || '')
  const [status, setStatus] = useState(record.status === 'resolved' ? 'open' : record.status)
  const [notify, setNotify] = useState(false)
  const [note, setNote] = useState(record.follow_up_note || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const resolved = record.status === 'resolved'

  const run = async (fn) => {
    setBusy(true)
    setError('')
    try { await fn(); onChanged() } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  const save = () => run(() => api.patch(`/api/discipline/${record.id}`, { action_taken: action, status, notify_guardians: notify }))
  const resolve = () => run(async () => {
    if (action !== (record.action_taken || '')) await api.patch(`/api/discipline/${record.id}`, { action_taken: action, notify_guardians: notify })
    await api.post(`/api/discipline/${record.id}/resolve`, { follow_up_note: note })
  })

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Avatar src={record.student_photo_url} name={record.student_name || '?'} size={42} />
        <div>
          <p className="font-medium">{record.student_name}</p>
          <p className="text-xs text-slate">{record.date}{record.reported_by_name ? ` · reported by ${record.reported_by_name}` : ''}</p>
        </div>
        <div className="ml-auto flex gap-2">
          <Badge tone={CATEGORY_TONE[record.category]}>{label(record.category)}</Badge>
          {record.severity && <Badge tone="slate">{record.severity} severity</Badge>}
          <Badge tone={STATUS_TONE[record.status]}>{label(record.status)}</Badge>
        </div>
      </div>

      <div className="card p-4 text-sm whitespace-pre-wrap">{record.description}</div>

      {resolved ? (
        <div className="card p-4 text-sm space-y-1">
          <p className="flex items-center gap-2 text-leaf font-medium"><CheckCircle2 size={16} /> Resolved</p>
          {record.action_taken && <p><span className="text-slate">Action taken: </span>{record.action_taken}</p>}
          {record.follow_up_note && <p><span className="text-slate">Follow up: </span>{record.follow_up_note}</p>}
        </div>
      ) : canUpdate || canResolve ? (
        <div className="space-y-4">
          <div>
            <label className="label">Action taken</label>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {ACTIONS.map((a) => (
                <button key={a} type="button" onClick={() => setAction(a)} className="text-[11px] px-2 py-1 rounded-md border border-rule text-slate hover:text-paper hover:border-leaf/40 transition-colors">{a}</button>
              ))}
            </div>
            <textarea rows={2} className="input" value={action} onChange={(e) => setAction(e.target.value)} placeholder="Describe what was done, or pick a suggestion above" />
          </div>
          {canUpdate && (
            <div className="grid grid-cols-2 gap-3 items-end">
              <div>
                <label className="label">Case status</label>
                <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="open">Open</option>
                  <option value="follow_up_needed">Follow up needed</option>
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm pb-2.5">
                <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} />
                <BellRing size={14} className="text-slate" /> Tell the parent or guardian
              </label>
            </div>
          )}
          {canUpdate && (
            <button onClick={save} disabled={busy} className="btn-secondary w-full">{busy ? 'Saving...' : 'Save action'}</button>
          )}
          {canResolve && (
            <div className="pt-4 border-t border-rule space-y-2">
              <label className="label">Close this case</label>
              <textarea rows={2} className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Follow up note: how was it settled?" />
              <button onClick={resolve} disabled={busy || !note.trim()} className="btn-primary w-full"><CheckCircle2 size={15} /> Mark as resolved</button>
            </div>
          )}
        </div>
      ) : (
        record.action_taken && <p className="text-sm"><span className="text-slate">Action taken: </span>{record.action_taken}</p>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}
    </div>
  )
}

function CreateForm({ onCreated }) {
  const [studentId, setStudentId] = useState('')
  const [form, setForm] = useState({ category: 'incident', severity: 'medium', description: '', action_taken: '', notify_guardians: false })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    if (!studentId) { setError('Pick a student'); return }
    setSubmitting(true)
    setError('')
    try {
      await api.post('/api/discipline', { ...form, student_id: studentId, severity: form.category === 'positive_recognition' ? undefined : form.severity })
      onCreated()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <StudentPicker value={studentId} onChange={setStudentId} />
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Category</label>
          <select className="input" value={form.category} onChange={set('category')}>
            <option value="warning">Warning</option>
            <option value="incident">Incident</option>
            <option value="suspension">Suspension</option>
            <option value="positive_recognition">Positive recognition</option>
          </select>
        </div>
        {form.category !== 'positive_recognition' && (
          <div>
            <label className="label">Severity</label>
            <select className="input" value={form.severity} onChange={set('severity')}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
        )}
      </div>
      <div>
        <label className="label">Description</label>
        <textarea required rows={3} className="input" value={form.description} onChange={set('description')} />
      </div>
      <div>
        <label className="label">Action taken (you can add or change this later)</label>
        <input className="input" value={form.action_taken} onChange={set('action_taken')} />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.notify_guardians} onChange={(e) => setForm((f) => ({ ...f, notify_guardians: e.target.checked }))} />
        Tell the parent or guardian about this
      </label>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Saving...' : 'Save record'}</button>
    </form>
  )
}

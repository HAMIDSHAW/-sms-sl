import { useEffect, useState } from 'react'
import { PlusCircle, Pencil } from 'lucide-react'
import { PageHeader, EmptyState, Modal } from '../../components/ui'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const TABS = ['Academic years', 'Classes', 'Subjects']

export default function AcademicsAdmin() {
  const [tab, setTab] = useState('Academic years')
  const [years, setYears] = useState([])
  const [classes, setClasses] = useState([])
  const [subjects, setSubjects] = useState([])
  const [editing, setEditing] = useState(null)
  const [yearFormOpen, setYearFormOpen] = useState(false)
  const { hasPermission } = useAuth()
  const canManage = hasPermission('academics.manage')

  const reload = () => {
    api.get('/api/academics/years').then((d) => setYears(asList(d)))
    api.get('/api/academics/classes').then((d) => setClasses(asList(d)))
    api.get('/api/academics/subjects').then((d) => setSubjects(asList(d)))
  }
  useEffect(() => { reload() }, [])

  const addClass = async () => {
    const name = prompt('Class name (e.g. JSS 1, SSS 2)')
    if (!name) return
    await api.post('/api/academics/classes', { name, order_index: classes.length })
    reload()
  }

  const addSubject = async () => {
    const name = prompt('Subject name')
    if (!name) return
    await api.post('/api/academics/subjects', { name })
    reload()
  }

  return (
    <div>
      <PageHeader eyebrow="Configuration" title="Academic structure" description="Years, terms, classes, sections, and subjects." />

      <div className="flex gap-1 border-b border-rule mb-6">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`relative px-4 py-2.5 text-sm font-medium transition-colors ${tab === t ? 'text-paper' : 'text-slate hover:text-paper'}`}
          >
            {t}
            {tab === t && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-leaf" />}
          </button>
        ))}
      </div>

      {tab === 'Academic years' && (
        <div>
          {canManage && (
            <button onClick={() => setYearFormOpen(true)} className="btn-secondary text-xs mb-4"><PlusCircle size={14} /> Add academic year</button>
          )}
          <div className="space-y-2">
            {years.length === 0 ? <EmptyState title="No academic years yet" /> : years.map((y) => (
              <div key={y.id} className="card p-4 flex items-center justify-between">
                <div>
                  <p className="font-medium text-sm">{y.name}</p>
                  <p className="text-xs text-slate">{y.start_date} → {y.end_date}</p>
                </div>
                {y.is_current && <span className="badge bg-leaf/12 text-leaf">Current</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'Classes' && (
        <div>
          {canManage && (
            <button onClick={addClass} className="btn-secondary text-xs mb-4"><PlusCircle size={14} /> Add class</button>
          )}
          <div className="grid grid-cols-3 gap-3">
            {classes.map((c) => (
              <button
                key={c.id} disabled={!canManage}
                onClick={() => canManage && setEditing({ type: 'class', item: c })}
                className={`card p-4 text-center font-medium text-sm relative group ${canManage ? 'hover:border-leaf/40 cursor-pointer' : 'cursor-default'}`}
              >
                {c.name}
                {canManage && <Pencil size={12} className="absolute top-2 right-2 text-slate opacity-0 group-hover:opacity-100 transition-opacity" />}
              </button>
            ))}
          </div>
        </div>
      )}

      {tab === 'Subjects' && (
        <div>
          {canManage && (
            <button onClick={addSubject} className="btn-secondary text-xs mb-4"><PlusCircle size={14} /> Add subject</button>
          )}
          <div className="grid grid-cols-3 gap-3">
            {subjects.map((s) => (
              <button
                key={s.id} disabled={!canManage}
                onClick={() => canManage && setEditing({ type: 'subject', item: s })}
                className={`card p-4 text-left relative group ${canManage ? 'hover:border-leaf/40 cursor-pointer' : 'cursor-default'}`}
              >
                <p className="font-medium text-sm">{s.name}</p>
                <p className="text-xs text-slate font-mono mt-0.5">{s.code}</p>
                {canManage && <Pencil size={12} className="absolute top-3 right-3 text-slate opacity-0 group-hover:opacity-100 transition-opacity" />}
              </button>
            ))}
          </div>
        </div>
      )}

      <Modal open={!!editing} onClose={() => setEditing(null)} title={`Edit ${editing?.type || ''}`}>
        {editing && (
          <EditForm
            editing={editing}
            onSaved={() => { setEditing(null); reload() }}
          />
        )}
      </Modal>

      <Modal open={yearFormOpen} onClose={() => setYearFormOpen(false)} title="Add academic year">
        <YearForm onCreated={() => { setYearFormOpen(false); reload() }} />
      </Modal>
    </div>
  )
}

function YearForm({ onCreated }) {
  const [form, setForm] = useState({ name: '', start_date: '', end_date: '', is_current: false })
  const [submitting, setSubmitting] = useState(false)
  const set = (f) => (e) => setForm((s) => ({ ...s, [f]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    await api.post('/api/academics/years', form)
    setSubmitting(false)
    onCreated()
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div><label className="label">Year name</label><input required className="input" placeholder="2027/2028" value={form.name} onChange={set('name')} /></div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="label">Start date</label><input required type="date" className="input" value={form.start_date} onChange={set('start_date')} /></div>
        <div><label className="label">End date</label><input required type="date" className="input" value={form.end_date} onChange={set('end_date')} /></div>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.is_current} onChange={(e) => setForm((s) => ({ ...s, is_current: e.target.checked }))} />
        Make this the current academic year
      </label>
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Creating…' : 'Create academic year'}</button>
    </form>
  )
}

function EditForm({ editing, onSaved }) {
  const { type, item } = editing
  const [name, setName] = useState(item.name)
  const [code, setCode] = useState(item.code || '')
  const [classMaster, setClassMaster] = useState(item.class_master_staff_id || '')
  const [staff, setStaff] = useState([])
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (type === 'class') api.get('/api/staff?per_page=200').then((d) => setStaff(d.items))
  }, [type])

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    if (type === 'class') {
      await api.patch(`/api/academics/classes/${item.id}`, { name, class_master_staff_id: classMaster || null })
    } else {
      await api.patch(`/api/academics/subjects/${item.id}`, { name, code })
    }
    setSubmitting(false)
    onSaved()
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="label">Name</label>
        <input required className="input" value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      {type === 'subject' && (
        <div>
          <label className="label">Code</label>
          <input className="input" value={code} onChange={(e) => setCode(e.target.value)} />
        </div>
      )}
      {type === 'class' && (
        <div>
          <label className="label">Class master</label>
          <select className="input" value={classMaster} onChange={(e) => setClassMaster(e.target.value)}>
            <option value="">None assigned</option>
            {staff.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
          </select>
        </div>
      )}
      <button type="submit" disabled={submitting} className="btn-primary w-full">
        {submitting ? 'Saving…' : 'Save changes'}
      </button>
    </form>
  )
}

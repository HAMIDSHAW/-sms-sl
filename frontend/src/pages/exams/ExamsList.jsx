import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PlusCircle } from 'lucide-react'
import { PageHeader, Table, Badge, Modal } from '../../components/ui'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const STATUS_TONE = { draft: 'slate', scheduled: 'sky', in_progress: 'marigold', completed: 'leaf' }

export default function ExamsList() {
  const [exams, setExams] = useState(null)
  const [createOpen, setCreateOpen] = useState(false)
  const navigate = useNavigate()
  const { hasPermission } = useAuth()

  const load = () => api.get('/api/exams').then((d) => setExams(asList(d)))
  useEffect(() => { load() }, [])

  return (
    <div>
      <PageHeader
        eyebrow="Assessment"
        title="Exams & Results"
        description="Examinations, marks, and published results."
        action={hasPermission('exams.create') && (
          <button onClick={() => setCreateOpen(true)} className="btn-primary text-xs">
            <PlusCircle size={14} /> New examination
          </button>
        )}
      />

      <Table
        emptyLabel="No examinations created yet"
        columns={[
          { key: 'name', header: 'Name', render: (r) => <span className="font-medium">{r.name}</span> },
          { key: 'start_date', header: 'Dates', render: (r) => <span className="text-xs text-slate">{r.start_date} → {r.end_date}</span> },
          { key: 'status', header: 'Status', render: (r) => <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge> },
        ]}
        rows={exams}
        onRowClick={(r) => navigate(`/exams/${r.id}/results`)}
      />

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New examination">
        <CreateExamForm onCreated={() => { setCreateOpen(false); load() }} />
      </Modal>
    </div>
  )
}

function CreateExamForm({ onCreated }) {
  const [years, setYears] = useState([])
  const [terms, setTerms] = useState([])
  const [form, setForm] = useState({ name: '', academic_year_id: '', term_id: '', start_date: '', end_date: '' })
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => { api.get('/api/academics/years').then((d) => setYears(asList(d))) }, [])
  useEffect(() => {
    if (form.academic_year_id) api.get(`/api/academics/years/${form.academic_year_id}/terms`).then((d) => setTerms(asList(d)))
  }, [form.academic_year_id])

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    await api.post('/api/exams', form)
    setSubmitting(false)
    onCreated()
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="label">Name</label>
        <input required className="input" value={form.name} onChange={set('name')} placeholder="First Term Examination" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Academic year</label>
          <select required className="input" value={form.academic_year_id} onChange={set('academic_year_id')}>
            <option value="">Select…</option>
            {years.map((y) => <option key={y.id} value={y.id}>{y.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Term</label>
          <select required className="input" value={form.term_id} onChange={set('term_id')}>
            <option value="">Select…</option>
            {terms.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Start date</label>
          <input required type="date" className="input" value={form.start_date} onChange={set('start_date')} />
        </div>
        <div>
          <label className="label">End date</label>
          <input required type="date" className="input" value={form.end_date} onChange={set('end_date')} />
        </div>
      </div>
      <button type="submit" disabled={submitting} className="btn-primary w-full">
        {submitting ? 'Creating…' : 'Create examination'}
      </button>
    </form>
  )
}

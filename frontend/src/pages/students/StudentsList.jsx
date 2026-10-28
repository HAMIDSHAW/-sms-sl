import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, UserPlus, Download, Trash2 } from 'lucide-react'
import { PageHeader, Table, Pagination, Badge, Modal } from '../../components/ui'
import { api, downloadFile } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const STATUS_TONE = { active: 'leaf', inactive: 'slate', graduated: 'sky', transferred: 'marigold', suspended: 'red' }

export default function StudentsList() {
  const [data, setData] = useState({ items: null, page: 1, pages: 1, total: 0 })
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const navigate = useNavigate()
  const { hasPermission } = useAuth()

  const load = () => {
    setLoading(true)
    const params = new URLSearchParams({ page, per_page: 15 })
    if (q) params.set('q', q)
    api.get(`/api/students?${params}`).then(setData).finally(() => setLoading(false))
  }

  const archiveStudent = async (r) => {
    if (!window.confirm(`Archive ${r.full_name}? Their records are kept (report cards, attendance history, etc.) but they'll no longer show as an active student.`)) return
    await api.delete(`/api/students/${r.id}`)
    load()
  }

  useEffect(() => { load() }, [page])
  useEffect(() => {
    const t = setTimeout(() => (page === 1 ? load() : setPage(1)), 300)
    return () => clearTimeout(t)
  }, [q])

  return (
    <div>
      <PageHeader
        eyebrow="Student information"
        title="Students"
        description="Every enrolled student's profile, guardians, and enrollment history."
        action={
          <div className="flex gap-2">
            {hasPermission('students.export') && (
              <button onClick={() => downloadFile('/api/students/export.xlsx', 'students_export.xlsx')} className="btn-secondary text-xs">
                <Download size={14} /> Export to Excel
              </button>
            )}
            {hasPermission('students.create') && (
              <button onClick={() => setCreateOpen(true)} className="btn-primary text-xs">
                <UserPlus size={14} /> Add student
              </button>
            )}
          </div>
        }
      />

      <div className="relative mb-5 max-w-sm">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate" />
        <input
          className="input pl-9"
          placeholder="Search by name, ID, or phone…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      <Table
        emptyLabel={q ? 'No students match your search' : 'No students yet. Add your first one.'}
        columns={[
          { key: 'student_number', header: 'ID', render: (r) => <span className="font-mono text-xs text-slate">{r.student_number}</span> },
          { key: 'full_name', header: 'Name', render: (r) => (
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-sky/15 flex items-center justify-center text-[10px] font-display font-semibold text-sky shrink-0 overflow-hidden">
                {r.photo_url ? <img src={r.photo_url} alt="" className="w-full h-full object-cover" /> : `${r.first_name?.[0] || ''}${r.last_name?.[0] || ''}`}
              </div>
              <span className="font-medium">{r.full_name}</span>
            </div>
          ) },
          { key: 'gender', header: 'Gender', render: (r) => r.gender || 'N/A' },
          { key: 'phone', header: 'Phone', render: (r) => r.phone || 'N/A' },
          { key: 'status', header: 'Status', render: (r) => <Badge tone={STATUS_TONE[r.status] || 'slate'}>{r.status}</Badge> },
          {
            key: 'actions', header: '', render: (r) => hasPermission('students.delete') && r.status !== 'inactive' && (
              <button
                onClick={(e) => { e.stopPropagation(); archiveStudent(r) }}
                className="text-slate hover:text-red-400 transition-colors p-1"
                title="Archive student"
              >
                <Trash2 size={14} />
              </button>
            ),
          },
        ]}
        rows={loading ? null : data.items}
        onRowClick={(r) => navigate(`/students/${r.id}`)}
      />

      <Pagination page={data.page} pages={data.pages} onChange={setPage} />

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Add student">
        <CreateStudentForm
          onCreated={() => {
            setCreateOpen(false)
            load()
          }}
        />
      </Modal>
    </div>
  )
}

function CreateStudentForm({ onCreated }) {
  const [form, setForm] = useState({ first_name: '', last_name: '', gender: '', date_of_birth: '', phone: '' })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api.post('/api/students', form)
      onCreated()
    } catch (err) {
      setError(err.data?.error || 'Could not create student')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">First name</label>
          <input required className="input" value={form.first_name} onChange={set('first_name')} />
        </div>
        <div>
          <label className="label">Last name</label>
          <input required className="input" value={form.last_name} onChange={set('last_name')} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Gender</label>
          <select className="input" value={form.gender} onChange={set('gender')}>
            <option value=""></option>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
        </div>
        <div>
          <label className="label">Date of birth</label>
          <input type="date" className="input" value={form.date_of_birth} onChange={set('date_of_birth')} />
        </div>
      </div>
      <div>
        <label className="label">Phone</label>
        <input className="input" value={form.phone} onChange={set('phone')} />
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting} className="btn-primary w-full">
        {submitting ? 'Creating…' : 'Create student'}
      </button>
    </form>
  )
}

import { useEffect, useState } from 'react'
import { GraduationCap, PlusCircle, LogOut, Building2 } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { PageHeader, Table, Badge, Modal } from '../components/ui'

export default function PlatformAdmin() {
  const { user, logout } = useAuth()
  const [schools, setSchools] = useState(null)
  const [createOpen, setCreateOpen] = useState(false)

  const load = () => api.get('/api/platform/schools').then(setSchools)
  useEffect(() => { load() }, [])

  const toggleStatus = async (school) => {
    await api.patch(`/api/platform/schools/${school.id}/status`, { is_active: !school.is_active })
    load()
  }

  return (
    <div className="min-h-screen bg-ink px-8 py-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-leaf flex items-center justify-center">
              <GraduationCap size={18} className="text-ink" strokeWidth={2.5} />
            </div>
            <div>
              <p className="font-display font-semibold text-sm">SchoolOS Platform</p>
              <p className="text-[11px] text-slate">{user?.first_name} {user?.last_name} · Platform Administrator</p>
            </div>
          </div>
          <button onClick={logout} className="btn-secondary text-xs"><LogOut size={14} /> Sign out</button>
        </div>

        <PageHeader
          eyebrow="Platform administration"
          title="Schools"
          description="Create and manage every school running on this platform. This view is separate from any individual school's dashboard. A platform admin isn't a member of any school."
          action={<button onClick={() => setCreateOpen(true)} className="btn-primary text-xs"><PlusCircle size={14} /> New school</button>}
        />

        <Table
          emptyLabel="No schools created yet"
          columns={[
            { key: 'name', header: 'School', render: (r) => (
              <div className="flex items-center gap-2">
                <Building2 size={14} className="text-slate" />
                <span className="font-medium">{r.name}</span>
              </div>
            ) },
            { key: 'short_name', header: 'Code', render: (r) => <span className="font-mono text-xs">{r.short_name || 'N/A'}</span> },
            { key: 'city', header: 'City', render: (r) => r.city || 'N/A' },
            { key: 'is_active', header: 'Status', render: (r) => (
              <button onClick={() => toggleStatus(r)}>
                <Badge tone={r.is_active ? 'leaf' : 'red'}>{r.is_active ? 'Active' : 'Suspended'}</Badge>
              </button>
            ) },
          ]}
          rows={schools}
        />

        <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create a new school">
          <CreateSchoolForm onCreated={() => { setCreateOpen(false); load() }} />
        </Modal>
      </div>
    </div>
  )
}

function CreateSchoolForm({ onCreated }) {
  const [form, setForm] = useState({
    name: '', short_name: '', owner_email: '', owner_password: '', owner_first_name: '', owner_last_name: '',
  })
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const set = (f) => (e) => setForm((s) => ({ ...s, [f]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api.post('/api/platform/schools', form)
      onCreated()
    } catch (err) {
      setError(err.data?.error || 'Could not create school')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div><label className="label">School name</label><input required className="input" value={form.name} onChange={set('name')} /></div>
      <div><label className="label">Short code</label><input className="input" value={form.short_name} onChange={set('short_name')} placeholder="e.g. KGSS" /></div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="label">Owner first name</label><input className="input" value={form.owner_first_name} onChange={set('owner_first_name')} /></div>
        <div><label className="label">Owner last name</label><input className="input" value={form.owner_last_name} onChange={set('owner_last_name')} /></div>
      </div>
      <div><label className="label">Owner email</label><input required type="email" className="input" value={form.owner_email} onChange={set('owner_email')} /></div>
      <div><label className="label">Owner temporary password</label><input required type="password" className="input" value={form.owner_password} onChange={set('owner_password')} /></div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Creating…' : 'Create school'}</button>
    </form>
  )
}

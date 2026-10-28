import { useEffect, useState } from 'react'
import { Download, Trash2, KeyRound, Copy, Pencil } from 'lucide-react'
import { PageHeader, Table, Badge, Pagination, Modal, PhoneLink } from '../../components/ui'
import { api, downloadFile } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'
import EditPersonModal from '../../components/EditPersonModal'

const TYPE_TONE = { teacher: 'leaf', administrator: 'sky', support: 'slate' }

export default function StaffList() {
  const { hasPermission } = useAuth()
  const [data, setData] = useState({ items: null, page: 1, pages: 1 })
  const [page, setPage] = useState(1)
  const [reset, setReset] = useState(null) // { name, email, temporary_password }
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(null) // the full staff record being edited

  const load = () => api.get(`/api/staff?page=${page}&per_page=15`).then(setData)
  useEffect(() => { load() }, [page])

  // The list never carries salaries; the detail record does, but only for people allowed to see them.
  const openEdit = async (r) => {
    setError('')
    try { setEditing(await api.get(`/api/staff/${r.id}`)) } catch (err) { setError(err.message) }
  }

  const archiveStaff = async (r) => {
    if (!window.confirm(`Archive ${r.full_name}? Their records are kept but they'll no longer show as active staff.`)) return
    await api.delete(`/api/staff/${r.id}`)
    load()
  }

  const resetPassword = async (r) => {
    if (!window.confirm(`Give ${r.full_name} a temporary password? They will be signed out everywhere and must choose a new password at next sign in.`)) return
    setError('')
    try {
      const res = await api.post(`/api/users/${r.user_id}/reset-password`, {})
      setReset({ name: r.full_name, email: res.email, temporary_password: res.temporary_password })
    } catch (err) { setError(err.message) }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Human resources"
        title="Staff"
        description="Teachers, administrators, and support staff."
        action={
          hasPermission('staff.view') && (
            <button onClick={() => downloadFile("/api/staff/export.xlsx", "staff_export.xlsx")} className="btn-secondary text-xs">
              <Download size={14} /> Export Excel
            </button>
          )
        }
      />
      {error && <p className="text-sm text-red-400 mb-3">{error}</p>}
      <Table
        columns={[
          { key: 'employee_number', header: 'ID', render: (r) => <span className="font-mono text-xs text-slate">{r.employee_number}</span> },
          { key: 'full_name', header: 'Name', render: (r) => (
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-leaf/15 flex items-center justify-center text-[10px] font-display font-semibold text-leaf shrink-0 overflow-hidden">
                {r.photo_url ? <img src={r.photo_url} alt="" className="w-full h-full object-cover" /> : `${r.first_name?.[0] || ''}${r.last_name?.[0] || ''}`}
              </div>
              <span className="font-medium">{r.full_name}</span>
            </div>
          ) },
          { key: 'staff_type', header: 'Type', render: (r) => <Badge tone={TYPE_TONE[r.staff_type] || 'slate'}>{r.staff_type}</Badge> },
          { key: 'position', header: 'Position', render: (r) => r.position || 'N/A' },
          { key: 'phone', header: 'Phone', render: (r) => <PhoneLink value={r.phone} /> },
          { key: 'address', header: 'Lives at', render: (r) => (r.address ? <span className="text-xs max-w-[220px] inline-block whitespace-normal">{r.address}</span> : <span className="text-xs text-slate">Not given</span>) },
          { key: 'status', header: 'Status', render: (r) => <Badge tone={r.status === 'active' ? 'leaf' : 'slate'}>{r.status || 'active'}</Badge> },
          {
            key: 'actions', header: '', render: (r) => (
              <div className="flex items-center gap-1 justify-end">
                {hasPermission('staff.update') && (
                  <button
                    onClick={(e) => { e.stopPropagation(); openEdit(r) }}
                    className="text-slate hover:text-leaf transition-colors p-1"
                    title="Edit name and details" aria-label={`Edit ${r.full_name}`}
                  >
                    <Pencil size={14} />
                  </button>
                )}
                {hasPermission('users.update') && r.user_id && r.status !== 'terminated' && (
                  <button
                    onClick={(e) => { e.stopPropagation(); resetPassword(r) }}
                    className="text-slate hover:text-leaf transition-colors p-1"
                    title="Reset password" aria-label={`Reset password for ${r.full_name}`}
                  >
                    <KeyRound size={14} />
                  </button>
                )}
                {hasPermission('staff.delete') && r.status !== 'terminated' && (
                  <button
                    onClick={(e) => { e.stopPropagation(); archiveStaff(r) }}
                    className="text-slate hover:text-red-400 transition-colors p-1"
                    title="Archive staff member" aria-label={`Archive ${r.full_name}`}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            ),
          },
        ]}
        rows={data.items}
      />
      <Pagination page={data.page} pages={data.pages} onChange={setPage} />

      <EditPersonModal
        open={!!editing} onClose={() => setEditing(null)} title={editing ? `Edit ${editing.full_name}` : ''}
        endpoint={editing ? `/api/staff/${editing.id}` : ''} initial={editing}
        note="Names are official and only an administrator can change them. A new name also appears on the person's login."
        onSaved={load}
        fields={[
          { key: 'title', label: 'Title', type: 'select', options: [['', 'None'], ['Mr', 'Mr'], ['Mrs', 'Mrs'], ['Miss', 'Miss'], ['Madam', 'Madam'], ['Dr', 'Dr'], ['Rev', 'Rev'], ['Pa', 'Pa']] },
          { key: 'status', label: 'Status', type: 'select', options: [['active', 'Active'], ['on_leave', 'On leave'], ['terminated', 'Left the school']] },
          { key: 'first_name', label: 'First name', required: true },
          { key: 'last_name', label: 'Last name', required: true },
          { key: 'phone', label: 'Phone', type: 'tel' },
          { key: 'email', label: 'Email', type: 'email' },
          { key: 'position', label: 'Position' },
          { key: 'department', label: 'Department' },
          { key: 'address', label: 'Lives at', wide: true },
          ...(hasPermission('hr.payroll.manage') && editing && 'base_salary' in editing ? [
            { key: 'base_salary', label: 'Monthly base salary (Le)', type: 'number', wide: true, hint: 'A raise or a cut is entered here. It is used for every payroll run from now on, and the change is recorded in the audit log. Marking someone as "Left the school" takes them off any unpaid payroll.' },
          ] : []),
        ]}
      />

      <Modal open={!!reset} onClose={() => setReset(null)} title="Temporary password">
        {reset && (
          <div className="space-y-4">
            <p className="text-sm text-slate">
              Give this to <span className="text-paper font-medium">{reset.name}</span> ({reset.email}) in person or by phone.
              It is shown only once. They will be asked to choose their own password when they sign in.
            </p>
            <div className="card p-4 flex items-center justify-between gap-3">
              <code className="font-mono text-lg tracking-wide select-all">{reset.temporary_password}</code>
              <button
                className="btn-secondary !py-1.5 text-xs" aria-label="Copy temporary password"
                onClick={() => navigator.clipboard?.writeText(reset.temporary_password)}
              >
                <Copy size={13} /> Copy
              </button>
            </div>
            <button className="btn-primary w-full" onClick={() => setReset(null)}>Done</button>
          </div>
        )}
      </Modal>
    </div>
  )
}

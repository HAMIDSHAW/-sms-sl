import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Phone, MapPin, Briefcase, Pencil } from 'lucide-react'
import { PageHeader, Table, Badge, PhoneLink } from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'
import EditPersonModal from '../../components/EditPersonModal'

const STATUS_TONE = { active: 'leaf', inactive: 'slate', graduated: 'sky', transferred: 'marigold', suspended: 'red' }

export default function GuardianProfile() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const [guardian, setGuardian] = useState(null)
  const [editOpen, setEditOpen] = useState(false)

  useEffect(() => {
    api.get(`/api/guardians/${id}`).then(setGuardian)
  }, [id])

  if (!guardian) return null

  return (
    <div>
      <button onClick={() => navigate('/guardians')} className="flex items-center gap-1.5 text-sm text-slate hover:text-paper mb-4 transition-colors">
        <ArrowLeft size={14} /> Back to guardians
      </button>

      <PageHeader
        eyebrow="Guardian" title={guardian.full_name} description="Contact details and linked children."
        action={hasPermission('parents.update') && (
          <button onClick={() => setEditOpen(true)} className="btn-secondary text-xs"><Pencil size={14} /> Edit details</button>
        )}
      />
      <EditPersonModal
        open={editOpen} onClose={() => setEditOpen(false)} title="Edit guardian"
        endpoint={`/api/guardians/${guardian.id}`} initial={guardian} onSaved={setGuardian}
        note="A new name also appears on the guardian's login."
        fields={[
          { key: 'first_name', label: 'First name', required: true },
          { key: 'last_name', label: 'Last name', required: true },
          { key: 'phone', label: 'Phone', type: 'tel' },
          { key: 'occupation', label: 'Occupation' },
          { key: 'address', label: 'Address', wide: true },
        ]}
      />

      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="card p-4 flex items-center gap-2.5">
          <Phone size={15} className="text-slate shrink-0" />
          <span className="text-sm"><PhoneLink value={guardian.phone} /></span>
        </div>
        <div className="card p-4 flex items-center gap-2.5">
          <Briefcase size={15} className="text-slate shrink-0" />
          <span className="text-sm">{guardian.occupation || 'N/A'}</span>
        </div>
        <div className="card p-4 flex items-center gap-2.5">
          <MapPin size={15} className="text-slate shrink-0" />
          <span className="text-sm">{guardian.address || 'N/A'}</span>
        </div>
      </div>

      <p className="eyebrow mb-3">Children</p>
      <Table
        emptyLabel="No students linked to this guardian"
        onRowClick={(r) => navigate(`/students/${r.id}`)}
        columns={[
          { key: 'full_name', header: 'Name', render: (r) => (
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-full bg-sky/15 flex items-center justify-center text-[10px] font-display font-semibold text-sky shrink-0">
                {r.first_name?.[0]}{r.last_name?.[0]}
              </div>
              <span className="font-medium">{r.full_name}</span>
            </div>
          ) },
          { key: 'student_number', header: 'Student #', render: (r) => <span className="font-mono text-xs">{r.student_number}</span> },
          { key: 'status', header: 'Status', render: (r) => <Badge tone={STATUS_TONE[r.status]}>{r.status}</Badge> },
        ]}
        rows={guardian.children}
      />
    </div>
  )
}

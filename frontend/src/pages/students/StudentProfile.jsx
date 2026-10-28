import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Phone, Mail, MapPin, Calendar, Wallet, History, Pencil } from 'lucide-react'
import { Badge, PhoneLink, EmailLink } from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'
import EditPersonModal from '../../components/EditPersonModal'

export default function StudentProfile() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const [student, setStudent] = useState(null)
  const [tab, setTab] = useState('Overview')
  const [history, setHistory] = useState(null)
  const [editOpen, setEditOpen] = useState(false)

  const canViewAudit = hasPermission('audit.view')
  const TABS = ['Overview', 'Guardians', ...(canViewAudit ? ['Activity'] : [])]

  useEffect(() => {
    api.get(`/api/students/${id}`).then(setStudent)
  }, [id])

  useEffect(() => {
    if (tab === 'Activity' && canViewAudit) {
      api.get(`/api/audit-logs?entity_type=student&entity_id=${id}`).then((r) => setHistory(r.items))
    }
  }, [tab, id])

  if (!student) return <div className="text-slate text-sm">Loading…</div>

  return (
    <div>
      <button onClick={() => navigate('/students')} className="flex items-center gap-1.5 text-sm text-slate hover:text-paper transition-colors mb-6">
        <ArrowLeft size={15} /> Back to students
      </button>

      <div className="flex items-center gap-4 mb-8">
        <div className="w-16 h-16 rounded-xl bg-sky/15 flex items-center justify-center font-display text-xl font-semibold text-sky shrink-0">
          {student.first_name[0]}{student.last_name[0]}
        </div>
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">{student.full_name}</h1>
          <p className="font-mono text-xs text-slate mt-0.5">{student.student_number}</p>
        </div>
        <Badge tone="leaf">{student.status}</Badge>
        <div className="ml-auto flex gap-2">
          {hasPermission('students.update') && (
            <button onClick={() => setEditOpen(true)} className="btn-secondary text-xs"><Pencil size={14} /> Edit name</button>
          )}
          {hasPermission('finance.view') && (
            <button onClick={() => navigate(`/finance/ledger/${student.id}`)} className="btn-secondary text-xs">
              <Wallet size={14} /> View fee ledger
            </button>
          )}
        </div>
      </div>

      <EditPersonModal
        open={editOpen} onClose={() => setEditOpen(false)} title="Edit student name"
        endpoint={`/api/students/${student.id}`} initial={student} onSaved={setStudent}
        note="The name on the record is the official one. Students cannot change it themselves. A new name also appears on their login."
        fields={[
          { key: 'first_name', label: 'First name', required: true },
          { key: 'middle_name', label: 'Middle name' },
          { key: 'last_name', label: 'Last name', required: true, wide: true },
        ]}
      />

      <div className="flex gap-1 border-b border-rule mb-6">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`relative px-4 py-2.5 text-sm font-medium transition-colors ${tab === t ? 'text-paper' : 'text-slate hover:text-paper'}`}
          >
            {t}
            {tab === t && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-leaf" />
            )}
          </button>
        ))}
      </div>

      {tab === 'Overview' && (
        <div className="grid md:grid-cols-2 gap-4">
          <InfoRow icon={Calendar} label="Date of birth" value={student.date_of_birth || 'N/A'} />
          <InfoRow icon={Phone} label="Phone" value={<PhoneLink value={student.phone} />} />
          <InfoRow icon={Mail} label="Email" value={<EmailLink value={student.email} />} />
          <InfoRow icon={MapPin} label="Address" value={student.address || 'N/A'} />
        </div>
      )}

      {tab === 'Guardians' && (
        <div className="space-y-3">
          {student.guardians?.length ? (
            student.guardians.map((g) => (
              <button
                key={g.guardian_id}
                onClick={() => navigate(`/guardians/${g.guardian_id}`)}
                className="card p-4 flex items-center justify-between w-full text-left hover:border-leaf/40 transition-colors"
              >
                <div>
                  <p className="font-medium text-sm">{g.guardian?.full_name}</p>
                  <p className="text-xs text-slate mt-0.5">{g.relationship_type} · {g.guardian?.phone || 'no phone on file'}</p>
                </div>
                {g.is_primary_contact && <Badge tone="marigold">Primary contact</Badge>}
              </button>
            ))
          ) : (
            <p className="text-sm text-slate">No guardians linked yet.</p>
          )}
        </div>
      )}

      {tab === 'Activity' && (
        <div className="space-y-2">
          {history === null ? null : history.length === 0 ? (
            <p className="text-sm text-slate">No recorded activity yet.</p>
          ) : (
            history.map((h) => (
              <div key={h.id} className="card p-4 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <History size={14} className="text-slate shrink-0" />
                  <div>
                    <p className="text-sm font-medium">{(h.action || 'unknown').replace(/[._]/g, ' ')}</p>
                    <p className="text-xs text-slate">{h.user_name || 'System'} ({h.user_email || 'N/A'})</p>
                  </div>
                </div>
                <span className="text-xs text-slate">{new Date(h.created_at).toLocaleString()}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

function InfoRow({ icon: Icon, label, value }) {
  return (
    <div className="card p-4 flex items-center gap-3">
      <div className="w-9 h-9 rounded-lg bg-white/5 flex items-center justify-center shrink-0">
        <Icon size={16} className="text-slate" />
      </div>
      <div>
        <p className="text-xs text-slate">{label}</p>
        <p className="text-sm font-medium mt-0.5">{value}</p>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { Check, Lock, UserCircle } from 'lucide-react'
import { PageHeader, ImageUpload } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../context/AuthContext'

export default function Profile() {
  const { user, refreshMe } = useAuth()
  const [form, setForm] = useState({
    phone: user?.phone || '',
    address: user?.address || '',
    photo_url: user?.photo_url || '',
  })
  const [saved, setSaved] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const setPhoto = async (url) => {
    setForm((f) => ({ ...f, photo_url: url }))
    // Photo saves immediately on upload, no reason to make someone hit
    // "Save changes" a second time just to keep a picture they already
    // picked. Phone still waits for the form submit below.
    await api.patch('/api/auth/me', { photo_url: url })
    refreshMe()
  }

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    await api.patch('/api/auth/me', { phone: form.phone, address: form.address })
    setSubmitting(false)
    setSaved(true)
    refreshMe()
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="max-w-lg">
      <PageHeader eyebrow="Account" title="My profile" description="Update your contact details, home address and photo." />

      <div className="card p-6">
        <div className="flex items-center gap-3 mb-6">
          <ImageUpload value={form.photo_url} onChange={setPhoto} fallback={UserCircle} />
          <div>
            <p className="font-display font-semibold">{user?.first_name} {user?.last_name}</p>
            <p className="text-xs text-slate">{user?.email}</p>
            {(user?.staff_position || user?.employee_number) && (
              <p className="text-xs text-slate mt-0.5">{[user.staff_position, user.employee_number].filter(Boolean).join(' · ')}</p>
            )}
            {user?.is_class_master && (
              <p className="text-xs text-leaf mt-0.5">Class master of {user.class_master_of.map((c) => c.name).join(', ')}</p>
            )}
          </div>
        </div>

        <div className="flex items-start gap-2 rounded-lg bg-white/[0.03] border border-rule px-3.5 py-3 mb-5">
          <Lock size={14} className="text-slate mt-0.5 shrink-0" />
          <p className="text-xs text-slate">
            Your official name is set by the school and can't be changed here. Contact your school
            administrator if it needs correcting.
          </p>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Phone</label>
            <input className="input" value={form.phone} onChange={set('phone')} />
          </div>
          <div>
            <label className="label">Home address</label>
            <textarea
              rows={3} maxLength={500} className="input" value={form.address} onChange={set('address')}
              placeholder="Where you live. A landmark helps if there is no street name, e.g. behind Kenema Government Hospital"
            />
            <p className="text-[11px] text-slate mt-1">The school can see this so it knows where to reach you.</p>
          </div>
          <button type="submit" disabled={submitting} className="btn-primary">
            {saved ? <><Check size={16} /> Saved</> : submitting ? 'Saving...' : 'Save changes'}
          </button>
        </form>
      </div>
    </div>
  )
}

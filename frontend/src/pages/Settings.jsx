import { useEffect, useState } from 'react'
import { Check, School as SchoolIcon } from 'lucide-react'
import { PageHeader, ImageUpload } from '../components/ui'
import { api } from '../lib/api'
import { useSchool } from '../context/SchoolContext'

export default function Settings() {
  const { school, setSchool } = useSchool()
  const [form, setForm] = useState(null)
  const [saved, setSaved] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (school) {
      setForm({
        name: school.name || '', short_name: school.short_name || '', motto: school.motto || '',
        address: school.address || '', city: school.city || '', district: school.district || '',
        country: school.country || '', phone: school.phone || '', email: school.email || '',
        website: school.website || '', logo_url: school.logo_url || '',
      })
    }
  }, [school])

  if (!form) return null

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    const updated = await api.patch('/api/school', form)
    setSchool(updated)
    setSubmitting(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="max-w-2xl">
      <PageHeader eyebrow="Configuration" title="School settings" description="Your school's identity and contact details, used throughout the platform." />

      <form onSubmit={submit} className="card p-6 space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label">School name</label><input required className="input" value={form.name} onChange={set('name')} /></div>
          <div><label className="label">Short code</label><input className="input" value={form.short_name} onChange={set('short_name')} /></div>
        </div>
        <div><label className="label">Motto</label><input className="input" value={form.motto} onChange={set('motto')} /></div>
        <div><label className="label">Address</label><input className="input" value={form.address} onChange={set('address')} /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label">City</label><input className="input" value={form.city} onChange={set('city')} /></div>
          <div><label className="label">District</label><input className="input" value={form.district} onChange={set('district')} /></div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="label">Phone</label><input className="input" value={form.phone} onChange={set('phone')} /></div>
          <div><label className="label">Email</label><input type="email" className="input" value={form.email} onChange={set('email')} /></div>
        </div>
        <div><label className="label">Website</label><input className="input" value={form.website} onChange={set('website')} /></div>
        <div>
          <label className="label">Logo</label>
          <div className="flex items-center gap-3">
            <ImageUpload
              value={form.logo_url} shape="square" size={64} fallback={SchoolIcon}
              onChange={async (url) => {
                setForm((f) => ({ ...f, logo_url: url }))
                const updated = await api.patch('/api/school', { logo_url: url })
                setSchool(updated)
              }}
            />
            <p className="text-xs text-slate">Shown on the sidebar and printed reports. Click to upload.</p>
          </div>
        </div>
        <button type="submit" disabled={submitting} className="btn-primary">
          {saved ? <><Check size={16} /> Saved</> : submitting ? 'Saving…' : 'Save changes'}
        </button>
      </form>
    </div>
  )
}

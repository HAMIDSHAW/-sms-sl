import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Megaphone, PlusCircle } from 'lucide-react'
import { PageHeader, EmptyState, Modal, Badge } from '../../components/ui'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const AUDIENCE_TONE = { school: 'leaf', teachers: 'sky', students: 'marigold', parents: 'marigold', staff: 'sky', class: 'leaf', section: 'leaf' }
const AUDIENCE_LABEL = { school: 'Entire school', teachers: 'Teachers', students: 'Students', parents: 'Parents', staff: 'Staff', class: 'Class', section: 'Section' }

export default function Announcements() {
  const [items, setItems] = useState([])
  const [createOpen, setCreateOpen] = useState(false)
  const { hasPermission } = useAuth()

  const load = () => api.get('/api/announcements').then((d) => setItems(asList(d)))
  useEffect(() => { load() }, [])

  return (
    <div>
      <PageHeader
        eyebrow="Communication"
        title="Announcements"
        description="School-wide and targeted notices."
        action={
          hasPermission('announcements.create') && (
            <button onClick={() => setCreateOpen(true)} className="btn-primary text-xs"><PlusCircle size={14} /> New announcement</button>
          )
        }
      />

      {items.length === 0 ? (
        <EmptyState icon={Megaphone} title="No announcements yet" />
      ) : (
        <div className="space-y-3">
          {items.map((a, i) => (
            <motion.div
              key={a.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
              className="card p-5"
            >
              <div className="flex items-start justify-between mb-2 gap-3">
                <h3 className="font-display font-semibold">{a.title}</h3>
                <div className="flex flex-wrap gap-1 justify-end shrink-0">
                  {(a.audience_types?.length ? a.audience_types : [a.audience_type]).map((t) => (
                    <Badge key={t} tone={AUDIENCE_TONE[t] || 'slate'}>{AUDIENCE_LABEL[t] || t}</Badge>
                  ))}
                </div>
              </div>
              <p className="text-sm text-slate">{a.body}</p>
              <p className="text-[11px] text-slate mt-3">{new Date(a.created_at).toLocaleDateString()}</p>
            </motion.div>
          ))}
        </div>
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New announcement">
        <CreateForm onCreated={() => { setCreateOpen(false); load() }} />
      </Modal>
    </div>
  )
}

const AUDIENCE_OPTIONS = [
  { value: 'school', label: 'Entire school' },
  { value: 'teachers', label: 'Teachers' },
  { value: 'students', label: 'Students' },
  { value: 'parents', label: 'Parents' },
  { value: 'staff', label: 'Staff' },
  { value: 'class', label: 'Specific class' },
]

function CreateForm({ onCreated }) {
  const [classes, setClasses] = useState([])
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [audienceTypes, setAudienceTypes] = useState(['school'])
  const [audienceClassId, setAudienceClassId] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => { api.get('/api/academics/classes').then((d) => setClasses(asList(d))) }, [])

  const toggle = (value) => {
    setAudienceTypes((prev) => {
      if (value === 'school') return ['school'] // "entire school" is exclusive of the others
      const withoutSchool = prev.filter((v) => v !== 'school')
      return withoutSchool.includes(value)
        ? withoutSchool.filter((v) => v !== value)
        : [...withoutSchool, value]
    })
  }

  const submit = async (e) => {
    e.preventDefault()
    if (audienceTypes.length === 0) {
      setError('Pick at least one audience')
      return
    }
    if (audienceTypes.includes('class') && !audienceClassId) {
      setError('Pick a class')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await api.post('/api/announcements', {
        title, body, audience_types: audienceTypes,
        audience_class_id: audienceTypes.includes('class') ? audienceClassId : undefined,
      })
      onCreated()
    } catch (err) {
      setError(err.data?.error || 'Could not publish')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="label">Title</label>
        <input required className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>
      <div>
        <label className="label">Message</label>
        <textarea required rows={3} className="input" value={body} onChange={(e) => setBody(e.target.value)} />
      </div>
      <div>
        <label className="label">Audience: select one or more</label>
        <div className="grid grid-cols-2 gap-2 mt-1">
          {AUDIENCE_OPTIONS.map((o) => (
            <label key={o.value} className="flex items-center gap-2 text-sm px-2.5 py-1.5 rounded-lg border border-rule cursor-pointer hover:bg-white/[0.03]">
              <input
                type="checkbox"
                checked={audienceTypes.includes(o.value)}
                onChange={() => toggle(o.value)}
              />
              {o.label}
            </label>
          ))}
        </div>
      </div>
      {audienceTypes.includes('class') && (
        <div>
          <label className="label">Class</label>
          <select required className="input" value={audienceClassId} onChange={(e) => setAudienceClassId(e.target.value)}>
            <option value="">Select…</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting} className="btn-primary w-full">
        {submitting ? 'Publishing…' : 'Publish announcement'}
      </button>
    </form>
  )
}

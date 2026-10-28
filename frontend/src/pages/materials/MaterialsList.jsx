import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { FileText, Link as LinkIcon, Image, Video, Sheet, PlusCircle, Trash2, Search } from 'lucide-react'
import { PageHeader, EmptyState, Modal, FileUpload, BlockSkeleton } from '../../components/ui'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const TYPE_ICON = { pdf: FileText, docx: FileText, pptx: FileText, xlsx: Sheet, image: Image, video: Video, link: LinkIcon }

export default function MaterialsList() {
  const [materials, setMaterials] = useState(null)
  const [createOpen, setCreateOpen] = useState(false)
  const { hasPermission } = useAuth()
  const canManage = hasPermission('materials.manage')
  const [q, setQ] = useState('')
  const [classes, setClasses] = useState([])
  const [classId, setClassId] = useState('')

  const load = () => {
    const params = new URLSearchParams()
    if (q.trim()) params.set('q', q.trim())
    if (classId) params.set('class_id', classId)
    const qs = params.toString()
    return api.get(`/api/materials${qs ? `?${qs}` : ''}`).then((d) => setMaterials(asList(d)))
  }
  // Search as you type, waiting a moment after the last key press.
  useEffect(() => {
    const t = setTimeout(load, 250)
    return () => clearTimeout(t)
  }, [q, classId])
  useEffect(() => { if (canManage) api.get('/api/academics/classes').then((d) => setClasses(asList(d))).catch(() => {}) }, [])

  const deleteMaterial = async (e, m) => {
    e.preventDefault()
    e.stopPropagation()
    if (!window.confirm(`Remove "${m.title}"?`)) return
    await api.delete(`/api/materials/${m.id}`)
    load()
  }

  return (
    <div>
      <PageHeader
        eyebrow="Resources"
        title="Learning materials"
        description="Notes, slides, and links shared by your teachers."
        action={canManage && (
          <button onClick={() => setCreateOpen(true)} className="btn-primary text-xs"><PlusCircle size={14} /> Share material</button>
        )}
      />

      <div className="flex flex-wrap gap-3 mb-5">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate" />
          <input className="input pl-9" placeholder="Search materials by title or description" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {canManage && classes.length > 0 && (
          <select aria-label="Filter by class" className="input w-44" value={classId} onChange={(e) => setClassId(e.target.value)}>
            <option value="">All classes</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
      </div>

      {materials == null ? (
        <div className="grid md:grid-cols-3 gap-4"><BlockSkeleton rows={3} height={110} /></div>
      ) : materials.length === 0 ? (
        <EmptyState title={q || classId ? 'No material matches your search' : 'No materials shared yet'} />
      ) : (
        <div className="grid md:grid-cols-3 gap-4">
          {materials.map((m, i) => {
            const Icon = TYPE_ICON[m.material_type] || FileText
            return (
              <motion.a
                key={m.id}
                href={m.file_url || m.external_link || '#'}
                target="_blank" rel="noreferrer"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className="card p-4 hover:border-leaf/40 transition-colors block relative group"
              >
                <div className="w-9 h-9 rounded-lg bg-sky/12 flex items-center justify-center mb-3">
                  <Icon size={16} className="text-sky" />
                </div>
                <p className="font-medium text-sm mb-1 pr-6">{m.title}</p>
                {m.description && <p className="text-xs text-slate line-clamp-2">{m.description}</p>}
                <p className="text-[11px] text-slate mt-2">
                  {[m.subject_name, m.class_name].filter(Boolean).join(', ')}{m.staff_name ? ` · by ${m.staff_name}` : ''}
                </p>
                {m.can_delete && (
                  <button
                    onClick={(e) => deleteMaterial(e, m)}
                    className="absolute top-3 right-3 text-slate hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity p-1"
                    title="Remove material"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </motion.a>
            )
          })}
        </div>
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Share a material">
        <CreateMaterialForm onCreated={() => { setCreateOpen(false); load() }} />
      </Modal>
    </div>
  )
}

function CreateMaterialForm({ onCreated }) {
  const [classes, setClasses] = useState([])
  const [subjects, setSubjects] = useState([])
  const [years, setYears] = useState([])
  const [form, setForm] = useState({ title: '', description: '', class_id: '', subject_id: '', external_link: '', file_url: '' })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.get('/api/academics/classes').then((d) => setClasses(asList(d)))
    api.get('/api/academics/subjects').then((d) => setSubjects(asList(d)))
    api.get('/api/academics/years').then((d) => setYears(asList(d)))
  }, [])

  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    if (!form.file_url && !form.external_link) {
      setError('Attach a file or add a link')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const currentYear = years.find((y) => y.is_current) || years[0]
      await api.post('/api/materials', {
        ...form, academic_year_id: currentYear?.id,
        material_type: form.file_url ? (form.file_url.split('.').pop().toLowerCase() === 'pdf' ? 'pdf' : 'docx') : 'link',
      })
      onCreated()
    } catch (err) {
      setError(err.data?.error || 'Could not share material')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="label">Title</label>
        <input required className="input" value={form.title} onChange={set('title')} />
      </div>
      <div>
        <label className="label">Description (optional)</label>
        <textarea rows={2} className="input" value={form.description} onChange={set('description')} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Class</label>
          <select required className="input" value={form.class_id} onChange={set('class_id')}>
            <option value="">Select…</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Subject</label>
          <select required className="input" value={form.subject_id} onChange={set('subject_id')}>
            <option value="">Select…</option>
            {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      </div>
      <div>
        <label className="label">File</label>
        <FileUpload value={form.file_url} onChange={(url) => setForm((f) => ({ ...f, file_url: url }))} label="Upload a file" />
      </div>
      <div>
        <label className="label">Or a link (optional, instead of a file)</label>
        <input className="input" placeholder="https://…" value={form.external_link} onChange={set('external_link')} />
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Sharing…' : 'Share material'}</button>
    </form>
  )
}

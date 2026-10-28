import { useEffect, useState } from 'react'
import { PlusCircle, Wrench, CheckCircle2, History, Trash2 } from 'lucide-react'
import { PageHeader, Table, Badge, Modal, Pagination } from '../../components/ui'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const STATUS_TONE = { in_use: 'leaf', in_storage: 'sky', in_stock: 'sky', under_maintenance: 'marigold', damaged: 'red', disposed: 'slate' }

export default function Inventory() {
  const { hasPermission } = useAuth()
  const [data, setData] = useState({ items: null, page: 1, pages: 1 })
  const [page, setPage] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)
  const [maintainFor, setMaintainFor] = useState(null)
  const [historyFor, setHistoryFor] = useState(null)
  const [error, setError] = useState('')

  const load = () => api.get(`/api/inventory/items?page=${page}&per_page=15`).then(setData)
  useEffect(() => { load() }, [page])

  const backInUse = async (item) => {
    setError('')
    try { await api.post(`/api/inventory/items/${item.id}/restore`, {}); load() } catch (err) { setError(err.message) }
  }
  const removeItem = async (item) => {
    if (!window.confirm(`Remove "${item.name}" from the inventory? Its maintenance history is kept.`)) return
    setError('')
    try { await api.delete(`/api/inventory/items/${item.id}`); load() } catch (err) { setError(err.message) }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Assets"
        title="Inventory"
        description="Furniture, equipment, and supplies."
        action={hasPermission('inventory.manage') && <button onClick={() => setCreateOpen(true)} className="btn-primary text-xs"><PlusCircle size={14} /> Add item</button>}
      />

      {error && <p className="text-sm text-red-400 mb-3">{error}</p>}
      <Table
        emptyLabel="No inventory items yet"
        columns={[
          { key: 'name', header: 'Item', render: (r) => <span className="font-medium">{r.name}</span> },
          { key: 'category', header: 'Category', render: (r) => r.category || 'N/A' },
          { key: 'quantity', header: 'Qty', render: (r) => <span className="font-mono text-xs">{r.quantity}</span> },
          { key: 'location', header: 'Location', render: (r) => r.location || 'N/A' },
          { key: 'status', header: 'Status', render: (r) => <Badge tone={STATUS_TONE[r.status]}>{(r.status || 'unknown').replace('_', ' ')}</Badge> },
          ...(hasPermission('inventory.manage') ? [{
            key: 'actions', header: '', render: (r) => (
              <div className="flex items-center gap-1.5 justify-end">
                {r.status === 'under_maintenance' ? (
                  <button onClick={(e) => { e.stopPropagation(); backInUse(r) }} className="btn-primary !py-1 text-xs">
                    <CheckCircle2 size={12} /> Repaired, back in use
                  </button>
                ) : (
                  <button onClick={(e) => { e.stopPropagation(); setMaintainFor(r) }} className="btn-secondary !py-1 text-xs">
                    <Wrench size={12} /> Log maintenance
                  </button>
                )}
                <button onClick={(e) => { e.stopPropagation(); setHistoryFor(r) }} className="btn-secondary !py-1 !px-2 text-xs" title="Maintenance history"><History size={13} /></button>
                <button onClick={(e) => { e.stopPropagation(); removeItem(r) }} className="text-slate hover:text-red-400 p-1" title="Remove item"><Trash2 size={14} /></button>
              </div>
            ),
          }] : []),
        ]}
        rows={data.items}
      />

      <Pagination page={data.page} pages={data.pages} onChange={setPage} />

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Add inventory item">
        <CreateForm onCreated={() => { setCreateOpen(false); load() }} />
      </Modal>

      <Modal open={!!historyFor} onClose={() => setHistoryFor(null)} title={`Maintenance history: ${historyFor?.name || ''}`}>
        {historyFor && <MaintenanceHistory item={historyFor} />}
      </Modal>

      <Modal open={!!maintainFor} onClose={() => setMaintainFor(null)} title={`Log maintenance: ${maintainFor?.name || ''}`}>
        {maintainFor && <MaintenanceForm item={maintainFor} onDone={() => { setMaintainFor(null); load() }} />}
      </Modal>
    </div>
  )
}

function CreateForm({ onCreated }) {
  const [form, setForm] = useState({ name: '', category: '', quantity: 1, location: '' })
  const [submitting, setSubmitting] = useState(false)
  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    await api.post('/api/inventory/items', { ...form, quantity: Number(form.quantity) })
    setSubmitting(false)
    onCreated()
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div><label className="label">Item name</label><input required className="input" value={form.name} onChange={set('name')} /></div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="label">Category</label><input className="input" value={form.category} onChange={set('category')} /></div>
        <div><label className="label">Quantity</label><input type="number" min={1} className="input" value={form.quantity} onChange={set('quantity')} /></div>
      </div>
      <div><label className="label">Location</label><input className="input" value={form.location} onChange={set('location')} /></div>
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Adding...' : 'Add item'}</button>
    </form>
  )
}

function MaintenanceForm({ item, onDone }) {
  const [description, setDescription] = useState('')
  const [cost, setCost] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    await api.post(`/api/inventory/items/${item.id}/maintenance`, { description, cost: cost ? Number(cost) : undefined })
    setSubmitting(false)
    onDone()
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div><label className="label">Description</label><textarea required rows={3} className="input" value={description} onChange={(e) => setDescription(e.target.value)} /></div>
      <div><label className="label">Cost (optional)</label><input type="number" className="input" value={cost} onChange={(e) => setCost(e.target.value)} /></div>
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Saving...' : 'Log maintenance'}</button>
    </form>
  )
}

function MaintenanceHistory({ item }) {
  const [rows, setRows] = useState(null)
  useEffect(() => { api.get(`/api/inventory/items/${item.id}/maintenance`).then((d) => setRows(asList(d))).catch(() => setRows([])) }, [item.id])
  if (rows == null) return <p className="text-sm text-slate">Loading...</p>
  if (rows.length === 0) return <p className="text-sm text-slate">No maintenance has been logged for this item.</p>
  return (
    <div className="divide-y divide-rule">
      {rows.map((m) => (
        <div key={m.id} className="py-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">{m.description}</p>
            <Badge tone={m.status === 'completed' ? 'leaf' : 'marigold'}>{m.status === 'completed' ? 'Completed' : 'In progress'}</Badge>
          </div>
          <p className="text-xs text-slate mt-1">
            Sent {m.performed_date}{m.completed_date ? `, back in use ${m.completed_date}` : ''}{m.cost ? ` · Le ${Number(m.cost).toLocaleString()}` : ''}
          </p>
        </div>
      ))}
    </div>
  )
}

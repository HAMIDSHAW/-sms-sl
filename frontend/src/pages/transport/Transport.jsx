import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bus, PlusCircle } from 'lucide-react'
import { PageHeader, Table, Badge, Modal, EmptyState, BlockSkeleton } from '../../components/ui'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const STATUS_TONE = { active: 'leaf', in_maintenance: 'marigold', retired: 'slate' }

export default function Transport() {
  const { hasPermission } = useAuth()
  const navigate = useNavigate()
  const [vehicles, setVehicles] = useState(null)
  const [drivers, setDrivers] = useState(null)
  const [routes, setRoutes] = useState(null)
  const [tab, setTab] = useState('Routes')
  const [createOpen, setCreateOpen] = useState(null)

  const load = () => {
    api.get('/api/transport/vehicles').then((d) => setVehicles(asList(d)))
    api.get('/api/transport/drivers').then((d) => setDrivers(asList(d)))
    api.get('/api/transport/routes').then((d) => setRoutes(asList(d)))
  }
  useEffect(() => { load() }, [])

  const driverName = (id) => (drivers || []).find((d) => d.id === id)?.full_name || 'Unassigned'
  const vehicleNumber = (id) => (vehicles || []).find((v) => v.id === id)?.vehicle_number || 'Unassigned'

  return (
    <div>
      <PageHeader
        eyebrow="Operations"
        title="Transport"
        description="Vehicles, drivers, and pickup routes."
        action={
          hasPermission('transport.manage') && (
            <button onClick={() => setCreateOpen(tab)} className="btn-primary text-xs">
              <PlusCircle size={14} /> Add {tab.toLowerCase().slice(0, -1)}
            </button>
          )
        }
      />

      <div className="flex gap-1 border-b border-rule mb-6">
        {['Routes', 'Vehicles', 'Drivers'].map((t) => (
          <button
            key={t} onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors ${tab === t ? 'text-paper border-b-2 border-leaf' : 'text-slate hover:text-paper'}`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'Routes' && (
        routes == null ? <BlockSkeleton /> : routes.length === 0 ? <EmptyState icon={Bus} title="No routes yet" /> : (
          <div className="space-y-3">
            {routes.map((r) => (
              <div key={r.id} className="card p-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="font-medium text-sm">{r.name}</p>
                  <span className="text-xs text-slate">{vehicleNumber(r.vehicle_id)} · {driverName(r.driver_id)} · {r.departure_time ? `Departs ${r.departure_time}` : 'Departure time not set'}</span>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {r.stops.map((s, i) => (
                    <Badge key={s.id} tone="sky">{i + 1}. {s.name} {s.arrival_time ? `(${s.arrival_time})` : ''}</Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {tab === 'Vehicles' && (
        <Table
          emptyLabel="No vehicles yet"
          columns={[
            { key: 'vehicle_number', header: 'Vehicle', render: (r) => <span className="font-mono text-xs">{r.vehicle_number}</span> },
            { key: 'vehicle_type', header: 'Type', render: (r) => r.vehicle_type || 'N/A' },
            { key: 'capacity', header: 'Capacity', render: (r) => r.capacity || 'N/A' },
            { key: 'driver_id', header: 'Driver', render: (r) => driverName(r.driver_id) },
            { key: 'status', header: 'Status', render: (r) => <Badge tone={STATUS_TONE[r.status]}>{(r.status || 'unknown').replace('_', ' ')}</Badge> },
          ]}
          rows={vehicles}
        />
      )}

      {tab === 'Drivers' && (
        <Table
          emptyLabel="No drivers yet"
          onRowClick={(r) => navigate(`/transport/drivers/${r.id}`)}
          columns={[
            { key: 'full_name', header: 'Name', render: (r) => (
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-full bg-marigold/15 flex items-center justify-center text-[10px] font-display font-semibold text-marigold shrink-0 overflow-hidden">
                  {r.photo_url ? <img src={r.photo_url} alt="" className="w-full h-full object-cover" /> : r.full_name.split(' ').map((n) => n[0]).join('').slice(0, 2)}
                </div>
                <span className="font-medium">{r.full_name}</span>
              </div>
            ) },
            { key: 'phone', header: 'Phone', render: (r) => r.phone || 'N/A' },
            { key: 'license_number', header: 'License', render: (r) => r.license_number || 'N/A' },
          ]}
          rows={drivers}
        />
      )}

      <Modal open={!!createOpen} onClose={() => setCreateOpen(null)} title={`Add ${createOpen?.toLowerCase().slice(0, -1)}`}>
        {createOpen === 'Drivers' && <DriverForm onCreated={() => { setCreateOpen(null); load() }} />}
        {createOpen === 'Vehicles' && <VehicleForm drivers={drivers} onCreated={() => { setCreateOpen(null); load() }} />}
        {createOpen === 'Routes' && <RouteForm vehicles={vehicles} drivers={drivers} onCreated={() => { setCreateOpen(null); load() }} />}
      </Modal>
    </div>
  )
}

function DriverForm({ onCreated }) {
  const [form, setForm] = useState({ full_name: '', phone: '', license_number: '', address: '', photo_url: '' })
  const [submitting, setSubmitting] = useState(false)
  const set = (f) => (e) => setForm((s) => ({ ...s, [f]: e.target.value }))
  const submit = async (e) => { e.preventDefault(); setSubmitting(true); await api.post('/api/transport/drivers', form); setSubmitting(false); onCreated() }
  return (
    <form onSubmit={submit} className="space-y-4">
      <div><label className="label">Full name</label><input required className="input" value={form.full_name} onChange={set('full_name')} /></div>
      <div><label className="label">Phone</label><input className="input" value={form.phone} onChange={set('phone')} /></div>
      <div><label className="label">License number</label><input className="input" value={form.license_number} onChange={set('license_number')} /></div>
      <div><label className="label">Address</label><input className="input" value={form.address} onChange={set('address')} /></div>
      <div><label className="label">Photo URL</label><input className="input" value={form.photo_url} onChange={set('photo_url')} /></div>
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Adding…' : 'Add driver'}</button>
    </form>
  )
}

function VehicleForm({ drivers, onCreated }) {
  const [form, setForm] = useState({ vehicle_number: '', vehicle_type: 'bus', capacity: '', driver_id: '' })
  const [submitting, setSubmitting] = useState(false)
  const set = (f) => (e) => setForm((s) => ({ ...s, [f]: e.target.value }))
  const submit = async (e) => {
    e.preventDefault(); setSubmitting(true)
    await api.post('/api/transport/vehicles', { ...form, capacity: form.capacity ? Number(form.capacity) : undefined })
    setSubmitting(false); onCreated()
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      <div><label className="label">Vehicle number</label><input required className="input" value={form.vehicle_number} onChange={set('vehicle_number')} /></div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="label">Type</label><input className="input" value={form.vehicle_type} onChange={set('vehicle_type')} /></div>
        <div><label className="label">Capacity</label><input type="number" className="input" value={form.capacity} onChange={set('capacity')} /></div>
      </div>
      <div>
        <label className="label">Driver</label>
        <select className="input" value={form.driver_id} onChange={set('driver_id')}>
          <option value="">Unassigned</option>
          {(drivers || []).map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
        </select>
      </div>
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Adding…' : 'Add vehicle'}</button>
    </form>
  )
}

function RouteForm({ vehicles, drivers, onCreated }) {
  const [form, setForm] = useState({ name: '', vehicle_id: '', driver_id: '', departure_time: '' })
  const [submitting, setSubmitting] = useState(false)
  const set = (f) => (e) => setForm((s) => ({ ...s, [f]: e.target.value }))
  const submit = async (e) => { e.preventDefault(); setSubmitting(true); await api.post('/api/transport/routes', form); setSubmitting(false); onCreated() }
  return (
    <form onSubmit={submit} className="space-y-4">
      <div><label className="label">Route name</label><input required className="input" value={form.name} onChange={set('name')} /></div>
      <div>
        <label className="label">Vehicle</label>
        <select className="input" value={form.vehicle_id} onChange={set('vehicle_id')}>
          <option value="">Select…</option>
          {(vehicles || []).map((v) => <option key={v.id} value={v.id}>{v.vehicle_number}</option>)}
        </select>
      </div>
      <div>
        <label className="label">Driver</label>
        <select className="input" value={form.driver_id} onChange={set('driver_id')}>
          <option value="">Select…</option>
          {(drivers || []).map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
        </select>
      </div>
      <div><label className="label">Departure time</label><input type="time" className="input" value={form.departure_time} onChange={set('departure_time')} /></div>
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Creating…' : 'Create route'}</button>
    </form>
  )
}

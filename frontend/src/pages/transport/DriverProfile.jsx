import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Phone, MapPin, IdCard } from 'lucide-react'
import { PageHeader, Badge } from '../../components/ui'
import { api } from '../../lib/api'

export default function DriverProfile() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [driver, setDriver] = useState(null)

  useEffect(() => {
    api.get(`/api/transport/drivers/${id}`).then(setDriver)
  }, [id])

  if (!driver) return null

  return (
    <div>
      <button onClick={() => navigate('/transport')} className="flex items-center gap-1.5 text-sm text-slate hover:text-paper mb-4 transition-colors">
        <ArrowLeft size={14} /> Back to transport
      </button>

      <div className="flex items-center gap-4 mb-6">
        <div className="w-16 h-16 rounded-full bg-marigold/15 flex items-center justify-center text-lg font-display font-semibold text-marigold overflow-hidden shrink-0">
          {driver.photo_url ? <img src={driver.photo_url} alt="" className="w-full h-full object-cover" /> : driver.full_name.split(' ').map((n) => n[0]).join('').slice(0, 2)}
        </div>
        <PageHeader eyebrow="Driver" title={driver.full_name} description="" />
      </div>

      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="card p-4 flex items-center gap-2.5">
          <Phone size={15} className="text-slate shrink-0" />
          <span className="text-sm">{driver.phone || 'N/A'}</span>
        </div>
        <div className="card p-4 flex items-center gap-2.5">
          <IdCard size={15} className="text-slate shrink-0" />
          <span className="text-sm">{driver.license_number || 'N/A'}</span>
        </div>
        <div className="card p-4 flex items-center gap-2.5">
          <MapPin size={15} className="text-slate shrink-0" />
          <span className="text-sm">{driver.address || 'N/A'}</span>
        </div>
      </div>

      <p className="eyebrow mb-3">Assigned routes</p>
      {driver.routes?.length ? (
        <div className="space-y-2">
          {driver.routes.map((r) => (
            <div key={r.id} className="card p-4 flex items-center justify-between">
              <span className="text-sm font-medium">{r.name}</span>
              <Badge tone="sky">{r.departure_time || 'N/A'}</Badge>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-slate">No routes assigned yet.</p>
      )}
    </div>
  )
}

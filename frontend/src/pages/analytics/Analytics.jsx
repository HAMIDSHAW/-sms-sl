import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Users, UserSquare2, CalendarCheck2, DollarSign, TrendingUp } from 'lucide-react'
import { PageHeader, StatCard, EmptyState } from '../../components/ui'
import { api } from '../../lib/api'

export default function Analytics() {
  const [overview, setOverview] = useState(null)
  const [enrollment, setEnrollment] = useState([])
  const [trend, setTrend] = useState([])

  useEffect(() => {
    api.get('/api/analytics/overview').then(setOverview)
    api.get('/api/analytics/enrollment').then(setEnrollment)
    api.get('/api/analytics/attendance-trend?days=14').then(setTrend)
  }, [])

  const maxEnrolled = Math.max(1, ...enrollment.map((e) => e.enrolled_count))

  return (
    <div>
      <PageHeader eyebrow="Insights" title="Analytics" description="School-wide trends across enrollment, attendance, and finance." />

      {overview && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="Total students" value={overview.total_students} icon={Users} accent="leaf" index={0} />
          <StatCard label="Total staff" value={overview.total_staff} icon={UserSquare2} accent="sky" index={1} />
          <StatCard label="Attendance today" value={overview.attendance_today_percentage != null ? `${overview.attendance_today_percentage}%` : 'N/A'} icon={CalendarCheck2} accent="marigold" index={2} />
          <StatCard label="Fee collection rate" value={overview.fee_collection_rate != null ? `${overview.fee_collection_rate}%` : 'N/A'} icon={DollarSign} accent="leaf" index={3} />
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-5">
        <div className="card p-5">
          <p className="eyebrow mb-4">Enrollment by class</p>
          {enrollment.length === 0 ? <EmptyState title="No classes yet" /> : (
            <div className="space-y-3">
              {enrollment.map((e, i) => (
                <motion.div key={e.class_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.03 }}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-medium">{e.class_name}</span>
                    <span className="text-slate font-mono">{e.enrolled_count}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }} animate={{ width: `${(e.enrolled_count / maxEnrolled) * 100}%` }}
                      transition={{ duration: 0.6, delay: i * 0.05 }}
                      className="h-full bg-leaf rounded-full"
                    />
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        <div className="card p-5">
          <p className="eyebrow mb-4 flex items-center gap-1.5"><TrendingUp size={13} /> Attendance trend (14 days)</p>
          {trend.length === 0 ? <EmptyState title="No attendance recorded yet" /> : (
            <div className="flex items-end gap-1.5 h-32">
              {trend.map((t, i) => (
                <motion.div
                  key={t.date}
                  initial={{ height: 0 }} animate={{ height: `${t.percentage || 0}%` }}
                  transition={{ duration: 0.5, delay: i * 0.03 }}
                  className="flex-1 bg-sky/60 rounded-t hover:bg-sky transition-colors relative group"
                  title={`${t.date}: ${t.percentage}%`}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

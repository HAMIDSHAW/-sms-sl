import { useEffect, useMemo, useState } from 'react'
import { PageHeader, Table, Badge, Pagination } from '../../components/ui'
import { api } from '../../lib/api'

const MODULES = [
  ['', 'Everything'], ['auth', 'Sign ins'], ['students', 'Students'], ['staff', 'Staff'], ['attendance', 'Attendance'],
  ['assignments', 'Assignments'], ['materials', 'Materials'], ['exams', 'Exams'], ['results', 'Results'],
  ['finance', 'Finance'], ['invoices', 'Invoices'], ['payments', 'Payments'], ['hr', 'HR and payroll'],
  ['discipline', 'Discipline'], ['library', 'Library'], ['inventory', 'Inventory'], ['transport', 'Transport'],
  ['messages', 'Messages'], ['announcements', 'Announcements'], ['school', 'Settings'],
]
const TONE = { auth: 'slate', finance: 'leaf', invoices: 'leaf', payments: 'leaf', hr: 'sky', discipline: 'red', results: 'marigold', exams: 'marigold' }

export default function ActivityLog() {
  const [data, setData] = useState({ items: null, page: 1, pages: 1, total: 0 })
  const [page, setPage] = useState(1)
  const [module, setModule] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [q, setQ] = useState('')

  useEffect(() => {
    const p = new URLSearchParams({ page, per_page: 50 })
    if (module) p.set('module', module)
    if (from) p.set('date_from', from)
    if (to) p.set('date_to', to)
    api.get(`/api/audit-logs?${p}`).then(setData)
  }, [page, module, from, to])

  // The person/action search works on the page you are looking at.
  const rows = useMemo(() => {
    if (!data.items) return null
    const term = q.trim().toLowerCase()
    if (!term) return data.items
    return data.items.filter((r) => `${r.user_name} ${r.role} ${r.summary}`.toLowerCase().includes(term))
  }, [data.items, q])

  return (
    <div>
      <PageHeader
        eyebrow="Accountability"
        title="Activity log"
        description="Who did what, and when. Every change made in the system is recorded here."
      />
      <div className="flex flex-wrap gap-3 mb-4">
        <input aria-label="Search a person or action" className="input !py-1.5 text-sm w-56" placeholder="Search a person or action" value={q} onChange={(e) => setQ(e.target.value)} />
        <select aria-label="Filter by area" className="input !py-1.5 text-sm w-44" value={module} onChange={(e) => { setModule(e.target.value); setPage(1) }}>
          {MODULES.map(([v, name]) => <option key={v} value={v}>{name}</option>)}
        </select>
        <label className="flex items-center gap-2 text-xs text-slate">From <input type="date" className="input !py-1.5 text-sm" value={from} onChange={(e) => { setFrom(e.target.value); setPage(1) }} /></label>
        <label className="flex items-center gap-2 text-xs text-slate">To <input type="date" className="input !py-1.5 text-sm" value={to} onChange={(e) => { setTo(e.target.value); setPage(1) }} /></label>
        <span className="text-xs text-slate self-center ml-auto">{data.total} entries</span>
      </div>
      <Table
        emptyLabel="No activity recorded for this filter"
        rows={rows}
        columns={[
          { key: 'when', header: 'When', render: (r) => <span className="text-xs text-slate whitespace-nowrap">{new Date(r.created_at).toLocaleString()}</span> },
          { key: 'who', header: 'Who', render: (r) => (
            <div><p className="text-sm font-medium">{r.user_name || 'System'}</p>{r.role && <p className="text-[11px] text-slate capitalize">{r.role}</p>}</div>
          ) },
          { key: 'what', header: 'What they did', render: (r) => <span className="text-sm">{r.summary}</span> },
          { key: 'module', header: 'Area', render: (r) => <Badge tone={TONE[r.module] || 'slate'}>{r.module}</Badge> },
        ]}
      />
      <Pagination page={data.page} pages={data.pages} onChange={setPage} />
    </div>
  )
}

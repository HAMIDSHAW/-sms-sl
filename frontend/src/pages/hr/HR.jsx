import { useEffect, useState } from 'react'
import { PlusCircle, Check, X, Wallet, ListChecks, Calculator, Pencil, UserMinus, UserPlus } from 'lucide-react'
import { PageHeader, Table, Badge, Modal, EmptyState, Avatar } from '../../components/ui'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const LEAVE_STATUS_TONE = { pending: 'marigold', approved: 'leaf', rejected: 'red', cancelled: 'slate' }

export default function HR() {
  const { hasPermission } = useAuth()
  const [tab, setTab] = useState('Leave')
  const [leave, setLeave] = useState(null)
  const [runs, setRuns] = useState(null)
  const [payslips, setPayslips] = useState([])
  const [requestOpen, setRequestOpen] = useState(false)
  const [runOpen, setRunOpen] = useState(false)
  const [leaveFilter, setLeaveFilter] = useState('pending')
  const [viewRunId, setViewRunId] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const canApproveLeave = hasPermission('hr.leave.approve')
  const canManagePayroll = hasPermission('hr.payroll.manage')
  // Every staff role can reach this page to request their own leave, but
  // payroll is staff/admin-only, fetching it unconditionally meant every
  // teacher/librarian/etc. visiting this page silently 403'd on two
  // requests they were never going to be allowed to see the result of.
  const canViewPayroll = hasPermission('hr.payroll.view') || canManagePayroll

  const load = () => {
    api.get('/api/hr/leave').then((d) => setLeave(asList(d))).catch(() => setLeave([]))
    if (canViewPayroll) {
      api.get('/api/hr/payroll/runs').then((d) => setRuns(asList(d))).catch(() => {})
      api.get('/api/hr/payroll/payslips').then((d) => setPayslips(asList(d))).catch(() => {})
    } else {
      setRuns([])
      setPayslips([])
    }
  }
  useEffect(() => { load() }, [])

  const respond = async (id, action) => {
    setError('')
    try {
      await api.post(`/api/hr/leave/${id}/${action}`)
      load()
    } catch (err) { setError(err.message) }
  }

  const generate = async (run) => {
    setError('')
    try {
      const res = await api.post(`/api/hr/payroll/runs/${run.id}/generate`, {})
      setNotice(res.created ? `Added ${res.created} payslip${res.created === 1 ? '' : 's'}.${res.missing_salary?.length ? ` No salary on record for: ${res.missing_salary.join(', ')}.` : ''}` : 'Everyone is already on this run.')
      load()
    } catch (err) { setError(err.message) }
  }

  const markPaid = async (run) => {
    if (!window.confirm(`Mark ${run.period_label} as paid for ${run.payslip_count} staff (Le ${Math.round(run.total_net || 0).toLocaleString()} in total)? Every one of them will be told their salary has been paid, and it can no longer be changed.`)) return
    setError('')
    try {
      const res = await api.post(`/api/hr/payroll/runs/${run.id}/mark-paid`, {})
      setNotice(res.removed_former_staff?.length ? `Paid. Not paid because they are no longer employees: ${res.removed_former_staff.join(', ')}.` : `${run.period_label} marked as paid.`)
      load()
    } catch (err) { setError(err.message) }
  }

  const viewRun = (runs || []).find((r) => r.id === viewRunId) || null
  const pendingCount = (leave || []).filter((l) => l.status === 'pending').length
  const leaveRows = leave && canApproveLeave && leaveFilter !== 'all' ? leave.filter((l) => l.status === leaveFilter) : leave

  return (
    <div>
      <PageHeader eyebrow="Human resources" title="HR" description="Leave requests and payroll." />

      <div className="flex gap-1 border-b border-rule mb-6">
        {(canViewPayroll ? ['Leave', 'Payroll'] : ['Leave']).map((t) => (
          <button
            key={t} onClick={() => setTab(t)}
            className={`relative px-4 py-2.5 text-sm font-medium transition-colors ${tab === t ? 'text-paper' : 'text-slate hover:text-paper'}`}
          >
            {t}
            {tab === t && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-leaf" />}
          </button>
        ))}
      </div>

      {error && <p className="text-sm text-red-400 mb-4">{error}</p>}
      {notice && <p className="text-sm text-leaf mb-4 card px-4 py-2.5 flex items-start justify-between gap-3" role="status"><span>{notice}</span><button className="text-slate hover:text-paper" aria-label="Dismiss" onClick={() => setNotice('')}><X size={14} /></button></p>}

      {tab === 'Leave' && (
        <div>
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            {canApproveLeave ? (
              <div className="flex flex-wrap gap-1.5">
                {[['pending', `Waiting for a decision (${pendingCount})`], ['approved', 'Approved'], ['rejected', 'Rejected'], ['all', 'All']].map(([key, name]) => (
                  <button
                    key={key} onClick={() => setLeaveFilter(key)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${leaveFilter === key ? 'bg-leaf/15 border-leaf/40 text-leaf' : 'border-rule text-slate hover:text-paper'}`}
                  >
                    {name}
                  </button>
                ))}
              </div>
            ) : <span />}
            <button onClick={() => setRequestOpen(true)} className="btn-secondary text-xs"><PlusCircle size={14} /> Request leave</button>
          </div>
          <Table
            emptyLabel="No leave requests"
            columns={[
              { key: 'staff_name', header: 'Requested by', render: (r) => (
                <div className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-full bg-marigold/15 flex items-center justify-center text-[10px] font-display font-semibold text-marigold shrink-0 overflow-hidden">
                    {r.staff_photo_url ? <img src={r.staff_photo_url} alt="" className="w-full h-full object-cover" /> : (r.staff_name || '?').split(' ').map((n) => n[0]).join('').slice(0, 2)}
                  </div>
                  <div>
                    <p className="font-medium leading-tight">{r.staff_name || 'Unknown staff member'}</p>
                    {r.staff_position && <p className="text-[11px] text-slate leading-tight">{r.staff_position}</p>}
                  </div>
                </div>
              ) },
              { key: 'leave_type', header: 'Type', render: (r) => <span className="capitalize">{r.leave_type}</span> },
              { key: 'dates', header: 'Dates', render: (r) => <span className="text-xs">{r.start_date} to {r.end_date}</span> },
              { key: 'reason', header: 'Reason', render: (r) => r.reason || 'N/A' },
              { key: 'status', header: 'Status', render: (r) => <Badge tone={LEAVE_STATUS_TONE[r.status]}>{r.status}</Badge> },
              ...(canApproveLeave ? [{
                key: 'actions', header: '', render: (r) => r.status === 'pending' && (
                  <div className="flex gap-1.5 justify-end">
                    <button onClick={() => respond(r.id, 'approve')} className="btn-secondary !py-1 text-xs !text-leaf"><Check size={13} /> Approve</button>
                    <button onClick={() => respond(r.id, 'reject')} className="btn-secondary !py-1 text-xs !text-red-400"><X size={13} /> Reject</button>
                  </div>
                ),
              }] : []),
            ]}
            rows={leaveRows}
          />
        </div>
      )}

      {tab === 'Payroll' && (
        <div>
          {canManagePayroll && (
            <div className="flex justify-end mb-4">
              <button onClick={() => setRunOpen(true)} className="btn-secondary text-xs"><PlusCircle size={14} /> New payroll run</button>
            </div>
          )}

          {canManagePayroll ? (
            <Table
              emptyLabel="No payroll runs yet"
              columns={[
                { key: 'period_label', header: 'Period', render: (r) => <span className="font-medium">{r.period_label}</span> },
                { key: 'period_start', header: 'Dates', render: (r) => <span className="text-xs text-slate">{r.period_start} to {r.period_end}</span> },
                { key: 'staff', header: 'Staff', render: (r) => <span className="text-xs">{r.payslip_count || 0}</span> },
                { key: 'net', header: 'Total net pay', render: (r) => <span className="font-mono text-xs">{r.payslip_count ? `Le ${Math.round(r.total_net).toLocaleString()}` : 'N/A'}</span> },
                { key: 'status', header: 'Status', render: (r) => <Badge tone={r.status === 'paid' ? 'leaf' : r.status === 'processed' ? 'sky' : 'slate'}>{r.status === 'processed' ? 'ready to pay' : r.status}</Badge> },
                { key: 'actions', header: '', render: (r) => (
                  <div className="flex gap-1.5 justify-end">
                    {(r.payslip_count > 0 || r.status !== 'draft') && (
                      <button onClick={() => setViewRunId(r.id)} className="btn-secondary !py-1 text-xs">
                        {r.status === 'paid' ? <ListChecks size={13} /> : <Pencil size={13} />} {r.status === 'paid' ? 'Payslips' : 'Review / edit'}
                      </button>
                    )}
                    {r.status === 'draft' && (
                      <button onClick={() => generate(r)} className="btn-secondary !py-1 text-xs"><Calculator size={13} /> Fill from staff list</button>
                    )}
                    {r.status === 'processed' && r.payslip_count > 0 && (
                      <button onClick={() => markPaid(r)} className="btn-primary !py-1 text-xs"><Wallet size={13} /> Mark as paid</button>
                    )}
                  </div>
                ) },
              ]}
              rows={runs}
            />
          ) : (
            <>
              <p className="eyebrow mb-3">My payslips</p>
              {payslips.length === 0 ? <EmptyState title="No payslips yet" /> : (
                <div className="card divide-y divide-rule">
                  {payslips.map((p) => (
                    <div key={p.id} className="flex items-center justify-between px-4 py-3">
                      <div>
                        <p className="text-sm font-medium">Base: Le {p.base_salary.toLocaleString()}</p>
                        <p className="text-xs text-slate">Allowances Le {p.allowances.toLocaleString()} · Taxes Le {p.taxes.toLocaleString()}</p>
                      </div>
                      <div className="text-right">
                        <p className="font-mono text-sm text-leaf">Le {p.net_salary.toLocaleString()}</p>
                        <Badge tone={p.status === 'paid' ? 'leaf' : 'slate'}>{p.status}</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      <Modal open={requestOpen} onClose={() => setRequestOpen(false)} title="Request leave">
        <LeaveRequestForm onCreated={() => { setRequestOpen(false); load() }} />
      </Modal>

      <Modal open={!!viewRun} onClose={() => setViewRunId(null)} title={viewRun ? `Payslips: ${viewRun.period_label}` : ''} wide>
        {viewRun && <RunPayslips run={viewRun} canEdit={canManagePayroll && viewRun.status !== 'paid'} onChanged={load} />}
      </Modal>

      <Modal open={runOpen} onClose={() => setRunOpen(false)} title="New payroll run">
        <RunForm onCreated={(res) => {
          setRunOpen(false)
          setNotice(`${res.period_label} created with ${res.created} staff, total net pay Le ${Math.round(res.total_net || 0).toLocaleString()}. Review it, remove or change anyone, then mark it as paid.${res.missing_salary?.length ? ` Left out because no salary is on record: ${res.missing_salary.join(', ')}.` : ''}`)
          load()
        }} />
      </Modal>
    </div>
  )
}

function LeaveRequestForm({ onCreated }) {
  const [form, setForm] = useState({ leave_type: 'annual', start_date: '', end_date: '', reason: '' })
  const [submitting, setSubmitting] = useState(false)
  const set = (f) => (e) => setForm((s) => ({ ...s, [f]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    await api.post('/api/hr/leave', form)
    setSubmitting(false)
    onCreated()
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="label">Leave type</label>
        <select className="input" value={form.leave_type} onChange={set('leave_type')}>
          <option value="annual">Annual</option>
          <option value="sick">Sick</option>
          <option value="maternity">Maternity</option>
          <option value="paternity">Paternity</option>
          <option value="unpaid">Unpaid</option>
        </select>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="label">Start date</label><input required type="date" className="input" value={form.start_date} onChange={set('start_date')} /></div>
        <div><label className="label">End date</label><input required type="date" className="input" value={form.end_date} onChange={set('end_date')} /></div>
      </div>
      <div><label className="label">Reason</label><textarea rows={2} className="input" value={form.reason} onChange={set('reason')} /></div>
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Submitting...' : 'Submit request'}</button>
    </form>
  )
}

function RunForm({ onCreated }) {
  const [form, setForm] = useState({ period_label: '', period_start: '', period_end: '' })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const set = (f) => (e) => setForm((s) => ({ ...s, [f]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      onCreated(await api.post('/api/hr/payroll/runs', form))
    } catch (err) { setError(err.message) }
    setSubmitting(false)
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-xs text-slate">Everyone currently employed is added automatically, using their standing salary. You can change anyone's figures or remove them before paying.</p>
      <div><label className="label">Period label</label><input required className="input" placeholder="January 2027" value={form.period_label} onChange={set('period_label')} /></div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="label">Start date</label><input required type="date" className="input" value={form.period_start} onChange={set('period_start')} /></div>
        <div><label className="label">End date</label><input required type="date" className="input" min={form.period_start || undefined} value={form.period_end} onChange={set('period_end')} /></div>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Creating...' : 'Create run'}</button>
    </form>
  )
}

const PAY_FIELDS = [
  ['base_salary', 'Base salary'], ['allowances', 'Allowances'], ['bonuses', 'Bonus'],
  ['deductions', 'Deductions'], ['taxes', 'Taxes'], ['other_deductions', 'Other deductions'],
]
const money = (n) => `Le ${Math.round(n || 0).toLocaleString()}`

function RunPayslips({ run, canEdit, onChanged }) {
  const [slips, setSlips] = useState(null)
  const [editing, setEditing] = useState(null)
  const [error, setError] = useState('')
  const [addable, setAddable] = useState([])
  const [addId, setAddId] = useState('')

  const reload = () => api.get(`/api/hr/payroll/payslips?payroll_run_id=${run.id}`).then((d) => setSlips(asList(d)))
  useEffect(() => { reload() }, [run.id])

  // Current employees who are not on this run (removed earlier, or newly hired), so they can be added back.
  useEffect(() => {
    if (!canEdit || !slips) return
    api.get('/api/staff?per_page=200').then((d) => {
      const on = new Set(slips.map((p) => p.staff_id))
      setAddable(asList(d).filter((m) => m.status !== 'terminated' && !on.has(m.id)))
    }).catch(() => {})
  }, [canEdit, slips])

  const changed = () => { reload(); onChanged() }

  const remove = async (p) => {
    if (!window.confirm(`Take ${p.staff_name} off ${run.period_label}? They will not be paid in this run. Their standing salary and other months are not affected.`)) return
    setError('')
    try { await api.delete(`/api/hr/payroll/payslips/${p.id}`); changed() } catch (err) { setError(err.message) }
  }

  const add = async () => {
    setError('')
    try { await api.post(`/api/hr/payroll/runs/${run.id}/payslips`, { staff_id: addId }); setAddId(''); changed() } catch (err) { setError(err.message) }
  }

  if (editing) {
    return <PayslipEditor slip={editing} onCancel={() => setEditing(null)} onSaved={() => { setEditing(null); changed() }} />
  }

  return (
    <div>
      <p className="text-sm text-slate mb-3">
        {run.payslip_count} staff · total net pay <span className="text-paper font-mono">{money(run.total_net)}</span> · <Badge tone={run.status === 'paid' ? 'leaf' : 'sky'}>{run.status === 'processed' ? 'ready to pay' : run.status}</Badge>
      </p>
      {canEdit && <p className="text-xs text-slate mb-3">Nothing is paid until you press Mark as paid. Edit a figure, or remove someone who should not be paid this month.</p>}
      {error && <p className="text-sm text-red-400 mb-3">{error}</p>}
      <Table
        rows={slips}
        emptyLabel="No payslips"
        columns={[
          { key: 'staff', header: 'Staff', render: (p) => (
            <span className="flex items-center gap-2"><Avatar src={p.staff_photo_url} name={p.staff_name || ''} size={26} />
              <span><span className="text-sm">{p.staff_name}</span><br /><span className="text-[11px] text-slate">{p.staff_position}</span></span></span>
          ) },
          { key: 'base', header: 'Base', render: (p) => <span className="font-mono text-xs">{money(p.base_salary)}</span> },
          { key: 'allow', header: 'Allowances', render: (p) => <span className="font-mono text-xs">{money(p.allowances)}</span> },
          { key: 'tax', header: 'Taxes', render: (p) => <span className="font-mono text-xs">{money(p.taxes)}</span> },
          { key: 'net', header: 'Net pay', render: (p) => <span className="font-mono text-xs text-leaf">{money(p.net_salary)}</span> },
          ...(canEdit ? [{ key: 'actions', header: '', render: (p) => (
            <div className="flex gap-1.5 justify-end">
              <button onClick={() => setEditing(p)} className="btn-secondary !py-1 text-xs" aria-label={`Edit ${p.staff_name}'s payslip`}><Pencil size={13} /> Edit</button>
              <button onClick={() => remove(p)} className="btn-secondary !py-1 text-xs !text-red-400" aria-label={`Remove ${p.staff_name} from this run`}><UserMinus size={13} /> Remove</button>
            </div>
          ) }] : []),
        ]}
      />
      {canEdit && addable.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mt-4">
          <select className="input !w-auto min-w-[14rem]" value={addId} onChange={(e) => setAddId(e.target.value)} aria-label="Add a staff member to this run">
            <option value="">Add someone to this run...</option>
            {addable.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
          </select>
          <button className="btn-secondary text-xs" disabled={!addId} onClick={add}><UserPlus size={13} /> Add</button>
        </div>
      )}
    </div>
  )
}

function PayslipEditor({ slip, onCancel, onSaved }) {
  const [form, setForm] = useState(() => Object.fromEntries(PAY_FIELDS.map(([k]) => [k, String(slip[k] ?? 0)])))
  const [standing, setStanding] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const n = (k) => Number(form[k]) || 0
  const net = n('base_salary') + n('allowances') + n('bonuses') - n('deductions') - n('taxes') - n('other_deductions')
  const baseChanged = n('base_salary') !== slip.base_salary

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const body = Object.fromEntries(PAY_FIELDS.map(([k]) => [k, n(k)]))
      if (standing && baseChanged) body.update_standing_salary = true
      await api.patch(`/api/hr/payroll/payslips/${slip.id}`, body)
      onSaved()
    } catch (err) { setError(err.message) }
    setSaving(false)
  }

  return (
    <form onSubmit={save} className="space-y-4">
      <p className="text-sm"><span className="font-medium">{slip.staff_name}</span> <span className="text-slate">· {slip.staff_position}</span></p>
      <div className="grid grid-cols-2 gap-3">
        {PAY_FIELDS.map(([k, label]) => (
          <div key={k}><label className="label">{label} (Le)</label><input type="number" min="0" step="any" required className="input" value={form[k]} onChange={set(k)} /></div>
        ))}
      </div>
      <p className="text-sm">Net pay: <span className={`font-mono ${net < 0 ? 'text-red-400' : 'text-leaf'}`}>{money(net)}</span></p>
      {baseChanged && (
        <label className="flex items-start gap-2 text-sm card p-3">
          <input type="checkbox" className="mt-0.5" checked={standing} onChange={(e) => setStanding(e.target.checked)} />
          <span>Make {money(n('base_salary'))} their salary from now on ({n('base_salary') > slip.base_salary ? 'a raise' : 'a cut'}), not only this month. Future payroll runs will start from it.</span>
        </label>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className="flex gap-2">
        <button type="button" onClick={onCancel} className="btn-secondary flex-1">Back</button>
        <button type="submit" disabled={saving || net < 0} className="btn-primary flex-1">{saving ? 'Saving...' : 'Save changes'}</button>
      </div>
    </form>
  )
}

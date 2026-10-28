import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DollarSign, TrendingDown, AlertTriangle, PiggyBank, PlusCircle, XCircle, Layers, Search } from 'lucide-react'
import { PageHeader, StatCard, Table, Badge, Modal, EmptyState, Pagination } from '../../components/ui'
import StudentPicker from '../../components/StudentPicker'
import PaymentForm from '../../components/PaymentForm'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

function money(n) {
  if (n == null) return 'N/A'
  return `Le ${Number(n).toLocaleString()}`
}

const STATUS_TONE = { unpaid: 'red', partially_paid: 'marigold', paid: 'leaf', cancelled: 'slate' }

export default function FinanceOverview() {
  const [summary, setSummary] = useState(null)
  const [invoices, setInvoices] = useState(null)
  const [payments, setPayments] = useState(null)
  const [tab, setTab] = useState('invoices')
  const [createOpen, setCreateOpen] = useState(false)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [payFor, setPayFor] = useState(null)
  const [structures, setStructures] = useState([])
  const [classes, setClasses] = useState([])
  const [classId, setClassId] = useState('')
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [paymentPage, setPaymentPage] = useState(1)
  const { hasPermission } = useAuth()
  const navigate = useNavigate()
  const canManage = hasPermission('finance.manage')
  const canPay = hasPermission('finance.payment.create')
  const staffView = canManage || canPay

  const loadInvoices = () => {
    const p = new URLSearchParams({ per_page: 25, page })
    if (classId) p.set('class_id', classId)
    if (status) p.set('status', status)
    if (search.trim()) p.set('q', search.trim())
    return api.get(`/api/invoices?${p}`).then(setInvoices)
  }
  const loadPayments = () => {
    const p = new URLSearchParams({ per_page: 25, page: paymentPage })
    if (search.trim()) p.set('q', search.trim())
    return api.get(`/api/payments?${p}`).then(setPayments)
  }
  const reload = () => { api.get('/api/finance/summary').then(setSummary).catch(() => {}); loadInvoices(); if (tab === 'payments') loadPayments() }

  useEffect(() => {
    api.get('/api/finance/summary').then(setSummary).catch(() => {})
    if (canManage) api.get('/api/finance/structures').then((d) => setStructures(asList(d))).catch(() => {})
    if (staffView) api.get('/api/academics/classes').then((d) => setClasses(asList(d))).catch(() => {})
  }, [])
  useEffect(() => { const t = setTimeout(loadInvoices, 250); return () => clearTimeout(t) }, [classId, status, search, page])
  useEffect(() => { if (tab === 'payments') { const t = setTimeout(loadPayments, 250); return () => clearTimeout(t) } }, [tab, search, paymentPage])

  const cancelInvoice = async (inv) => {
    if (!window.confirm(`Cancel invoice ${inv.invoice_number}? This can't be undone.`)) return
    await api.patch(`/api/invoices/${inv.id}/cancel`)
    reload()
  }

  const invoiceRows = invoices?.items ?? null
  const paymentRows = payments?.items ?? null

  return (
    <div>
      <PageHeader
        eyebrow="Finance"
        title="Overview"
        description="Fee collection and billing at a glance."
        action={canManage && (
          <div className="flex gap-2">
            <button onClick={() => setBulkOpen(true)} className="btn-secondary text-xs"><Layers size={14} /> Bill a class</button>
            <button onClick={() => setCreateOpen(true)} className="btn-primary text-xs"><PlusCircle size={14} /> New invoice</button>
          </div>
        )}
      />

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard label="Total billed" value={money(summary.total_billed)} icon={DollarSign} accent="sky" index={0} />
          <StatCard label="Collected" value={money(summary.total_collected)} icon={PiggyBank} accent="leaf" index={1} />
          <StatCard label="Outstanding" value={money(summary.outstanding)} icon={AlertTriangle} accent="marigold" index={2} />
          <StatCard label="Overdue" value={money(summary.overdue)} icon={TrendingDown} accent="marigold" index={3} />
        </div>
      )}

      {summary && (
        <div className="card p-5 mb-8">
          <p className="eyebrow mb-2">Collection rate</p>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 rounded-full bg-white/5 overflow-hidden">
              <div className="h-full bg-leaf rounded-full transition-all" style={{ width: `${summary.collection_rate || 0}%` }} />
            </div>
            <span className="font-mono text-sm">{summary.collection_rate ?? 0}%</span>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex gap-1">
          {[['invoices', 'Invoices'], ...(staffView ? [['payments', 'Payments']] : [])].map(([key, name]) => (
            <button
              key={key} onClick={() => setTab(key)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${tab === key ? 'bg-leaf/15 border-leaf/40 text-leaf' : 'border-rule text-slate hover:text-paper'}`}
            >
              {name}
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[220px] max-w-xs ml-auto">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate" />
          <input
            aria-label="Search"
            className="input !pl-8 !py-1.5 text-sm"
            placeholder={tab === 'invoices' ? 'Student, invoice # or description' : 'Student, payer or receipt #'}
            value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); setPaymentPage(1) }}
          />
        </div>
        {tab === 'invoices' && staffView && (
          <>
            <select aria-label="Filter by class" className="input !py-1.5 text-sm w-36" value={classId} onChange={(e) => { setClassId(e.target.value); setPage(1) }}>
              <option value="">All classes</option>
              {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <select aria-label="Filter by status" className="input !py-1.5 text-sm w-36" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
              <option value="">Any status</option>
              <option value="unpaid">Unpaid</option>
              <option value="partially_paid">Part paid</option>
              <option value="paid">Paid</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </>
        )}
      </div>

      {tab === 'invoices' ? (
        <>
          <Table
            emptyLabel="No invoices match"
            rows={invoiceRows}
            onRowClick={(r) => navigate(`/finance/ledger/${r.student_id}`)}
            columns={[
              ...(staffView ? [{ key: 'student', header: 'Student', render: (r) => (
                <div><p className="text-sm">{r.student_name}</p><p className="text-[11px] text-slate">{r.student_number}{r.class_name ? ` · ${r.class_name}` : ''}</p></div>
              ) }] : []),
              { key: 'description', header: 'For', render: (r) => (
                <div><p className="text-sm">{r.description}</p><p className="text-[11px] text-slate font-mono">{r.invoice_number}{r.due_date ? ` · due ${r.due_date}` : ''}</p></div>
              ) },
              { key: 'amount', header: 'Amount', render: (r) => <span className="font-mono text-xs">{money(r.amount)}</span> },
              { key: 'balance', header: 'Balance', render: (r) => <span className={`font-mono text-xs ${r.balance > 0 ? 'text-marigold' : 'text-leaf'}`}>{money(r.balance)}</span> },
              { key: 'status', header: 'Status', render: (r) => <Badge tone={STATUS_TONE[r.status]}>{(r.status || 'unknown').replace('_', ' ')}</Badge> },
              {
                key: 'actions', header: '', render: (r) => (r.status !== 'cancelled' && r.status !== 'paid') && (
                  <div className="flex items-center gap-3 justify-end">
                    {canPay && (
                      <button onClick={(e) => { e.stopPropagation(); setPayFor(r) }} className="btn-secondary !py-1 text-xs">Record payment</button>
                    )}
                    {canManage && (
                      <button onClick={(e) => { e.stopPropagation(); cancelInvoice(r) }} className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1">
                        <XCircle size={13} /> Cancel
                      </button>
                    )}
                  </div>
                ),
              },
            ]}
          />
          <Pagination page={invoices?.page || 1} pages={invoices?.pages || 1} onChange={setPage} />
        </>
      ) : (
        <>
          <Table
            emptyLabel="No payments match"
            rows={paymentRows}
            onRowClick={(r) => navigate(`/finance/ledger/${r.student_id}`)}
            columns={[
              { key: 'receipt', header: 'Receipt', render: (r) => <span className="font-mono text-xs">{r.receipt_number}</span> },
              { key: 'date', header: 'Date', render: (r) => <span className="text-xs text-slate">{new Date(r.paid_at).toLocaleDateString()}</span> },
              { key: 'student', header: 'Student', render: (r) => (
                <div><p className="text-sm">{r.student_name}</p><p className="text-[11px] text-slate">{r.student_number}</p></div>
              ) },
              { key: 'for', header: 'Paid for', render: (r) => r.paid_for || 'N/A' },
              { key: 'amount', header: 'Amount', render: (r) => <span className="font-mono text-xs text-leaf">{money(r.amount)}</span> },
              { key: 'by', header: 'Paid by', render: (r) => (
                r.payer_name ? (
                  <div><p className="text-sm">{r.payer_name}</p><p className="text-[11px] text-slate">{[r.payer_relationship, r.payer_phone].filter(Boolean).join(' · ')}</p></div>
                ) : <span className="text-slate text-xs">Not recorded</span>
              ) },
              { key: 'method', header: 'Method', render: (r) => <span className="text-xs capitalize">{(r.payment_method || '').replace('_', ' ')}</span> },
              { key: 'recv', header: 'Received by', render: (r) => <span className="text-xs">{r.received_by_name || 'N/A'}</span> },
            ]}
          />
          <Pagination page={payments?.page || 1} pages={payments?.pages || 1} onChange={setPaymentPage} />
        </>
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="New invoice">
        <CreateInvoiceForm onCreated={() => { setCreateOpen(false); reload() }} />
      </Modal>

      <Modal open={bulkOpen} onClose={() => setBulkOpen(false)} title="Bill a class">
        <BulkBillForm structures={structures} classes={classes} onCreated={() => { setBulkOpen(false); reload() }} />
      </Modal>

      <Modal open={!!payFor} onClose={() => setPayFor(null)} title="Record payment">
        {payFor && <PaymentForm invoice={payFor} onSaved={() => { setPayFor(null); reload() }} />}
      </Modal>
    </div>
  )
}

function CreateInvoiceForm({ onCreated }) {
  const [studentId, setStudentId] = useState('')
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!studentId) { setError('Pick a student'); return }
    setSubmitting(true)
    setError(null)
    try {
      await api.post('/api/invoices', { student_id: studentId, description, amount: Number(amount), due_date: dueDate || undefined })
      onCreated()
    } catch (err) {
      setError(err.data?.error || 'Could not create invoice')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <StudentPicker value={studentId} onChange={setStudentId} />
      <div>
        <label className="label">Description</label>
        <input required className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="e.g. Term 1 Tuition" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Amount (Le)</label>
          <input required type="number" min="1" className="input" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </div>
        <div>
          <label className="label">Due date (optional)</label>
          <input type="date" className="input" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </div>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Creating...' : 'Create invoice'}</button>
    </form>
  )
}

function BulkBillForm({ structures, classes, onCreated }) {
  const [classId, setClassId] = useState('')
  const [description, setDescription] = useState('')
  const [amount, setAmount] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState(null)

  const classStructures = structures.filter((s) => !s.class_id || s.class_id === classId)
  const useStructure = (id) => {
    const st = structures.find((s) => s.id === id)
    if (st) { setDescription(st.name); setAmount(String(st.amount)); if (st.due_date) setDueDate(st.due_date) }
  }

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      setResult(await api.post('/api/invoices/bill-class', { class_id: classId, description, amount: Number(amount), due_date: dueDate || undefined }))
    } catch (err) {
      setError(err.data?.error || 'Could not bill the class')
    } finally {
      setSubmitting(false)
    }
  }

  if (result) {
    return (
      <div className="text-center py-4">
        <p className="font-display font-semibold mb-1">{result.created} invoice{result.created === 1 ? '' : 's'} created for {result.class_name}</p>
        <p className="text-sm text-slate mb-4">{result.skipped ? `${result.skipped} student${result.skipped === 1 ? ' was' : 's were'} already billed for this and skipped.` : 'Every student in the class was billed.'}</p>
        <button className="btn-primary" onClick={onCreated}>Done</button>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="label">Class</label>
        <select required className="input" value={classId} onChange={(e) => setClassId(e.target.value)}>
          <option value="">Choose a class</option>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      {classId && classStructures.length > 0 && (
        <div>
          <label className="label">Start from a saved fee structure (optional)</label>
          <select className="input" defaultValue="" onChange={(e) => useStructure(e.target.value)}>
            <option value="">Type the details myself</option>
            {classStructures.map((s) => <option key={s.id} value={s.id}>{s.name}, Le {Number(s.amount).toLocaleString()}</option>)}
          </select>
        </div>
      )}
      <div>
        <label className="label">Description</label>
        <input required className="input" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="e.g. Term 1 Tuition" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="label">Amount per student (Le)</label><input required type="number" min="1" className="input" value={amount} onChange={(e) => setAmount(e.target.value)} /></div>
        <div><label className="label">Due date</label><input type="date" className="input" value={dueDate} onChange={(e) => setDueDate(e.target.value)} /></div>
      </div>
      <p className="text-xs text-slate">One invoice is created for every student currently enrolled in the class. Anyone already billed for the same description is skipped, so it is safe to press twice.</p>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting || !classId} className="btn-primary w-full">{submitting ? 'Billing...' : 'Bill the class'}</button>
    </form>
  )
}

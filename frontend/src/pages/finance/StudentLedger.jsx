import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { PageHeader, Badge, Modal, EmptyState, Table } from '../../components/ui'
import PaymentForm, { money } from '../../components/PaymentForm'
import { api } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const STATUS_TONE = { unpaid: 'red', partially_paid: 'marigold', paid: 'leaf', cancelled: 'slate' }
const label = (s) => (s || 'unknown').replace(/_/g, ' ')

export default function StudentLedger() {
  const { studentId } = useParams()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const [ledger, setLedger] = useState(null)
  const [payOpen, setPayOpen] = useState(null)

  const load = () => api.get(`/api/finance/ledger/${studentId}`).then(setLedger)
  useEffect(() => { load() }, [studentId])

  if (!ledger) return <div className="text-slate text-sm">Loading...</div>
  const invoiceById = Object.fromEntries(ledger.invoices.map((i) => [i.id, i]))

  return (
    <div>
      <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-slate hover:text-paper transition-colors mb-5">
        <ArrowLeft size={15} /> Back
      </button>
      <PageHeader
        eyebrow="Student account"
        title={ledger.student_name ? `${ledger.student_name}: fee ledger` : 'Fee ledger'}
        description={[ledger.student_number, ledger.class_name].filter(Boolean).join(' · ')}
      />

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="card p-4"><p className="text-xs text-slate mb-1">Total billed</p><p className="font-display text-xl font-semibold">{money(ledger.total_billed)}</p></div>
        <div className="card p-4"><p className="text-xs text-slate mb-1">Total paid</p><p className="font-display text-xl font-semibold text-leaf">{money(ledger.total_paid)}</p></div>
        <div className="card p-4"><p className="text-xs text-slate mb-1">Balance</p><p className={`font-display text-xl font-semibold ${ledger.balance > 0 ? 'text-marigold' : 'text-leaf'}`}>{money(ledger.balance)}</p></div>
      </div>

      <p className="eyebrow mb-3">Invoices</p>
      {ledger.invoices.length === 0 ? <EmptyState title="No invoices yet" /> : (
        <div className="card divide-y divide-rule mb-8">
          {ledger.invoices.map((inv) => (
            <div key={inv.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div>
                <p className="text-sm font-medium">{inv.description}</p>
                <p className="text-xs text-slate font-mono">{inv.invoice_number}{inv.due_date ? ` · due ${inv.due_date}` : ''}</p>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right">
                  <p className="font-mono text-sm">{money(inv.amount)}</p>
                  {inv.paid_amount > 0 && <p className="text-[11px] text-slate">paid {money(inv.paid_amount)}, owes {money(inv.balance)}</p>}
                </div>
                <Badge tone={STATUS_TONE[inv.status]}>{label(inv.status)}</Badge>
                {hasPermission('finance.payment.create') && inv.status !== 'paid' && inv.status !== 'cancelled' && (
                  <button onClick={() => setPayOpen(inv)} className="btn-secondary !py-1.5 text-xs">Record payment</button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="eyebrow mb-3">Payment history</p>
      <Table
        emptyLabel="No payments recorded yet"
        rows={ledger.payments}
        columns={[
          { key: 'receipt', header: 'Receipt', render: (p) => <span className="font-mono text-xs">{p.receipt_number}</span> },
          { key: 'date', header: 'Date', render: (p) => <span className="text-xs text-slate">{new Date(p.paid_at).toLocaleDateString()}</span> },
          { key: 'for', header: 'Paid for', render: (p) => p.paid_for || invoiceById[p.invoice_id]?.description || 'N/A' },
          { key: 'amount', header: 'Amount', render: (p) => <span className="font-mono text-xs text-leaf">{money(p.amount)}</span> },
          { key: 'by', header: 'Paid by', render: (p) => (
            p.payer_name ? (
              <div>
                <p className="text-sm">{p.payer_name}</p>
                <p className="text-[11px] text-slate">{[p.payer_relationship, p.payer_phone].filter(Boolean).join(' · ')}</p>
              </div>
            ) : <span className="text-slate text-xs">Not recorded</span>
          ) },
          { key: 'method', header: 'Method', render: (p) => <span className="text-xs capitalize">{label(p.payment_method)}</span> },
          { key: 'recv', header: 'Received by', render: (p) => <span className="text-xs">{p.received_by_name || 'N/A'}</span> },
        ]}
      />

      <Modal open={!!payOpen} onClose={() => setPayOpen(null)} title="Record payment">
        {payOpen && <PaymentForm invoice={{ ...payOpen, student_name: ledger.student_name, class_name: ledger.class_name }} onSaved={() => { setPayOpen(null); load() }} />}
      </Modal>
    </div>
  )
}

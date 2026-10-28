import { useState } from 'react'
import { api } from '../lib/api'

export const money = (n) => (n == null ? 'N/A' : `Le ${Number(n).toLocaleString()}`)

/**
 * Record a payment against an invoice. Captures who actually paid (a parent,
 * a relative, the student), so the ledger can always answer "who paid this
 * and what was it for". The amount starts at the remaining balance.
 */
export default function PaymentForm({ invoice, onSaved }) {
  const balance = invoice.balance ?? invoice.amount
  const [form, setForm] = useState({
    amount: balance, payment_method: 'mobile_money', reference: '',
    payer_name: '', payer_phone: '', payer_relationship: 'parent',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await api.post('/api/payments', { invoice_id: invoice.id, ...form, amount: Number(form.amount) })
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="card p-3 text-sm">
        <p className="font-medium">{invoice.description}</p>
        <p className="text-xs text-slate mt-0.5">
          {invoice.student_name ? `${invoice.student_name}${invoice.class_name ? `, ${invoice.class_name}` : ''} · ` : ''}
          Balance {money(balance)}
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Amount (Le)</label>
          <input type="number" min="1" max={balance} required className="input" value={form.amount} onChange={set('amount')} />
        </div>
        <div>
          <label className="label">Payment method</label>
          <select className="input" value={form.payment_method} onChange={set('payment_method')}>
            <option value="mobile_money">Mobile money</option>
            <option value="cash">Cash</option>
            <option value="bank_transfer">Bank transfer</option>
            <option value="card">Card</option>
            <option value="online_gateway">Online gateway</option>
          </select>
        </div>
      </div>
      <p className="eyebrow">Who is paying</p>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Full name</label>
          <input required className="input" value={form.payer_name} onChange={set('payer_name')} placeholder="e.g. Alhaji Bangura" />
        </div>
        <div>
          <label className="label">Relationship</label>
          <select className="input" value={form.payer_relationship} onChange={set('payer_relationship')}>
            <option value="parent">Parent</option>
            <option value="guardian">Guardian</option>
            <option value="relative">Relative</option>
            <option value="student">The student</option>
            <option value="sponsor">Sponsor</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Phone</label>
          <input className="input" value={form.payer_phone} onChange={set('payer_phone')} placeholder="+232 ..." />
        </div>
        <div>
          <label className="label">Reference (optional)</label>
          <input className="input" value={form.reference} onChange={set('reference')} placeholder="Receipt or mobile money ref" />
        </div>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Recording...' : 'Record payment'}</button>
    </form>
  )
}

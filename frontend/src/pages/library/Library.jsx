import { useEffect, useState } from 'react'
import { PlusCircle, Search, Pencil, Trash2, Undo2 } from 'lucide-react'
import { PageHeader, Table, Badge, Modal, Pagination, Avatar } from '../../components/ui'
import StudentPicker from '../../components/StudentPicker'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const money = (n) => `Le ${Math.round(n || 0).toLocaleString()}`
const localDate = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const inDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return localDate(d) }

/** The school's standard loan period and daily fine, set by the principal. */
function usePolicy() {
  const [policy, setPolicy] = useState({ loan_days: 14, daily_fine: 500 })
  useEffect(() => { api.get('/api/library/policy').then(setPolicy).catch(() => {}) }, [])
  return [policy, setPolicy]
}

export default function Library() {
  const { hasPermission } = useAuth()
  const [tab, setTab] = useState('Catalog')
  const canManage = hasPermission('library.manage')
  const canCirculate = hasPermission('library.circulation')
  const canSetRules = hasPermission('library.policy')
  const tabs = ['Catalog', ...((canManage || canCirculate) ? ['Loans'] : []), ...(canSetRules ? ['Rules'] : [])]

  return (
    <div>
      <PageHeader eyebrow="Resources" title="Library" description="Catalog, borrowing, and returns." />
      {tabs.length > 1 && (
        <div className="flex gap-1 border-b border-rule mb-6">
          {tabs.map((t) => (
            <button
              key={t} onClick={() => setTab(t)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors ${tab === t ? 'text-paper border-b-2 border-leaf' : 'text-slate hover:text-paper'}`}
            >
              {t === 'Rules' ? 'Loan rules and fines' : t}
            </button>
          ))}
        </div>
      )}
      {tab === 'Catalog' && <Catalog />}
      {tab === 'Loans' && <Loans />}
      {tab === 'Rules' && <Rules />}
    </div>
  )
}

/** The principal sets how long books may be kept and what a late day costs. Books can still have their own rule. */
function Rules() {
  const [policy, setPolicy] = usePolicy()
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState({ text: '', bad: false })
  useEffect(() => { setForm({ loan_days: String(policy.loan_days), daily_fine: String(policy.daily_fine) }) }, [policy])
  if (!form) return null

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setMsg({ text: '', bad: false })
    try {
      setPolicy(await api.patch('/api/library/policy', { loan_days: Number(form.loan_days), daily_fine: Number(form.daily_fine) }))
      setMsg({ text: 'Saved. New loans will use these rules.', bad: false })
    } catch (err) { setMsg({ text: err.message, bad: true }) }
    setSaving(false)
  }

  return (
    <form onSubmit={save} className="card p-5 max-w-lg space-y-4">
      <div>
        <p className="font-display font-semibold">School-wide library rules</p>
        <p className="text-xs text-slate mt-1">These apply to every book unless that book was given its own loan period or fine when it was added. Loans already out keep the rules they were lent under. The librarian can still choose a different length when lending, and can reduce or waive a fine when a book comes back (with a reason, which is recorded).</p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="label" htmlFor="rule-days">Standard loan (days)</label><input id="rule-days" type="number" min="1" max="365" required className="input" value={form.loan_days} onChange={(e) => setForm((f) => ({ ...f, loan_days: e.target.value }))} /></div>
        <div><label className="label" htmlFor="rule-fine">Fine per late day (Le)</label><input id="rule-fine" type="number" min="0" step="any" required className="input" value={form.daily_fine} onChange={(e) => setForm((f) => ({ ...f, daily_fine: e.target.value }))} /></div>
      </div>
      <p className="text-xs text-slate">Set the fine to 0 if the school does not charge for late books.</p>
      {msg.text && <p className={`text-sm ${msg.bad ? 'text-red-400' : 'text-leaf'}`}>{msg.text}</p>}
      <button type="submit" disabled={saving} className="btn-primary">{saving ? 'Saving...' : 'Save rules'}</button>
    </form>
  )
}

function Catalog() {
  const { hasPermission } = useAuth()
  const [data, setData] = useState({ items: null, page: 1, pages: 1 })
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState('recent')
  const [createOpen, setCreateOpen] = useState(false)
  const [borrowFor, setBorrowFor] = useState(null)
  const [editing, setEditing] = useState(null)

  const load = () => {
    const params = new URLSearchParams({ page, per_page: 15, sort })
    if (q) params.set('q', q)
    api.get(`/api/library/books?${params}`).then(setData)
  }
  useEffect(() => { load() }, [page, sort])
  useEffect(() => { const t = setTimeout(() => (page === 1 ? load() : setPage(1)), 300); return () => clearTimeout(t) }, [q])

  const remove = async (book) => {
    if (!window.confirm(`Remove "${book.title}" from the catalog?`)) return
    try {
      await api.delete(`/api/library/books/${book.id}`)
      load()
    } catch (err) { window.alert(err.message) }
  }

  const canManage = hasPermission('library.manage')
  const canCirculate = hasPermission('library.circulation')

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div className="relative flex-1 min-w-[220px] max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate" />
          <input className="input pl-9" placeholder="Search title or author" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select aria-label="Sort books" className="input w-44" value={sort} onChange={(e) => { setSort(e.target.value); setPage(1) }}>
          <option value="recent">Recently added</option>
          <option value="title">Title A to Z</option>
        </select>
        {canManage && (
          <button onClick={() => setCreateOpen(true)} className="btn-primary text-xs ml-auto"><PlusCircle size={14} /> Add book</button>
        )}
      </div>

      <Table
        emptyLabel="No books in the catalog yet"
        columns={[
          { key: 'title', header: 'Title', render: (r) => <span className="font-medium">{r.title}</span> },
          { key: 'author', header: 'Author', render: (r) => r.author || 'N/A' },
          { key: 'category', header: 'Category', render: (r) => r.category || 'N/A' },
          {
            key: 'available_copies', header: 'Available', render: (r) => (
              <Badge tone={r.available_copies > 0 ? 'leaf' : 'red'}>{r.available_copies}/{r.total_copies}</Badge>
            ),
          },
          ...((canManage || canCirculate) ? [{
            key: 'actions', header: '', render: (r) => (
              <div className="flex items-center gap-1.5 justify-end">
                {canCirculate && (
                  <button disabled={r.available_copies < 1} onClick={() => setBorrowFor(r)} className="btn-secondary !py-1 text-xs">Lend</button>
                )}
                {canManage && (
                  <>
                    <button onClick={() => setEditing(r)} className="btn-secondary !py-1 !px-2 text-xs" title="Edit book and availability"><Pencil size={13} /></button>
                    <button onClick={() => remove(r)} className="text-slate hover:text-red-400 p-1" title="Remove from catalog"><Trash2 size={14} /></button>
                  </>
                )}
              </div>
            ),
          }] : []),
        ]}
        rows={data.items}
      />

      <Pagination page={data.page} pages={data.pages} onChange={setPage} />

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Add book">
        <BookForm onDone={() => { setCreateOpen(false); setSort('recent'); setPage(1); load() }} />
      </Modal>

      <Modal open={!!editing} onClose={() => setEditing(null)} title="Edit book">
        {editing && <BookForm book={editing} onDone={() => { setEditing(null); load() }} />}
      </Modal>

      <Modal open={!!borrowFor} onClose={() => setBorrowFor(null)} title={`Lend: ${borrowFor?.title || ''}`}>
        {borrowFor && <BorrowForm book={borrowFor} onDone={() => { setBorrowFor(null); load() }} />}
      </Modal>
    </div>
  )
}

function BookForm({ book, onDone }) {
  const editing = !!book
  const [form, setForm] = useState({
    title: book?.title || '', author: book?.author || '', publisher: book?.publisher || '', category: book?.category || '',
    total_copies: book?.total_copies ?? 1, available_copies: book?.available_copies ?? 1,
    loan_days: book?.loan_days ?? '', daily_fine: book?.daily_fine ?? '',
  })
  const [policy] = usePolicy()
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      if (editing) {
        await api.patch(`/api/library/books/${book.id}`, {
          title: form.title, author: form.author, publisher: form.publisher, category: form.category,
          total_copies: Number(form.total_copies), available_copies: Number(form.available_copies),
          loan_days: form.loan_days === '' ? null : Number(form.loan_days),
          daily_fine: form.daily_fine === '' ? null : Number(form.daily_fine),
        })
      } else {
        await api.post('/api/library/books', {
          title: form.title, author: form.author, publisher: form.publisher, category: form.category,
          total_copies: Number(form.total_copies),
          loan_days: form.loan_days === '' ? null : Number(form.loan_days),
          daily_fine: form.daily_fine === '' ? null : Number(form.daily_fine),
        })
      }
      onDone()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div><label className="label">Title</label><input required className="input" value={form.title} onChange={set('title')} /></div>
      <div className="grid grid-cols-2 gap-3">
        <div><label className="label">Author</label><input className="input" value={form.author} onChange={set('author')} /></div>
        <div><label className="label">Publisher</label><input className="input" value={form.publisher} onChange={set('publisher')} /></div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div><label className="label">Category</label><input className="input" value={form.category} onChange={set('category')} /></div>
        <div><label className="label">Total copies</label><input type="number" min={0} className="input" value={form.total_copies} onChange={set('total_copies')} /></div>
        {editing && (
          <div><label className="label">Available now</label><input type="number" min={0} max={form.total_copies} className="input" value={form.available_copies} onChange={set('available_copies')} /></div>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label" htmlFor="book-days">Loan period (days)</label>
          <input id="book-days" type="number" min={1} max={365} className="input" placeholder={`School standard: ${policy.loan_days}`} value={form.loan_days} onChange={set('loan_days')} />
        </div>
        <div>
          <label className="label" htmlFor="book-fine">Fine per late day (Le)</label>
          <input id="book-fine" type="number" min={0} step="any" className="input" placeholder={`School standard: ${Math.round(policy.daily_fine)}`} value={form.daily_fine} onChange={set('daily_fine')} />
        </div>
      </div>
      <p className="text-xs text-slate">Optional. Leave both empty to use the school standard set by the principal. Set a shorter period or a higher fine for books in high demand.</p>
      {editing && <p className="text-xs text-slate">Change "Available now" when a copy is lost, damaged or found. Changing total copies adjusts availability by the same amount.</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Saving...' : editing ? 'Save changes' : 'Add to catalog'}</button>
    </form>
  )
}

function BorrowForm({ book, onDone }) {
  const [policy] = usePolicy()
  const standardDays = book.loan_days || policy.loan_days
  const rate = book.daily_fine ?? policy.daily_fine
  const [studentId, setStudentId] = useState('')
  const [choice, setChoice] = useState('standard') // standard | 7 | 14 | 21 | 30 | custom | date
  const [customDays, setCustomDays] = useState('')
  const [pickedDate, setPickedDate] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const days = choice === 'standard' ? standardDays : choice === 'custom' ? Number(customDays) : choice === 'date' ? null : Number(choice)
  const dueDate = choice === 'date' ? pickedDate : (days > 0 ? inDays(days) : '')
  const ready = studentId && dueDate && (choice !== 'date' || pickedDate > localDate(new Date()))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const body = { book_id: book.id, student_id: studentId }
      if (choice === 'date') body.due_date = pickedDate
      else if (choice !== 'standard') body.loan_days = days
      await api.post('/api/library/borrow', body)
      onDone()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <StudentPicker value={studentId} onChange={setStudentId} />
      <div>
        <label className="label" htmlFor="loan-length">How long can they keep it?</label>
        <select id="loan-length" className="input" value={choice} onChange={(e) => setChoice(e.target.value)}>
          <option value="standard">Standard ({standardDays} days)</option>
          {[7, 14, 21, 30].filter((d) => d !== standardDays).map((d) => <option key={d} value={d}>{d} days</option>)}
          <option value="custom">Another number of days...</option>
          <option value="date">Until a date I choose...</option>
        </select>
      </div>
      {choice === 'custom' && (
        <div><label className="label" htmlFor="loan-custom">Number of days</label><input id="loan-custom" type="number" min={1} max={365} required className="input" value={customDays} onChange={(e) => setCustomDays(e.target.value)} /></div>
      )}
      {choice === 'date' && (
        <div><label className="label" htmlFor="loan-date">Due back on</label><input id="loan-date" type="date" required className="input" min={inDays(1)} max={inDays(365)} value={pickedDate} onChange={(e) => setPickedDate(e.target.value)} /></div>
      )}
      <p className="text-xs text-slate">
        {dueDate ? <>Due back <span className="text-paper">{dueDate}</span>. </> : null}
        {rate > 0 ? <>Late books cost {money(rate)} for each day after that.</> : <>This book has no late fine.</>}
      </p>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting || !ready} className="btn-primary w-full">{submitting ? 'Issuing...' : 'Issue book'}</button>
    </form>
  )
}

/** Taking a copy back: shows what is owed for lateness, and lets the librarian reduce or waive it with a reason. */
function ReturnForm({ loan, canAdjust, onDone }) {
  const calculated = loan.fine_due || 0
  const [amount, setAmount] = useState(String(calculated))
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const changed = canAdjust && Number(amount) !== calculated

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const body = changed ? { fine_amount: Number(amount), fine_note: note } : {}
      await api.post(`/api/library/borrow-records/${loan.id}/return`, body)
      onDone()
    } catch (err) { setError(err.message) }
    setSubmitting(false)
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm"><span className="font-medium">{loan.book_title}</span><span className="text-slate"> from {loan.borrower_name}</span></p>
      {loan.days_overdue > 0 ? (
        <div className="card p-3 text-sm">
          <p className="text-red-400 font-medium">{loan.days_overdue} day{loan.days_overdue === 1 ? '' : 's'} late (was due {loan.due_date})</p>
          <p className="text-xs text-slate mt-1">{loan.days_overdue} × {money(loan.daily_fine_rate)} per day = <span className="text-paper font-mono">{money(calculated)}</span></p>
        </div>
      ) : (
        <p className="text-sm text-leaf">Returned on time. No fine.</p>
      )}
      {canAdjust && loan.days_overdue > 0 && (
        <>
          <div>
            <label className="label" htmlFor="fine-amount">Fine to charge (Le)</label>
            <input id="fine-amount" type="number" min="0" step="any" required className="input" value={amount} onChange={(e) => setAmount(e.target.value)} />
            <p className="text-[11px] text-slate mt-1">Leave as it is to charge the full amount, or enter less, or 0 to waive it.</p>
          </div>
          {changed && (
            <div>
              <label className="label" htmlFor="fine-note">Reason for the change</label>
              <input id="fine-note" required minLength={3} className="input" placeholder="e.g. Waived, student was ill" value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
          )}
        </>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting} className="btn-primary w-full">{submitting ? 'Saving...' : 'Take back'}</button>
    </form>
  )
}

function Loans() {
  const { hasPermission } = useAuth()
  const [rows, setRows] = useState(null)
  const [status, setStatus] = useState('borrowed')
  const [returning, setReturning] = useState(null)
  const load = () => api.get(`/api/library/borrow-records${status ? `?status=${status}` : ''}`).then((d) => setRows(asList(d)))
  useEffect(() => { setRows(null); load() }, [status])
  const today = new Date().toISOString().slice(0, 10)

  return (
    <div>
      <div className="flex gap-1 mb-4">
        {[['borrowed', 'Out on loan'], ['returned', 'Returned'], ['', 'All']].map(([key, label]) => (
          <button
            key={label} onClick={() => setStatus(key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${status === key ? 'bg-leaf/15 border-leaf/40 text-leaf' : 'border-rule text-slate hover:text-paper'}`}
          >
            {label}
          </button>
        ))}
      </div>
      <Table
        emptyLabel="No loans to show"
        columns={[
          { key: 'book', header: 'Book', render: (r) => <span className="font-medium">{r.book_title}</span> },
          { key: 'who', header: 'Borrower', render: (r) => (
            <span className="flex items-center gap-2"><Avatar src={r.borrower_photo_url} name={r.borrower_name || ''} size={26} />{r.borrower_name}</span>
          ) },
          { key: 'out', header: 'Lent', render: (r) => <span className="text-xs text-slate">{r.borrowed_date}</span> },
          { key: 'due', header: 'Due', render: (r) => (
            <span className={`text-xs ${r.status === 'borrowed' && r.due_date < today ? 'text-red-400 font-medium' : 'text-slate'}`}>{r.due_date}</span>
          ) },
          { key: 'status', header: 'Status', render: (r) => (
            <Badge tone={r.status === 'returned' ? 'leaf' : r.due_date < today ? 'red' : 'sky'}>{r.status === 'returned' ? 'Returned' : r.due_date < today ? 'Overdue' : 'On loan'}</Badge>
          ) },
          { key: 'fine', header: 'Fine', render: (r) => {
            if (r.status === 'borrowed') return r.fine_due > 0 ? <span className="font-mono text-xs text-marigold">{money(r.fine_due)} so far</span> : 'N/A'
            if (r.fine_amount > 0) return <span className="font-mono text-xs text-marigold">{money(r.fine_amount)}{r.fine_calculated > r.fine_amount ? <span className="text-slate"> (reduced)</span> : null}</span>
            return r.fine_calculated > 0 ? <span className="text-xs text-slate" title={r.fine_note || ''}>Waived</span> : 'N/A'
          } },
          ...(hasPermission('library.circulation') ? [{
            key: 'actions', header: '', render: (r) => r.status === 'borrowed' && (
              <button onClick={() => setReturning(r)} className="btn-secondary !py-1 text-xs"><Undo2 size={13} /> Take back</button>
            ),
          }] : []),
        ]}
        rows={rows}
      />
      <Modal open={!!returning} onClose={() => setReturning(null)} title="Take back a book">
        {returning && <ReturnForm loan={returning} canAdjust={hasPermission('library.manage')} onDone={() => { setReturning(null); load() }} />}
      </Modal>
    </div>
  )
}

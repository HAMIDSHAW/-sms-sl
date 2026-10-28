import { useEffect, useState } from 'react'
import { Send, Mail, MailOpen, VenetianMask, Reply } from 'lucide-react'
import { PageHeader, EmptyState, Modal } from '../../components/ui'
import { api, asList } from '../../lib/api'

export default function MessagesInbox() {
  const [tab, setTab] = useState('inbox')
  const [messages, setMessages] = useState([])
  const [composeOpen, setComposeOpen] = useState(false)
  const [opened, setOpened] = useState(null)

  const load = () => api.get(`/api/messages/${tab}`).then((d) => setMessages(asList(d)))
  useEffect(() => { load() }, [tab])

  // Clicking a message opens it in full (with a reply box) and marks it read straight away.
  const openMessage = async (m) => {
    setOpened(m)
    if (tab === 'inbox' && !m.read_at) {
      setMessages((list) => list.map((x) => (x.id === m.id ? { ...x, read_at: new Date().toISOString() } : x)))
      api.patch(`/api/messages/${m.id}/read`).catch(load)
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Communication"
        title="Messages"
        action={<button onClick={() => setComposeOpen(true)} className="btn-primary text-xs"><Send size={14} /> Compose</button>}
      />

      <div className="flex gap-1 border-b border-rule mb-6">
        {['inbox', 'sent'].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`relative px-4 py-2.5 text-sm font-medium capitalize transition-colors ${tab === t ? 'text-paper' : 'text-slate hover:text-paper'}`}
          >
            {t}
            {tab === t && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-leaf" />}
          </button>
        ))}
      </div>

      {messages.length === 0 ? (
        <EmptyState title={`No ${tab} messages`} icon={Mail} />
      ) : (
        <div className="card divide-y divide-rule">
          {messages.map((m) => (
            <button
              key={m.id} onClick={() => openMessage(m)}
              className="w-full text-left flex items-start gap-3 px-4 py-3.5 hover:bg-white/[0.02] transition-colors"
            >
              {m.read_at || tab === 'sent' ? (
                <MailOpen size={16} className="text-slate mt-0.5 shrink-0" />
              ) : (
                <Mail size={16} className="text-leaf mt-0.5 shrink-0" />
              )}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <p className="text-xs text-slate">
                    {tab === 'inbox' ? 'From' : 'To'} <span className="font-medium text-paper">{m.sender_name || 'Unknown'}</span>
                  </p>
                  {m.is_anonymous && <VenetianMask size={11} className="text-slate" title="Sent anonymously" />}
                </div>
                <p className={`text-sm mt-0.5 ${!m.read_at && tab === 'inbox' ? 'font-semibold' : 'font-medium'}`}>{m.subject || '(no subject)'}</p>
                <p className="text-xs text-slate mt-0.5 truncate">{m.body}</p>
              </div>
              <span className="text-[11px] text-slate shrink-0">{new Date(m.created_at).toLocaleDateString()}</span>
            </button>
          ))}
        </div>
      )}

      <Modal open={!!opened} onClose={() => setOpened(null)} title={opened?.subject || '(no subject)'} wide>
        {opened && <MessageView message={opened} canReply={tab === 'inbox'} onReplied={() => { setOpened(null); load() }} />}
      </Modal>

      <Modal open={composeOpen} onClose={() => setComposeOpen(false)} title="New message">
        <ComposeForm onSent={() => { setComposeOpen(false); load() }} />
      </Modal>
    </div>
  )
}

function ComposeForm({ onSent }) {
  const [query, setQuery] = useState('')
  const [contacts, setContacts] = useState([])
  const [recipient, setRecipient] = useState(null)
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [anonymous, setAnonymous] = useState(false)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => {
      api.get(`/api/messages/contacts?q=${encodeURIComponent(query)}`).then((d) => setContacts(asList(d)))
    }, 250)
    return () => clearTimeout(t)
  }, [query])

  const submit = async (e) => {
    e.preventDefault()
    if (!recipient) {
      setError('Pick a recipient from the list')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await api.post('/api/messages', { recipient_user_id: recipient.id, subject, body, is_anonymous: anonymous })
      onSent()
    } catch (err) {
      setError(err.data?.error || 'Could not send message')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="label">Recipient</label>
        {recipient ? (
          <div className="flex items-center justify-between input !py-2">
            <span className="text-sm">{recipient.full_name} · {recipient.email}</span>
            <button type="button" onClick={() => setRecipient(null)} className="text-xs text-slate hover:text-paper">Change</button>
          </div>
        ) : (
          <>
            <input
              className="input" placeholder="Search by name or email"
              value={query} onChange={(e) => setQuery(e.target.value)}
            />
            {contacts.length > 0 && (
              <div className="mt-1.5 card divide-y divide-rule max-h-40 overflow-y-auto">
                {contacts.map((c) => (
                  <button
                    key={c.id} type="button" onClick={() => setRecipient(c)}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-white/5 transition-colors"
                  >
                    {c.full_name} <span className="text-slate text-xs">· {c.email}</span>
                  </button>
                ))}
              </div>
            )}
            {query && contacts.length === 0 && (
              <p className="text-xs text-slate mt-1.5">No one matching that search is available to message.</p>
            )}
          </>
        )}
      </div>
      <div>
        <label className="label">Subject</label>
        <input className="input" value={subject} onChange={(e) => setSubject(e.target.value)} />
      </div>
      <div>
        <label className="label">Message</label>
        <textarea required rows={4} className="input" value={body} onChange={(e) => setBody(e.target.value)} />
      </div>
      <label className="flex items-center gap-2 text-xs text-slate cursor-pointer">
        <input type="checkbox" checked={anonymous} onChange={(e) => setAnonymous(e.target.checked)} />
        Send anonymously (recipient won't see your name)
      </label>
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={submitting} className="btn-primary w-full">
        {submitting ? 'Sending...' : 'Send message'}
      </button>
    </form>
  )
}

function MessageView({ message, canReply, onReplied }) {
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  const reply = async (e) => {
    e.preventDefault()
    setSending(true)
    setError('')
    try {
      await api.post(`/api/messages/${message.id}/reply`, { body })
      onReplied()
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  return (
    <div>
      <p className="text-xs text-slate mb-4">
        {canReply ? 'From' : 'To'} <span className="font-medium text-paper">{message.sender_name || 'Unknown'}</span>
        {message.is_anonymous && ' (anonymous)'} · {new Date(message.created_at).toLocaleString()}
      </p>
      <div className="card p-4 text-sm whitespace-pre-wrap mb-5">{message.body}</div>
      {canReply && (
        <form onSubmit={reply} className="space-y-3">
          <label className="label">Your reply</label>
          <textarea required autoFocus rows={4} className="input" value={body} onChange={(e) => setBody(e.target.value)} placeholder="Write your reply" />
          {error && <p className="text-sm text-red-400">{error}</p>}
          <button type="submit" disabled={sending || !body.trim()} className="btn-primary"><Reply size={15} /> {sending ? 'Sending...' : 'Send reply'}</button>
        </form>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Send, CheckCircle2, Paperclip, Trash2, Clock, XCircle, Lock, CalendarPlus } from 'lucide-react'
import { Badge, EmptyState, FileUpload, Avatar, PhoneLink } from '../../components/ui'
import { api, asList } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'
import { useChildSelection } from '../../context/ChildContext'

const STATUS = {
  not_submitted: { label: 'Not submitted', tone: 'red' },
  overdue: { label: 'Overdue', tone: 'red' },
  submitted: { label: 'Submitted', tone: 'sky' },
  late: { label: 'Submitted late', tone: 'marigold' },
  graded: { label: 'Graded', tone: 'leaf' },
}

export default function AssignmentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user, hasPermission, hasRole } = useAuth()
  const childCtx = useChildSelection()
  const [assignment, setAssignment] = useState(null)
  const [rows, setRows] = useState([])
  const [content, setContent] = useState('')
  const [attachmentUrl, setAttachmentUrl] = useState('')
  const [filter, setFilter] = useState('all')
  const [error, setError] = useState('')
  const [missing, setMissing] = useState(false)
  const [newDue, setNewDue] = useState('')
  const [busy, setBusy] = useState(false)

  const canGrade = hasPermission('assignments.grade')
  const canSubmit = hasPermission('assignments.submit') && !canGrade
  const isParent = hasRole('parent')
  const isOwner = !!user?.staff_id && assignment?.staff_id === user.staff_id
  const canManage = !!assignment?.is_owner // the teacher who set it (or the administrator who set it for them)

  const load = () => {
    api.get(`/api/assignments/${id}`).then((a) => {
      setAssignment(a)
      const rowsFrom = (path) => api.get(`/api/assignments/${id}/${path}`).then((d) => setRows(asList(d))).catch(() => {})
      if (a.read_only) rowsFrom('progress')      // the principal: who handed in and the marks, never the work itself
      else if (canGrade) rowsFrom('roster')
      else rowsFrom('submissions')
    }).catch(() => setMissing(true))
  }
  useEffect(() => { load() }, [id])

  const submitWork = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api.post(`/api/assignments/${id}/submissions`, { content_text: content, attachment_url: attachmentUrl })
      load()
    } catch (err) { setError(err.message) }
  }

  const grade = async (submissionId, marks, feedback) => {
    setError('')
    try {
      await api.patch(`/api/assignments/${id}/submissions/${submissionId}/grade`, { marks_obtained: Number(marks), feedback })
      load()
    } catch (err) { setError(err.message) }
  }

  // Give students more time (this also reopens a closed assignment), or stop hand-ins early.
  const extend = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api.post(`/api/assignments/${id}/extend`, { due_date: newDue })
      setNewDue('')
      load()
    } catch (err) { setError(err.message) }
    setBusy(false)
  }
  const closeNow = async () => {
    if (!window.confirm('Close this assignment now? Students will not be able to hand in any more work. You can reopen it by extending the deadline.')) return
    setError('')
    try { await api.patch(`/api/assignments/${id}`, { status: 'closed' }); load() } catch (err) { setError(err.message) }
  }

  const remove = async () => {
    if (!window.confirm('Delete this assignment and all its submissions? This cannot be undone.')) return
    try {
      await api.delete(`/api/assignments/${id}`)
      navigate('/assignments')
    } catch (err) { setError(err.message) }
  }

  if (missing) {
    return (
      <div>
        <button onClick={() => navigate('/assignments')} className="flex items-center gap-1.5 text-sm text-slate hover:text-paper transition-colors mb-6">
          <ArrowLeft size={15} /> Back to assignments
        </button>
        <EmptyState title="This assignment is not available" description="It may have been deleted, or it belongs to another teacher. An assignment can only be opened by the teacher who set it and by the students it was set for." />
      </div>
    )
  }
  if (!assignment) return <div className="text-slate text-sm">Loading...</div>

  const closed = assignment.is_closed && assignment.status !== 'draft'
  const tomorrow = (() => { const d = new Date(); d.setDate(d.getDate() + 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` })()

  const mine = assignment.my_submission
  const childName = isParent && childCtx?.selectedChild ? childCtx.selectedChild.first_name : null
  const counts = {
    all: rows.length,
    to_grade: rows.filter((r) => ['submitted', 'late'].includes(r.status)).length,
    not_submitted: rows.filter((r) => r.status === 'not_submitted').length,
  }
  const visible = rows.filter((r) => filter === 'all' || (filter === 'to_grade' ? ['submitted', 'late'].includes(r.status) : r.status === 'not_submitted'))

  return (
    <div>
      <button onClick={() => navigate('/assignments')} className="flex items-center gap-1.5 text-sm text-slate hover:text-paper transition-colors mb-6">
        <ArrowLeft size={15} /> Back to assignments
      </button>

      <div className="flex items-start justify-between gap-4 mb-2">
        <div>
          <h1 className="font-display text-2xl font-semibold tracking-tight">{assignment.title}</h1>
          <p className="text-sm text-slate mt-1">
            {assignment.subject_name}{assignment.class_name ? `, ${assignment.class_name}` : ''} · Due {assignment.due_date} · {assignment.max_marks} marks
          </p>
          {assignment.extended && <p className="text-xs text-marigold mt-0.5">Deadline extended from {assignment.original_due_date}</p>}
        </div>
        <div className="flex items-center gap-2">
          {closed ? <Badge tone="marigold"><span className="inline-flex items-center gap-1"><Lock size={11} /> Closed</span></Badge> : <Badge tone="leaf">{assignment.status}</Badge>}
          {isOwner && (
            <button onClick={remove} className="btn-secondary !px-3 !py-1.5 text-xs text-red-400">
              <Trash2 size={13} /> Delete
            </button>
          )}
        </div>
      </div>

      <div className="card p-3 flex items-center gap-3 mb-5 w-fit">
        <Avatar src={assignment.teacher_photo_url} name={assignment.teacher_name || ''} size={36} />
        <div>
          <p className="text-[11px] uppercase tracking-wider text-slate">Set by</p>
          <p className="text-sm font-medium">{assignment.teacher_name || 'N/A'}</p>
          {(assignment.teacher_position || assignment.teacher_phone) && (
            <p className="text-xs text-slate">{assignment.teacher_position}{assignment.teacher_position && assignment.teacher_phone ? ' · ' : ''}{assignment.teacher_phone && <PhoneLink value={assignment.teacher_phone} />}</p>
          )}
        </div>
      </div>

      {(assignment.instructions || assignment.description) && (
        <p className="card p-4 text-sm mb-2 whitespace-pre-wrap">{assignment.instructions || assignment.description}</p>
      )}
      {assignment.attachment_url ? (
        <a href={assignment.attachment_url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-xs text-sky hover:underline mb-6 w-fit">
          <Paperclip size={13} /> {decodeURIComponent(assignment.attachment_url.split('/').pop())}
        </a>
      ) : <div className="mb-6" />}

      {error && <p className="text-sm text-red-400 mb-4">{error}</p>}

      {/* Student: hand in, or see what was handed in and the grade */}
      {canSubmit && !isParent && (
        <div className="card p-5">
          {rows[0] ? (
            <SubmissionSummary submission={rows[0]} maxMarks={assignment.max_marks} />
          ) : closed ? (
            <div className="flex items-start gap-2 text-sm">
              <Lock size={18} className="text-marigold shrink-0 mt-0.5" />
              <p>This assignment closed on <span className="font-medium">{assignment.due_date}</span>, so work can no longer be handed in. If you still need to hand it in, ask your teacher whether they can extend the deadline.</p>
            </div>
          ) : (
            <form onSubmit={submitWork} className="space-y-3">
              <label className="label">Your answer</label>
              <textarea rows={5} className="input" value={content} onChange={(e) => setContent(e.target.value)} placeholder="Type your answer, or just attach a file below" />
              <FileUpload value={attachmentUrl} onChange={setAttachmentUrl} label="Attach your work" />
              <button type="submit" disabled={!content && !attachmentUrl} className="btn-primary">
                <Send size={15} /> Submit assignment
              </button>
            </form>
          )}
        </div>
      )}

      {/* Parent: read only status for the child being viewed */}
      {isParent && (
        <div className="card p-5">
          <p className="eyebrow mb-3">{childName ? `${childName}'s work` : 'Submission status'}</p>
          {rows[0] ? (
            <SubmissionSummary submission={rows[0]} maxMarks={assignment.max_marks} />
          ) : (
            <div className="flex items-center gap-2 text-sm">
              {mine?.status === 'overdue' ? <XCircle size={18} className="text-red-400" /> : <Clock size={18} className="text-marigold" />}
              <span>{childName || 'Your child'} has not handed this in yet{mine?.status === 'overdue' ? ' and it is overdue.' : '.'}</span>
            </div>
          )}
        </div>
      )}

      {/* Teacher: the whole class, including who has not handed in */}
      {canManage && assignment.status !== 'draft' && (
        <form onSubmit={extend} className="card p-4 mb-5">
          <p className="text-sm font-medium flex items-center gap-2">
            {closed ? <><Lock size={15} className="text-marigold" /> Closed on {assignment.due_date}. Students can no longer hand in.</> : <>Open for hand-ins until the end of {assignment.due_date}.</>}
          </p>
          <p className="text-xs text-slate mt-1">Only you can change this. Extending {closed ? 'reopens it and ' : ''}tells the class and their parents the new deadline.</p>
          <div className="flex flex-wrap items-end gap-2 mt-3">
            <div>
              <label className="label" htmlFor="new-due">{closed ? 'Reopen until' : 'New deadline'}</label>
              <input id="new-due" type="date" required className="input !py-1.5 !text-xs" min={closed ? tomorrow : assignment.due_date} value={newDue} onChange={(e) => setNewDue(e.target.value)} />
            </div>
            <button type="submit" disabled={busy || !newDue} className="btn-secondary !py-1.5 text-xs"><CalendarPlus size={13} /> {closed ? 'Reopen' : 'Extend deadline'}</button>
            {!closed && <button type="button" onClick={closeNow} className="btn-secondary !py-1.5 text-xs !text-marigold ml-auto"><Lock size={13} /> Close now</button>}
          </div>
        </form>
      )}
      {assignment.read_only && (
        <div>
          <p className="text-sm text-slate card p-3 mb-4">
            Read-only view. This assignment was set by <span className="text-paper">{assignment.teacher_name}</span>. Only they can see what students handed in, grade it, or change the deadline.
          </p>
          <p className="text-xs text-slate mb-3">
            {(rows || []).filter((r) => r.status !== 'not_submitted').length} of {(rows || []).length} students have handed in · {(rows || []).filter((r) => r.status === 'graded').length} graded
          </p>
          <div className="card divide-y divide-rule">
            {(rows || []).map((r) => (
              <div key={r.student_id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                <span className="text-sm">{r.student_name} <span className="text-[11px] text-slate">{r.student_number}</span></span>
                <span className="flex items-center gap-2">
                  <Badge tone={(STATUS[r.status] || STATUS.not_submitted).tone}>{(STATUS[r.status] || STATUS.not_submitted).label}</Badge>
                  {r.status === 'graded' && <span className="font-mono text-xs text-marigold">{r.marks_obtained}/{assignment.max_marks}</span>}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {canGrade && !assignment.read_only && (
        <div>
          <div className="flex items-center gap-1 border-b border-rule mb-4">
            {[['all', 'Whole class'], ['to_grade', 'To grade'], ['not_submitted', 'Not submitted']].map(([key, label]) => (
              <button
                key={key} onClick={() => setFilter(key)}
                className={`px-4 py-2.5 text-sm font-medium transition-colors ${filter === key ? 'text-paper border-b-2 border-leaf' : 'text-slate hover:text-paper'}`}
              >
                {label} <span className="text-slate font-mono text-xs">({counts[key]})</span>
              </button>
            ))}
          </div>
          {visible.length === 0 ? (
            <EmptyState title="Nothing in this list" />
          ) : (
            <div className="space-y-3">
              {visible.map((r) => <GradeRow key={r.student_id} row={r} maxMarks={assignment.max_marks} onGrade={grade} />)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SubmissionSummary({ submission, maxMarks }) {
  const info = STATUS[submission.status] || STATUS.submitted
  return (
    <div>
      <div className="flex items-center gap-2 text-sm font-medium mb-2">
        <CheckCircle2 size={18} className="text-leaf" />
        Handed in {submission.submitted_at ? `on ${new Date(submission.submitted_at).toLocaleDateString()}` : ''}
        <Badge tone={info.tone}>{info.label}</Badge>
        {submission.status === 'graded' && (
          <span className="ml-auto font-mono text-marigold text-base">{submission.marks_obtained}/{maxMarks}</span>
        )}
      </div>
      {submission.content_text && <p className="text-sm text-slate whitespace-pre-wrap mb-2">{submission.content_text}</p>}
      {submission.attachment_url && (
        <a href={submission.attachment_url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-xs text-sky hover:underline w-fit mb-2">
          <Paperclip size={12} /> {decodeURIComponent(submission.attachment_url.split('/').pop())}
        </a>
      )}
      {submission.status === 'graded' && (
        <div className="mt-3 pt-3 border-t border-rule text-sm">
          {submission.feedback && <p><span className="text-slate">Teacher feedback: </span>{submission.feedback}</p>}
          {submission.graded_by_name && <p className="text-xs text-slate mt-1">Graded by {submission.graded_by_name}</p>}
        </div>
      )}
    </div>
  )
}

function GradeRow({ row, maxMarks, onGrade }) {
  const [marks, setMarks] = useState(row.marks_obtained ?? '')
  const [feedback, setFeedback] = useState(row.feedback ?? '')
  const info = STATUS[row.status] || STATUS.submitted
  const handedIn = row.status !== 'not_submitted'

  return (
    <div className="card p-4">
      <div className="flex items-center gap-3 mb-2">
        <Avatar src={row.student_photo_url} name={row.student_name || ''} size={34} />
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">{row.student_name}</p>
          <p className="text-xs text-slate font-mono">{row.student_number}{row.class_name ? ` · ${row.class_name}` : ''}</p>
        </div>
        <div className="ml-auto text-right">
          <Badge tone={info.tone}>{info.label}</Badge>
          {row.submitted_at && <p className="text-[11px] text-slate mt-1">{new Date(row.submitted_at).toLocaleString()}</p>}
        </div>
      </div>
      {handedIn ? (
        <>
          <p className="text-sm mb-2">{row.content_text || <span className="text-slate italic">No text submitted</span>}</p>
          {row.attachment_url && (
            <a href={row.attachment_url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-xs text-sky hover:underline mb-3 w-fit">
              <Paperclip size={12} /> {decodeURIComponent(row.attachment_url.split('/').pop())}
            </a>
          )}
          <div className="flex items-center gap-2">
            <input
              type="number" min={0} max={maxMarks} placeholder={`/${maxMarks}`}
              className="input !py-1.5 !text-xs w-20" value={marks} onChange={(e) => setMarks(e.target.value)}
            />
            <input placeholder="Feedback for the student" className="input !py-1.5 !text-xs flex-1" value={feedback} onChange={(e) => setFeedback(e.target.value)} />
            <button onClick={() => onGrade(row.id, marks, feedback)} disabled={marks === ''} className="btn-secondary !py-1.5 text-xs">
              {row.status === 'graded' ? 'Update grade' : 'Save grade'}
            </button>
          </div>
          {row.status === 'graded' && row.graded_by_name && <p className="text-[11px] text-slate mt-2">Graded by {row.graded_by_name}</p>}
        </>
      ) : (
        <p className="text-xs text-slate">Nothing handed in yet.</p>
      )}
    </div>
  )
}

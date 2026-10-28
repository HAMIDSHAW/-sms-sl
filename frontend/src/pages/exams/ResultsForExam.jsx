import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Sparkles } from 'lucide-react'
import { Badge, EmptyState } from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../context/AuthContext'

const WORKFLOW_TONE = {
  draft: 'slate', teacher_submitted: 'sky', exam_officer_review: 'marigold',
  principal_approved: 'marigold', published: 'leaf',
}

const NEXT_ACTION = {
  draft: { action: 'submit', label: 'Submit', perm: 'results.submit' },
  teacher_submitted: { action: 'review', label: 'Review', perm: 'results.review' },
  exam_officer_review: { action: 'approve', label: 'Approve', perm: 'results.approve' },
  principal_approved: { action: 'publish', label: 'Publish', perm: 'results.publish' },
}

export default function ResultsForExam() {
  const { examId } = useParams()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const [results, setResults] = useState([])
  const [students, setStudents] = useState({})

  const load = async () => {
    const rs = await api.get(`/api/results?examination_id=${examId}`)
    setResults(rs)
    const ids = [...new Set(rs.map((r) => r.student_id))]
    const map = {}
    await Promise.all(ids.map(async (id) => { map[id] = await api.get(`/api/students/${id}`) }))
    setStudents(map)
  }
  useEffect(() => { load() }, [examId])

  const runAction = async (result) => {
    await api.post(`/api/results/${result.id}/${NEXT_ACTION[result.status].action}`)
    load()
  }

  return (
    <div>
      <button onClick={() => navigate('/exams')} className="flex items-center gap-1.5 text-sm text-slate hover:text-paper transition-colors mb-6">
        <ArrowLeft size={15} /> Back to examinations
      </button>

      <div className="flex items-center justify-between mb-6">
        <h1 className="font-display text-2xl font-semibold tracking-tight">Results</h1>
      </div>

      {results.length === 0 ? (
        <EmptyState title="No results yet" description="Enter marks for this examination's schedules, then compute results." />
      ) : (
        <div className="card divide-y divide-rule">
          {results.map((r) => {
            const next = NEXT_ACTION[r.status]
            const student = students[r.student_id]
            return (
              <div key={r.id} className="flex items-center justify-between px-4 py-3.5">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-sky/15 flex items-center justify-center text-xs font-display font-semibold text-sky">
                    {student ? student.first_name[0] + student.last_name[0] : '··'}
                  </div>
                  <div>
                    <p className="text-sm font-medium">{student?.full_name || '…'}</p>
                    <p className="text-xs text-slate font-mono">{r.average_percentage}% · {r.overall_grade}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={WORKFLOW_TONE[r.status]}>{(r.status || 'unknown').replace(/_/g, ' ')}</Badge>
                  {r.status === 'published' && (
                    <button
                      onClick={() => navigate(`/exams/${examId}/report-card/${r.student_id}`)}
                      className="btn-secondary !py-1.5 text-xs"
                    >
                      <Sparkles size={13} /> Report card
                    </button>
                  )}
                  {next && hasPermission(next.perm) && (
                    <button onClick={() => runAction(r)} className="btn-primary !py-1.5 text-xs">
                      {next.label}
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

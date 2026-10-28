import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, Award, TrendingUp, Printer, Users, CalendarCheck } from 'lucide-react'
import { api } from '../../lib/api'

function ordinal(n) {
  const v = n % 100
  const suffix = ['th', 'st', 'nd', 'rd']
  return `${n}${suffix[(v - 20) % 10] || suffix[v] || suffix[0]}`
}

export default function ReportCard() {
  const { examId, studentId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [revealed, setRevealed] = useState(false)

  useEffect(() => {
    api.get(`/api/results/report-card/${studentId}/${examId}`).then((d) => {
      setData(d)
      setTimeout(() => setRevealed(true), 250)
    })
  }, [examId, studentId])

  if (!data) return <div className="text-slate text-sm">Loading...</div>

  const { school, student, examination, subjects, summary, class: classInfo, class_average, attendance, position, ranked_count } = data
  const gradeColor = summary.is_pass ? 'text-leaf' : 'text-red-400'

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-8 print:hidden">
        <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm text-slate hover:text-paper transition-colors">
          <ArrowLeft size={15} /> Back
        </button>
        <button onClick={() => window.print()} className="btn-secondary text-xs">
          <Printer size={14} /> Print
        </button>
      </div>

      {/* The signature moment: the card flips in from behind, like turning
          over a physical report card to see the grade, a direct nod to
          the subject rather than a generic fade-in. */}
      <div style={{ perspective: 1400 }}>
        <motion.div
          initial={{ rotateY: -90, opacity: 0 }}
          animate={revealed ? { rotateY: 0, opacity: 1 } : {}}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          style={{ transformStyle: 'preserve-3d' }}
          className="card p-8 bg-ruled print-area"
        >
          <div className="flex items-start justify-between mb-8 pb-6 border-b border-rule">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-lg bg-leaf flex items-center justify-center overflow-hidden shrink-0">
                {school.logo_url ? <img src={school.logo_url} alt="" className="w-full h-full object-cover" /> : <Award size={20} className="text-ink" />}
              </div>
              <div>
                <p className="font-display font-semibold text-sm">{school.name}</p>
                <p className="text-xs text-slate">{school.address}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="eyebrow">{examination.name}</p>
              <p className="text-xs text-slate mt-1">{examination.term_name}</p>
            </div>
          </div>

          <div className="flex items-center justify-between mb-2">
            <div>
              <p className="text-xs text-slate mb-1">Student</p>
              <h1 className="font-display text-2xl font-semibold tracking-tight">{student.full_name}</h1>
              <p className="text-xs text-slate mt-1 font-mono">{student.student_number}</p>
            </div>
            <motion.div
              initial={{ scale: 0 }}
              animate={revealed ? { scale: 1 } : {}}
              transition={{ delay: 0.5, type: 'spring', bounce: 0.5 }}
              className="text-center"
            >
              <div className={`w-16 h-16 rounded-full border-2 flex items-center justify-center font-display text-2xl font-bold ${gradeColor} ${summary.is_pass ? 'border-leaf' : 'border-red-400'}`}>
                {summary.overall_grade}
              </div>
              {position && (
                <p className="text-[11px] text-marigold font-medium mt-1.5 flex items-center gap-1 justify-center">
                  <TrendingUp size={11} /> {ordinal(position)} position
                </p>
              )}
            </motion.div>
          </div>

          {classInfo && (
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate mb-6 pb-4 border-b border-rule">
              <span>Class: <span className="text-paper font-medium">{classInfo.name}</span></span>
              {classInfo.class_teacher_name && (
                <span>Class teacher: <span className="text-paper font-medium">{classInfo.class_teacher_name}</span></span>
              )}
              {classInfo.class_size != null && (
                <span className="flex items-center gap-1"><Users size={12} /> {classInfo.class_size} students in class</span>
              )}
            </div>
          )}

          <table className="w-full text-sm mb-6">
            <thead>
              <tr className="border-b border-rule text-xs text-slate uppercase tracking-wider">
                <th className="text-left font-medium py-2">Subject</th>
                <th className="text-right font-medium py-2">Marks</th>
                <th className="text-right font-medium py-2">%</th>
                <th className="text-right font-medium py-2">Remark</th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((s, i) => {
                const notExamined = s.obtained_marks == null && !s.is_absent
                return (
                  <motion.tr
                    key={s.code}
                    initial={{ opacity: 0, x: -8 }}
                    animate={revealed ? { opacity: 1, x: 0 } : {}}
                    transition={{ delay: 0.6 + i * 0.06 }}
                    className="border-b border-rule last:border-0"
                  >
                    <td className="py-2.5">{s.subject}</td>
                    <td className="py-2.5 text-right font-mono">
                      {s.is_absent ? 'Absent' : notExamined ? 'N/A' : `${s.obtained_marks}/${s.max_marks}`}
                    </td>
                    <td className="py-2.5 text-right font-mono text-slate">{s.percentage != null ? `${s.percentage}%` : 'N/A'}</td>
                    <td className={`py-2.5 text-right text-xs ${notExamined ? 'text-slate italic' : ''}`}>{s.remark || 'N/A'}</td>
                  </motion.tr>
                )
              })}
            </tbody>
          </table>

          <div className="grid grid-cols-4 gap-3 mb-6 text-sm">
            <div className="card !bg-white/[0.02] p-3 border-marigold/40">
              <p className="eyebrow mb-1">Position</p>
              <p className="font-mono font-semibold text-marigold">{position ? `${ordinal(position)} of ${ranked_count || classInfo?.class_size || '?'}` : 'N/A'}</p>
            </div>
            <div className="card !bg-white/[0.02] p-3">
              <p className="eyebrow mb-1">Total marks</p>
              <p className="font-mono font-semibold">{summary.total_marks}/{summary.total_max_marks}</p>
            </div>
            <div className="card !bg-white/[0.02] p-3">
              <p className="eyebrow mb-1">Class average</p>
              <p className="font-mono font-semibold">{class_average != null ? `${class_average}%` : 'N/A'}</p>
            </div>
            <div className="card !bg-white/[0.02] p-3">
              <p className="eyebrow mb-1 flex items-center gap-1"><CalendarCheck size={11} /> Attendance</p>
              <p className="font-mono font-semibold">
                {attendance?.total_days ? `${attendance.present_days}/${attendance.total_days} (${attendance.attendance_rate}%)` : 'N/A'}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {summary.teacher_remark && (
              <div>
                <p className="eyebrow mb-1">Teacher's remark</p>
                <p className="text-sm text-slate">{summary.teacher_remark}</p>
              </div>
            )}
            {summary.principal_remark && (
              <div>
                <p className="eyebrow mb-1">Principal's remark</p>
                <p className="text-sm text-slate">{summary.principal_remark}</p>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  )
}

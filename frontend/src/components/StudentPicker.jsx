import { useEffect, useId, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { api } from '../lib/api'

const asList = (d) => (Array.isArray(d) ? d : d?.items || [])

/**
 * Pick a student safely: choose the class first, then search inside that class.
 * Two students with the same name in different classes can never be confused,
 * because the list only ever shows one class at a time and every row shows the
 * student number.
 *
 * value: selected student id. onChange(studentId, student) is called on pick.
 */
export default function StudentPicker({ value, onChange, label = 'Student', required = true }) {
  const [classes, setClasses] = useState([])
  const [classId, setClassId] = useState('')
  const [students, setStudents] = useState(null)
  const [q, setQ] = useState('')
  const uid = useId()

  useEffect(() => {
    api.get('/api/academics/classes').then((d) => setClasses(asList(d))).catch(() => setClasses([]))
  }, [])

  useEffect(() => {
    setQ('')
    onChange('', null)
    if (!classId) { setStudents(null); return }
    setStudents(null)
    api.get(`/api/students?class_id=${classId}&per_page=200`).then((d) => setStudents(asList(d))).catch(() => setStudents([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classId])

  const shown = useMemo(() => {
    const term = q.trim().toLowerCase()
    if (!students) return []
    if (!term) return students
    return students.filter((s) => `${s.first_name} ${s.last_name} ${s.student_number}`.toLowerCase().includes(term))
  }, [students, q])

  return (
    <div className="space-y-2">
      <div>
        <label className="label" htmlFor={`${uid}-class`}>Class</label>
        <select id={`${uid}-class`} className="input" value={classId} onChange={(e) => setClassId(e.target.value)} required={required}>
          <option value="">Choose the class first</option>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      <div>
        <label className="label" htmlFor={`${uid}-student`}>{label}</label>
        <div className="relative mb-2">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate" />
          <input
            aria-label="Search students in this class"
            className="input pl-9" placeholder={classId ? 'Search by name or student number' : 'Pick a class to search its students'}
            value={q} onChange={(e) => setQ(e.target.value)} disabled={!classId}
          />
        </div>
        <select
          id={`${uid}-student`} className="input" size={classId ? 5 : 1} value={value || ''} required={required} disabled={!classId}
          onChange={(e) => onChange(e.target.value, students?.find((s) => s.id === e.target.value) || null)}
        >
          {!classId && <option value="">Choose a class above</option>}
          {classId && students == null && <option value="">Loading students...</option>}
          {classId && students && shown.length === 0 && <option value="">No student matches</option>}
          {shown.map((s) => (
            <option key={s.id} value={s.id}>{s.first_name} {s.last_name} ({s.student_number})</option>
          ))}
        </select>
      </div>
    </div>
  )
}

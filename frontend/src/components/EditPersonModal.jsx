import { useEffect, useState } from 'react'
import { Modal } from './ui'
import { api } from '../lib/api'

/**
 * A small edit dialog for a person's record (staff, student or guardian).
 *
 * fields: [{ key, label, type?: 'text'|'number'|'select'|'tel'|'email', options?: [[value, label]], required?, hint?, wide? }]
 * Only the fields that were actually changed are sent. `note` is shown above the form.
 */
export default function EditPersonModal({ open, onClose, title, endpoint, initial, fields, note, onSaved }) {
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setError('')
    setForm(Object.fromEntries(fields.map((f) => [f.key, initial?.[f.key] ?? ''])))
  }, [open, initial])

  const set = (k) => (e) => setForm((s) => ({ ...s, [k]: e.target.value }))

  const save = async (e) => {
    e.preventDefault()
    setError('')
    const body = {}
    for (const f of fields) {
      const before = initial?.[f.key] ?? ''
      if (String(form[f.key] ?? '') !== String(before)) {
        body[f.key] = f.type === 'number' ? (form[f.key] === '' ? null : Number(form[f.key])) : form[f.key]
      }
    }
    if (Object.keys(body).length === 0) { onClose(); return }
    setSaving(true)
    try {
      const updated = await api.patch(endpoint, body)
      onSaved?.(updated)
      onClose()
    } catch (err) { setError(err.message) }
    setSaving(false)
  }

  return (
    <Modal open={open} onClose={onClose} title={title}>
      <form onSubmit={save} className="space-y-4">
        {note && <p className="text-xs text-slate">{note}</p>}
        <div className="grid grid-cols-2 gap-3">
          {fields.map((f) => (
            <div key={f.key} className={f.wide ? 'col-span-2' : ''}>
              <label className="label" htmlFor={`edit-${f.key}`}>{f.label}</label>
              {f.type === 'select' ? (
                <select id={`edit-${f.key}`} className="input" value={form[f.key] ?? ''} onChange={set(f.key)}>
                  {f.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              ) : (
                <input
                  id={`edit-${f.key}`} className="input" required={f.required}
                  type={f.type || 'text'} {...(f.type === 'number' ? { min: 0, step: 'any' } : {})}
                  value={form[f.key] ?? ''} onChange={set(f.key)}
                />
              )}
              {f.hint && <p className="text-[11px] text-slate mt-1">{f.hint}</p>}
            </div>
          ))}
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
        <div className="flex gap-2">
          <button type="button" className="btn-secondary flex-1" onClick={onClose}>Cancel</button>
          <button type="submit" disabled={saving} className="btn-primary flex-1">{saving ? 'Saving...' : 'Save changes'}</button>
        </div>
      </form>
    </Modal>
  )
}

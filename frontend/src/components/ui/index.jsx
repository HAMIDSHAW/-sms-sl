import { useEffect, useId, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Inbox, Eye, EyeOff, Camera, Loader2, X } from 'lucide-react'
import { uploadFile } from '../../lib/api'

/**
 * A circular (or square, via `shape`) image picker: click to choose a file,
 * it uploads immediately and calls onChange(url) with the new public URL.
 * Used for profile photos and the school logo, replaces what used to be a
 * plain "paste a URL" text input.
 */
export function ImageUpload({ value, onChange, shape = 'circle', size = 56, kind = 'image', fallback: Fallback = Camera }) {
  const inputRef = useRef(null)
  const [uploading, setUploading] = useState(null) // false | 'uploading' | 'error'

  const pick = () => inputRef.current?.click()

  const onFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = '' // allow re-picking the same file later
    if (!file) return
    setUploading('uploading')
    try {
      const url = await uploadFile(file, kind)
      onChange(url)
      setUploading(null)
    } catch {
      setUploading('error')
      setTimeout(() => setUploading(null), 2500)
    }
  }

  return (
    <button
      type="button" onClick={pick}
      className={`relative shrink-0 bg-sky/15 flex items-center justify-center overflow-hidden group ${shape === 'circle' ? 'rounded-full' : 'rounded-lg'}`}
      style={{ width: size, height: size }}
      title="Change photo"
    >
      {value ? (
        <img src={value} alt="" className="w-full h-full object-cover" />
      ) : (
        <Fallback size={size * 0.5} className="text-sky" />
      )}
      <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
        {uploading === 'uploading' ? <Loader2 size={size * 0.3} className="animate-spin text-paper" /> : <Camera size={size * 0.35} className="text-paper" />}
      </div>
      {uploading === 'error' && (
        <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-[10px] text-red-400 whitespace-nowrap">Upload failed</div>
      )}
      <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={onFile} />
    </button>
  )
}

/**
 * A plain "attach a file" button + filename chip, for assignment
 * attachments and submissions. Unlike ImageUpload this isn't a preview
 * thumbnail, just upload-and-show-the-name, since the file could be a
 * PDF, a Word doc, a zip, etc.
 */
export function FileUpload({ value, onChange, label = 'Attach a file' }) {
  const inputRef = useRef(null)
  const [state, setState] = useState(null) // null | 'uploading' | 'error'

  const onFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setState('uploading')
    try {
      const url = await uploadFile(file, 'document')
      onChange(url, file.name)
      setState(null)
    } catch {
      setState('error')
      setTimeout(() => setState(null), 2500)
    }
  }

  const filename = value ? decodeURIComponent(value.split('/').pop()) : null

  return (
    <div>
      <button
        type="button" onClick={() => inputRef.current?.click()}
        className="btn-secondary text-xs"
        disabled={state === 'uploading'}
      >
        {state === 'uploading' ? <Loader2 size={14} className="animate-spin" /> : null}
        {value ? 'Replace file' : label}
      </button>
      {filename && <p className="text-xs text-slate mt-1.5 truncate">Attached: {filename}</p>}
      {state === 'error' && <p className="text-xs text-red-400 mt-1.5">Upload failed. Try again.</p>}
      <input ref={inputRef} type="file" className="hidden" onChange={onFile} />
    </div>
  )
}

export function PasswordInput({ value, onChange, placeholder, required, className = 'input', id }) {
  const [visible, setVisible] = useState(false)
  return (
    <div className="relative">
      <input
        id={id}
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        className={`${className} pr-10`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        tabIndex={-1}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate hover:text-paper transition-colors"
        aria-label={visible ? 'Hide password' : 'Show password'}
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  )
}

export function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 mb-7">
      <div className="min-w-0">
        {eyebrow && <p className="eyebrow mb-1.5">{eyebrow}</p>}
        <h1 className="font-display text-2xl font-semibold tracking-tight text-paper">{title}</h1>
        {description && <p className="text-sm text-slate mt-1.5 max-w-xl">{description}</p>}
      </div>
      {action && <div className="flex flex-wrap gap-2 max-w-full">{action}</div>}
    </div>
  )
}

export function StatCard({ label, value, icon: Icon, accent = 'leaf', index = 0 }) {
  const accents = {
    leaf: 'bg-leaf/12 text-leaf',
    sky: 'bg-sky/12 text-sky',
    marigold: 'bg-marigold/12 text-marigold',
  }
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.05 }}
      className="card p-5"
    >
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center mb-4 ${accents[accent]}`}>
        <Icon size={18} />
      </div>
      <p className="font-display text-2xl font-semibold tabular-nums">{value}</p>
      <p className="text-xs text-slate mt-1">{label}</p>
    </motion.div>
  )
}

// A blank ruled line waiting for an entry, not a generic "empty folder"
// icon-in-a-circle, the same restraint everywhere else in the app: one
// component, reused constantly, so a small considered touch here pays off
// on every single empty list in the system without any call site changing.
export function EmptyState({ title = 'Nothing here yet', description, icon: Icon = Inbox }) {
  return (
    <div className="card flex flex-col items-center justify-center text-center py-16 px-6 bg-ruled">
      <div className="w-11 h-11 rounded-lg border border-dashed border-white/15 flex items-center justify-center mb-4 bg-ink/40">
        <Icon size={18} className="text-slate" />
      </div>
      <p className="font-display font-medium text-paper mb-1">{title}</p>
      {description && <p className="text-sm text-slate max-w-sm">{description}</p>}
    </div>
  )
}

export function Badge({ children, tone = 'slate' }) {
  const tones = {
    slate: 'bg-white/5 text-slate',
    leaf: 'bg-leaf/12 text-leaf',
    sky: 'bg-sky/12 text-sky',
    marigold: 'bg-marigold/12 text-marigold',
    red: 'bg-red-400/12 text-red-400',
  }
  return <span className={`badge ${tones[tone]}`}>{children}</span>
}

/** Generic "something is loading here" placeholder for non-table layouts
 * (card grids, lists built by hand rather than via <Table>). */
export function BlockSkeleton({ rows = 3, height = 64 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="card animate-pulse" style={{ height }} />
      ))}
    </div>
  )
}

function TableSkeleton({ columns }) {
  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Data table, scrolls sideways on small screens">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule bg-white/[0.02]">
              {columns.map((col) => (
                <th key={col.key} className="text-left font-medium text-slate text-xs uppercase tracking-wider px-4 py-3 whitespace-nowrap">
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 6 }).map((_, i) => (
              <tr key={i} className="border-b border-rule last:border-0">
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-3">
                    <div className="h-3.5 rounded bg-white/5 animate-pulse" style={{ width: `${55 + ((i * 13 + col.key.length * 7) % 35)}%` }} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/**
 * rows === undefined/null means "hasn't loaded yet" and shows a skeleton;
 * rows === [] means "loaded, genuinely nothing here" and shows the real
 * empty state. These used to be treated identically, so every table
 * flashed "No records found" for a moment on every navigation before the
 * real data arrived, even for pages with hundreds of rows, it looked
 * like the app was slow/broken rather than just loading.
 */
export function Table({ columns, rows, keyField = 'id', onRowClick, emptyLabel = 'No records found' }) {
  if (rows == null) return <TableSkeleton columns={columns} />
  if (rows.length === 0) return <EmptyState title={emptyLabel} />

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Data table, scrolls sideways on small screens">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-rule bg-white/[0.02]">
              {columns.map((col) => (
                <th key={col.key} className="text-left font-medium text-slate text-xs uppercase tracking-wider px-4 py-3 whitespace-nowrap">
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <motion.tr
                key={row[keyField]}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2, delay: Math.min(i * 0.02, 0.3) }}
                onClick={() => onRowClick?.(row)}
                className={`border-b border-rule last:border-0 ${onRowClick ? 'cursor-pointer hover:bg-white/[0.03]' : ''} transition-colors`}
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-3 whitespace-nowrap">
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function Pagination({ page, pages, onChange }) {
  if (pages <= 1) return null
  return (
    <div className="flex items-center justify-center gap-2 mt-5">
      <button
        className="btn-secondary !px-3 !py-1.5 text-xs"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        Previous
      </button>
      <span className="text-xs text-slate font-mono px-2">{page} / {pages}</span>
      <button
        className="btn-secondary !px-3 !py-1.5 text-xs"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
      >
        Next
      </button>
    </div>
  )
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Accessible dialog: announced as a dialog with its title, closes on Escape or a click outside,
 * moves focus inside when it opens, keeps Tab inside it, and returns focus to what opened it.
 */
export function Modal({ open, onClose, title, children, wide }) {
  const titleId = useId()
  const panel = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const opener = document.activeElement
    const focusFirst = () => {
      const first = panel.current?.querySelector('[data-autofocus], input, select, textarea') || panel.current?.querySelector(FOCUSABLE)
      ;(first || panel.current)?.focus()
    }
    const t = setTimeout(focusFirst, 30)
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose?.(); return }
      if (e.key !== 'Tab' || !panel.current) return
      const items = [...panel.current.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null)
      if (!items.length) { e.preventDefault(); return }
      const first = items[0]
      const last = items[items.length - 1]
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      clearTimeout(t)
      document.removeEventListener('keydown', onKey)
      if (opener && typeof opener.focus === 'function') opener.focus()
    }
  }, [open])

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />
      <motion.div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        tabIndex={-1}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        className={`relative card w-full ${wide ? 'max-w-2xl' : 'max-w-md'} max-h-[85vh] overflow-y-auto p-6 outline-none`}
      >
        <button
          type="button" onClick={onClose} aria-label="Close dialog"
          className="absolute top-3 right-3 p-2 rounded-lg text-slate hover:text-paper hover:bg-white/5 transition-colors"
        >
          <X size={16} aria-hidden="true" />
        </button>
        {title && <h2 id={titleId} className="font-display text-lg font-semibold mb-4 pr-8">{title}</h2>}
        {children}
      </motion.div>
    </div>
  )
}

export function Avatar({ src, name = '', size = 32, className = '' }) {
  const initials = name.split(' ').filter(Boolean).slice(-2).map((p) => p[0]).join('').toUpperCase()
  return (
    <div
      className={`rounded-full bg-white/8 flex items-center justify-center text-[11px] font-semibold text-slate overflow-hidden shrink-0 ${className}`}
      style={{ width: size, height: size }}
    >
      {src ? <img src={src} alt="" className="w-full h-full object-cover" /> : initials}
    </div>
  )
}


/** A phone number that dials when tapped on a phone. Shows "N/A" when empty. */
export function PhoneLink({ value, className = '' }) {
  if (!value) return <span className={className}>N/A</span>
  const dial = String(value).replace(/[^\d+]/g, '')
  return <a href={`tel:${dial}`} className={`hover:underline text-sky ${className}`} onClick={(e) => e.stopPropagation()}>{value}</a>
}

/** An email address that opens the mail app. Shows "N/A" when empty. */
export function EmailLink({ value, className = '' }) {
  if (!value) return <span className={className}>N/A</span>
  return <a href={`mailto:${value}`} className={`hover:underline text-sky break-all ${className}`} onClick={(e) => e.stopPropagation()}>{value}</a>
}

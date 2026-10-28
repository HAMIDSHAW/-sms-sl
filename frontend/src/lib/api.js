// A stray slash on the end of VITE_API_URL is an easy typo and would produce //api/... addresses.
const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:5000').trim().replace(/\/+$/, '')

function getTokens() {
  return {
    access: localStorage.getItem('access_token'),
    refresh: localStorage.getItem('refresh_token'),
  }
}

function setTokens({ access_token, refresh_token }) {
  if (access_token) localStorage.setItem('access_token', access_token)
  if (refresh_token) localStorage.setItem('refresh_token', refresh_token)
}

function clearTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

let refreshPromise = null

// For a parent with several children: the child currently being viewed. Every
// child-scoped GET gets ?student_id=<child> added automatically, so no page can
// forget to follow the switcher (the server validates it is really their child).
let childScope = null
const CHILD_SCOPED_PREFIXES = [
  '/api/assignments', '/api/materials', '/api/attendance', '/api/invoices', '/api/payments',
  '/api/dashboard', '/api/timetable', '/api/results', '/api/exams', '/api/finance/summary',
]
function withChildScope(path, method) {
  if (!childScope || method !== 'GET' || path.includes('student_id=')) return path
  if (!CHILD_SCOPED_PREFIXES.some((p) => path.startsWith(p))) return path
  if (/^\/api\/(results\/report-card|finance\/ledger)/.test(path)) return path
  return path + (path.includes('?') ? '&' : '?') + 'student_id=' + encodeURIComponent(childScope)
}

async function tryRefresh() {
  const { refresh } = getTokens()
  if (!refresh) throw new Error('No refresh token')

  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/api/auth/refresh`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${refresh}` },
    })
      .then(async (res) => {
        if (!res.ok) throw new Error('Refresh failed')
        const data = await res.json()
        setTokens(data)
        return data.access_token
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

/**
 * Core request helper. Automatically attaches the access token, retries
 * once on a 401 by refreshing, and throws a normalized ApiError so callers
 * don't need to know about Response objects.
 */
async function request(path, { method = 'GET', body, isForm = false, retry = true } = {}) {
  const { access } = getTokens()
  const headers = {}
  if (access) headers['Authorization'] = `Bearer ${access}`
  if (!isForm && body !== undefined) headers['Content-Type'] = 'application/json'

  path = withChildScope(path, method)
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  })

  if (res.status === 401 && retry) {
    try {
      await tryRefresh()
      return request(path, { method, body, isForm, retry: false })
    } catch {
      clearTokens()
      window.location.href = '/login'
      throw new Error('Session expired')
    }
  }

  let data = null
  const text = await res.text()
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!res.ok) {
    const error = new Error((data && data.error) || 'Request failed')
    error.status = res.status
    error.data = data
    throw error
  }

  return data
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  delete: (path) => request(path, { method: 'DELETE' }),
  postForm: (path, formData) => request(path, { method: 'POST', body: formData, isForm: true }),
  setTokens,
  setChildScope: (id) => { childScope = id || null },
  clearTokens,
  getTokens,
  base: API_BASE,
}

/**
 * Upload a single file (profile photo, school logo, assignment/submission
 * attachment) and return its public URL. kind='image' restricts to image
 * types server-side; kind='document' (default) also allows pdf/doc/etc.
 */
/**
 * Download a file from an authenticated API endpoint (CSV/XLSX exports,
 * etc). A plain <a href="/api/..."> doesn't work for these, browser
 * navigation can't attach the Authorization header our API requires, so
 * every export link 401'd. This does a real authenticated fetch, then
 * hands the browser the result as a blob download.
 */
export async function downloadFile(path, fallbackFilename) {
  const { access } = getTokens()
  const res = await fetch(`${API_BASE}${path}`, {
    headers: access ? { Authorization: `Bearer ${access}` } : {},
  })
  if (!res.ok) throw new Error(`Download failed (${res.status})`)
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const filename = match ? match[1] : fallbackFilename

  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

export async function uploadFile(file, kind = 'document') {
  const formData = new FormData()
  formData.append('file', file)
  const data = await api.postForm(`/api/uploads?kind=${kind}`, formData)
  return data.url.startsWith('http') ? data.url : `${API_BASE}${data.url}`
}

/** Normalise a list response: accepts [..] or {items:[..]}; anything else becomes []. */
export function asList(d) {
  if (Array.isArray(d)) return d
  if (d && Array.isArray(d.items)) return d.items
  return []
}

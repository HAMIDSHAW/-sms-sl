import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center px-6">
      <div className="text-center max-w-sm">
        <Compass size={36} className="mx-auto mb-4 text-slate" aria-hidden="true" />
        <p className="eyebrow mb-2">Error 404</p>
        <h1 className="font-display text-2xl font-semibold mb-2">This page does not exist</h1>
        <p className="text-sm text-slate mb-6">The link may be wrong or the page may have moved.</p>
        <Link to="/" className="btn-primary">Go to the dashboard</Link>
      </div>
    </div>
  )
}

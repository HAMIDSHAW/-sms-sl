import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, info: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    this.setState({ info })
    // eslint-disable-next-line no-console
    console.error('Page crashed:', error, info)
  }

  componentDidUpdate(prevProps) {
    if (prevProps.routeKey !== this.props.routeKey && this.state.hasError) {
      this.setState({ hasError: false, error: null, info: null })
    }
  }

  render() {
    if (this.state.hasError) {
      const err = this.state.error
      const message = (err && (err.message || String(err))) || 'Unknown error'
      const stack = [err && err.stack, this.state.info && this.state.info.componentStack]
        .filter(Boolean).join('\n').split('\n').slice(0, 14).join('\n')
      return (
        <div className="card relative overflow-hidden flex flex-col items-center justify-center text-center py-12 px-6">
          {/* A mark in the margin, the way a form master would flag a line
              in a register that needs a second look, not a generic alert
              icon in a circle. */}
          <div
            className="absolute top-0 left-0 w-16 h-16 opacity-80"
            style={{
              background: 'linear-gradient(135deg, rgba(239,68,68,0.35) 0%, rgba(239,68,68,0.35) 48%, transparent 50%)',
            }}
          />
          <div className="w-11 h-11 rounded-lg border-2 border-red-400/40 flex items-center justify-center mb-4 relative -rotate-6">
            <AlertTriangle size={20} className="text-red-400" />
          </div>
          <p className="font-display font-medium text-paper mb-1">This page couldn't load</p>
          <p className="text-sm text-slate max-w-sm mb-4">
            Something went wrong rendering this screen. Try another page from the sidebar, or
            reload. Your session is still active.
          </p>
          <div className="flex gap-2 mb-4">
            <button className="btn-primary text-xs" onClick={() => window.location.reload()}>Reload page</button>
            <button className="btn-secondary text-xs" onClick={() => this.setState({ hasError: false, error: null, info: null })}>Try again</button>
          </div>
          <details className="w-full max-w-2xl text-left" open>
            <summary className="text-xs text-slate cursor-pointer mb-2">Error details (send this if the problem persists)</summary>
            <pre className="text-[11px] text-red-300 bg-black/30 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words">{message}{'\n\n'}{stack}</pre>
          </details>
        </div>
      )
    }
    return this.props.children
  }
}

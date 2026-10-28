import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { initA11y } from './lib/a11y'
import './index.css'

// StrictMode double-invokes effects in development specifically to surface
// side-effect bugs, which is exactly how the AppShell double-mount issue
// got found and fixed earlier. But it also means every single data fetch on
// every page fires twice during normal `npm run dev` testing (visible in
// your own backend log: every GET preceded by a duplicate OPTIONS+GET pair),
// which doubles perceived navigation latency for no benefit once a page is
// stable. Turned off here for snappier day-to-day testing; safe to wrap
// back in <React.StrictMode> temporarily if you're debugging a new
// component's effects.
ReactDOM.createRoot(document.getElementById('root')).render(<App />)

initA11y()

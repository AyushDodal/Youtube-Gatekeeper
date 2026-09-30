import { useEffect, useState } from 'react'
import { Sidebar, type Page } from './components/Sidebar'
import { Icon } from './components/Icon'
import { protectionLabels } from './components/ProtectionPanel'
import { useGatekeeper } from './hooks/useGatekeeper'
import { GatekeeperPage } from './pages/GatekeeperPage'
import { HistoryPage } from './pages/HistoryPage'
import { AboutPage } from './pages/AboutPage'

function currentPage(): Page {
  return window.location.hash === '#history' ? 'history' : window.location.hash === '#about' ? 'about' : 'gatekeeper'
}

export default function App() {
  const [page, setPage] = useState<Page>(currentPage)
  const state = useGatekeeper()
  useEffect(() => {
    const navigate = () => setPage(currentPage())
    window.addEventListener('hashchange', navigate)
    return () => window.removeEventListener('hashchange', navigate)
  }, [])
  const modelError = state.status && !state.status.model.available ? state.status.model.error : null
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <Sidebar page={page} setPage={setPage} state={state} />
    <div className="main-shell">
      <div className="topbar"><div className="breadcrumb"><Icon name="gate" size={15} /><span>Your workspace</span><span className="breadcrumb-slash">/</span><strong>{page === 'gatekeeper' ? 'Big Bro' : page === 'history' ? 'Usage history' : 'How it works'}</strong></div><div className={`top-status ${state.protection}`}><span className="status-dot" />{protectionLabels[state.protection]}</div></div>
      <main id="main-content" className={page === 'gatekeeper' ? 'chat-workspace' : undefined} tabIndex={-1}>
        {state.status?.dry_run && <div className="notice simulation"><Icon name="monitor" size={18} /><span><strong>Simulation mode</strong> — YouTube access is simulated. The Windows hosts file is not modified.</span></div>}
        {(state.connectionError || state.status?.error) && <div className="notice warning" role="alert"><Icon name="warning" size={18} /><span>{state.connectionError ?? state.status?.error}</span><button className="text-button" onClick={() => void state.refresh()}><Icon name="refresh" size={14} />Reconnect</button></div>}
        {!state.connectionError && modelError && <div className="notice model-notice" role="status"><Icon name="info" size={18} /><span><strong>Big Bro needs a local model.</strong> {modelError}</span><button className="text-button" onClick={() => setPage('about')}>Setup details<Icon name="chevron" size={13} /></button></div>}
        {page === 'gatekeeper' ? <GatekeeperPage state={state} /> : page === 'history' ? <HistoryPage state={state} /> : <AboutPage state={state} />}
      </main>
    </div>
  </div>
}

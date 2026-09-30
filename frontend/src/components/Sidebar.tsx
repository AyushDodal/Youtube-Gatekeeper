import type { GatekeeperState } from '../hooks/useGatekeeper'
import { Icon } from './Icon'

export type Page = 'gatekeeper' | 'history' | 'about'

export function Sidebar({ page, setPage, state }: { page: Page; setPage: (page: Page) => void; state: GatekeeperState }) {
  const connected = Boolean(state.status && !state.connectionError)
  return <aside className="sidebar">
    <a href="#gatekeeper" className="brand" onClick={() => setPage('gatekeeper')} aria-label="YouTube Gatekeeper home">
      <span className="brand-mark"><Icon name="gate" size={27} /></span>
      <span className="brand-name">YouTube<span>Gatekeeper<span className="brand-period">.</span></span></span>
    </a>
    <div className="workspace-label">YOUR WORKSPACE</div>
    <nav className="navigation" aria-label="Main navigation">
      <a href="#gatekeeper" aria-label="Big Bro" className={`nav-item ${page === 'gatekeeper' ? 'active' : ''}`} aria-current={page === 'gatekeeper' ? 'page' : undefined} onClick={() => setPage('gatekeeper')}><Icon name="chat" /> <span>Big Bro</span>{page === 'gatekeeper' && <span className="nav-dot" />}</a>
      <a href="#history" aria-label="Usage history" className={`nav-item ${page === 'history' ? 'active' : ''}`} aria-current={page === 'history' ? 'page' : undefined} onClick={() => setPage('history')}><Icon name="history" /><span>Usage history</span></a>
      <a href="#about" aria-label="How it works" className={`nav-item ${page === 'about' ? 'active' : ''}`} aria-current={page === 'about' ? 'page' : undefined} onClick={() => setPage('about')}><Icon name="info" /><span>How it works</span></a>
    </nav>
    <div className="sidebar-bottom">
      <div className="local-status"><span className={`status-dot ${connected ? 'green' : 'amber'}`} /><span>{connected ? 'Running on your machine' : 'Local server disconnected'}</span></div>
      <div className="sidebar-version"><span>LOCAL FIRST. ALWAYS.</span><span>v1.0</span></div>
    </div>
  </aside>
}

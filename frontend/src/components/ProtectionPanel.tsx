import type { GatekeeperState } from '../hooks/useGatekeeper'
import { minutes } from '../services/api'
import { Icon } from './Icon'

export const protectionLabels: Record<string, string> = { blocked: 'YouTube is blocked', unlocked: 'YouTube is unlocked', pending: 'Reblocking pending', unknown: 'Protection unverified', connecting: 'Connecting locally' }

export function ProtectionPanel({ state }: { state: GatekeeperState }) {
  const { status, protection, secondsRemaining, usage } = state
  const safe = protection === 'blocked'
  const open = protection === 'unlocked'
  const remaining = `${Math.floor(secondsRemaining / 60).toString().padStart(2, '0')}:${(secondsRemaining % 60).toString().padStart(2, '0')}`
  const percent = usage ? Math.min(100, (usage.today_minutes / Math.max(1, usage.daily_limit_minutes)) * 100) : 0
  return <aside className="context-rail" aria-label="Protection and usage">
    <section className={`protection-card ${safe ? 'protected' : ''} ${open ? 'access-active' : ''}`}>
      <div className="section-eyebrow">RIGHT NOW <span className={`status-dot ${safe ? 'green' : open ? 'blue' : 'amber'}`} /></div>
      <h2>{protectionLabels[protection]}</h2>
      {(!safe && !open) && <p className="protection-copy">{protection === 'pending' ? 'Waiting for blocking confirmation.' : 'Waiting for the local server.'}</p>}
      {open && <div className="countdown" role="timer" aria-label={`${Math.floor(secondsRemaining / 60)} minutes and ${secondsRemaining % 60} seconds remaining`}><span>{remaining}</span><small>UNTIL YOUTUBE IS BLOCKED</small></div>}
      <div className="protection-divider" />
      <div className="session-row"><Icon name="clock" size={15} /><span>Current session</span><strong>{open && status?.session ? `${status.session.duration_minutes} min` : safe ? 'None' : 'Unconfirmed'}</strong></div>
      {open && <button className="end-session" onClick={() => void state.block()} disabled={state.blocking || state.sending}><Icon name="stop" size={14} />{state.blocking ? 'Ending session…' : 'I’m done. Block YouTube.'}</button>}
      {protection === 'unknown' && status && <button className="end-session" onClick={() => void state.block()} disabled={state.blocking || state.sending}><Icon name="lock" size={14} />{state.blocking ? 'Blocking…' : 'Retry blocking YouTube'}</button>}
    </section>
    <section className="budget-card">
      <div className="section-eyebrow">TODAY’S ALLOWANCE <Icon name="clock" size={15} /></div>
      <div className="budget-total"><strong>{usage ? minutes(usage.today_minutes) : '—'}</strong><span>/ {usage ? usage.daily_limit_minutes : status?.limits.daily_limit_minutes ?? '—'} min</span></div>
      <div className="progress-track" role="progressbar" aria-label="Today's YouTube allowance used" aria-valuenow={usage?.today_minutes ?? 0} aria-valuemin={0} aria-valuemax={usage?.daily_limit_minutes ?? 100}><span style={{ width: `${percent}%` }} /></div>
      <p>{state.usageError ? 'Usage unavailable' : usage ? `${minutes(usage.remaining_minutes)} min remaining` : 'Loading usage'}</p>
      <div className="budget-policy"><span>Maximum per session</span><strong>{status ? `${status.limits.max_session_minutes} min` : '—'}</strong></div>
    </section>
  </aside>
}

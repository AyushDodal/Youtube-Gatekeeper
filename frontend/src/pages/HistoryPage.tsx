import { Icon } from '../components/Icon'
import type { GatekeeperState } from '../hooks/useGatekeeper'
import { dateValue, minutes } from '../services/api'

function dayLabel(value: string): string {
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { weekday: 'short' })
}

export function HistoryPage({ state }: { state: GatekeeperState }) {
  const { usage } = state
  const daily = usage?.daily ?? []
  const chartMax = Math.max(1, ...daily.map(day => day.minutes))
  return <>
    <header className="page-heading"><div className="eyebrow"><span />THE BIGGER PICTURE</div><h1>Time spent, on purpose<span>.</span></h1><p>A record of the access you asked for, and the time you chose to spend.</p></header>
    {state.usageError && <div className="notice warning" role="alert"><Icon name="warning" size={18} /><span>{state.usageError}</span><button className="text-button" onClick={() => void state.refresh()}>Retry</button></div>}
    <div className="history-summary"><div className="summary-card"><span>TODAY’S USAGE</span><strong>{usage ? minutes(usage.today_minutes) : '—'}<small> min</small></strong><p>Of {usage?.daily_limit_minutes ?? '—'} minutes available</p></div><div className="summary-card"><span>TIME LEFT TODAY</span><strong>{usage ? minutes(usage.remaining_minutes) : '—'}<small> min</small></strong><p>Spend it with intention</p></div><div className="summary-card"><span>RECENT SESSIONS</span><strong>{usage?.history.length ?? '—'}</strong><p>Every session started with a reason</p></div></div>
    <section className="history-chart panel"><div className="panel-heading"><div><h2>Your daily rhythm</h2><p>YouTube access time, in minutes</p></div><span className="chart-legend"><i />Daily usage</span></div>
      {daily.length > 0 ? <div className="chart-bars" role="img" aria-label={daily.map(day => `${day.date}: ${minutes(day.minutes)} minutes`).join('; ')}>{daily.map(day => <div className="chart-column" key={day.date}><div className="bar-space"><span className="bar-value">{minutes(day.minutes)}</span><div className={`chart-bar ${day.minutes === 0 ? 'empty-bar' : ''}`} style={{ height: `${Math.max(2, day.minutes / chartMax * 135)}px` }} /></div><span className="bar-day">{dayLabel(day.date)}</span><span className="bar-date">{new Date(`${day.date}T12:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}</span></div>)}</div> : <div className="chart-empty"><Icon name="history" size={26} /><p>{usage ? 'Your daily usage will appear here.' : 'Waiting for local usage data…'}</p></div>}
    </section>
    <section className="session-history panel"><div className="panel-heading"><div><h2>Session history</h2><p>The reason behind every visit</p></div><Icon name="history" size={20} /></div>{usage?.history.length ? <div className="session-table-wrap"><table><thead><tr><th>Reason</th><th>Started</th><th>Approved time</th><th>Status</th></tr></thead><tbody>{usage.history.map(session => <tr key={session.id}><td><span className="session-reason">{session.reason}</span></td><td>{new Date(dateValue(session.started_at)).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</td><td>{minutes(session.duration_minutes)} min</td><td><span className={`session-status ${session.status === 'active' ? 'active' : ''}`}>{session.status.replaceAll('_', ' ')}</span></td></tr>)}</tbody></table></div> : <div className="history-empty"><div className="empty-icon"><Icon name="history" size={27} /></div><h3>{usage ? 'A clean slate. Keep it intentional.' : 'Your history lives on this device.'}</h3><p>{usage ? 'Your approved sessions will appear here, along with why you opened YouTube and how long you had.' : 'Connect to the local backend to see your sessions.'}</p></div>}</section>
    <p className="history-note"><Icon name="info" size={15} />Usage measures the time YouTube access was available. It does not track your browsing or videos watched.</p>
  </>
}

import { Icon } from '../components/Icon'
import type { GatekeeperState } from '../hooks/useGatekeeper'

export function AboutPage({ state }: { state: GatekeeperState }) {
  const { status } = state
  return <>
    <header className="page-heading"><div className="eyebrow"><span />FRICTION, BY DESIGN</div><h1>A gate. Not a cage<span>.</span></h1><p>A small pause to turn an impulse into a decision. You’re still in control.</p></header>
    <section className="how-it-works panel"><div className="panel-heading"><div><h2>Every visit starts with an intention</h2><p>Four steps between you and the feed</p></div><Icon name="gate" size={25} /></div><div className="steps">{[
      ['01', 'Make your case', 'Explain what you need YouTube for. A specific goal and a realistic time limit help.'],
      ['02', 'Expect some pushback', 'Big Bro challenges vague reasons and asks useful questions. He has a job to do.'],
      ['03', 'Stay within the rules', 'The backend checks every request against your session and daily limits before allowing access.'],
      ['04', 'Get back to your day', 'When your approved time runs out, the running backend blocks YouTube again automatically.'],
    ].map(([number, title, description]) => <article className="step" key={number}><span>{number}</span><h3>{title}</h3><p>{description}</p></article>)}</div></section>
    <div className="about-grid"><section className="panel rules-panel"><div className="panel-heading"><div><h2>Your ground rules</h2><p>Big Bro can’t negotiate these</p></div><Icon name="shield" size={20} /></div><dl className="settings-list"><div><dt>Minimum session</dt><dd>{status ? `${status.limits.min_session_minutes} minutes` : '—'}</dd></div><div><dt>Maximum session</dt><dd>{status ? `${status.limits.max_session_minutes} minutes` : '—'}</dd></div><div><dt>Daily allowance</dt><dd>{status ? `${status.limits.daily_limit_minutes} minutes` : '—'}</dd></div><div><dt>Maximum question rounds</dt><dd>{status?.limits.max_question_rounds ?? '—'}</dd></div><div><dt>Unlimited access</dt><dd>Never</dd></div></dl><p className="settings-footnote">These are your backend’s configured limits. Update <code>config.yaml</code> and restart the backend to change them.</p></section>
    <section className="panel model-panel"><div className="panel-heading"><div><h2>Entirely on your machine</h2><p>Your attention is nobody else’s data</p></div><Icon name="monitor" size={20} /></div><dl className="settings-list"><div><dt>AI provider</dt><dd>Ollama · local</dd></div><div><dt>Model</dt><dd className="model-name">{status?.model.name || 'Not connected'}</dd></div><div><dt>Model status</dt><dd className={status?.model.available && !state.connectionError ? 'lime-text' : 'amber-text'}>{!status || state.connectionError ? 'Unverified' : status.model.available ? 'Ready' : 'Unavailable'}</dd></div><div><dt>Storage</dt><dd>SQLite · on this device</dd></div><div><dt>Operating mode</dt><dd>{status ? status.dry_run ? 'Simulation' : 'Windows hosts file' : 'Unverified'}</dd></div></dl><p className="settings-footnote">Configure the model with <code>OLLAMA_MODEL</code>. No cloud LLM service is required.</p></section></div>
    <section className="boundaries-note"><Icon name="info" size={21} /><div><h3>A productivity tool, with honest boundaries.</h3><p>Keep the backend running so it can end sessions on time. Hosts-file blocking can be affected by browser caches and alternative domains. This is voluntary friction, and an administrator can change or remove it. Your browser and the videos you watch aren’t monitored.</p></div></section>
  </>
}

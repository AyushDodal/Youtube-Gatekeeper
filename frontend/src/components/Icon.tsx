type IconName = 'gate' | 'chat' | 'history' | 'info' | 'settings' | 'arrow' | 'plus' | 'shield' | 'lock' | 'unlock' | 'clock' | 'check' | 'chevron' | 'book' | 'search' | 'coffee' | 'refresh' | 'warning' | 'monitor' | 'external' | 'stop' | 'close'

const paths: Record<IconName, React.ReactNode> = {
  gate: <><path d="M6 20V10a6 6 0 0 1 12 0v10M3 20h18M6 11h12M10 11v9m4-9v9" /></>,
  chat: <path d="M20 11.5a8.5 8.5 0 0 1-8.5 8.5 9 9 0 0 1-3.5-.7L3 21l1.7-5A9 9 0 0 1 4 12.5 8.5 8.5 0 0 1 12.5 4H13a8.5 8.5 0 0 1 7 7v.5Z" />,
  history: <><path d="M3 11a9 9 0 1 1 2.6 7M3 4v7h7M12 7v5l3 2" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7h.01" /></>,
  settings: <><path d="m9 3-.6 2.1-2 .9-2-.5-2 3.5 1.5 1.5-.2 2.2L2 14l2 3.5 2-.5 1.8 1.1.7 2.4h4l.7-2.4 1.8-1.1 2 .5 2-3.5-1.7-1.3-.2-2.2L21 9l-2-3.5-2 .5-2-.9L14.4 3Z" /><circle cx="11.5" cy="12" r="3" /></>,
  arrow: <path d="M12 19V5m-6 6 6-6 6 6" />,
  plus: <path d="M12 5v14M5 12h14" />,
  shield: <><path d="m12 3 8 3v6c0 4-4.5 7-8 9-3.5-2-8-5-8-9V6l8-3Z" /><path d="m8.5 12 2.2 2.2 4.8-4.8" /></>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3M12 15v2" /></>,
  unlock: <><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 7.5-2M12 15v2" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  chevron: <path d="m9 5 7 7-7 7" />,
  book: <><path d="M12 5v15M3 4c4-1 6 0 9 2 3-2 5-3 9-2v14c-4-1-6 0-9 2-3-2-5-3-9-2V4Z" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
  coffee: <><path d="M4 8h13v8a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4V8Zm13 1h2a3 3 0 0 1 0 6h-2M7 3v2m4-2v2m4-2v2" /></>,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5M6.1 6a8 8 0 0 1 13 1L20 12M4 12l.9 5A8 8 0 0 0 18 18" /></>,
  warning: <><path d="m10.3 4.5-8 14A1.5 1.5 0 0 0 3.6 21h16.8a1.5 1.5 0 0 0 1.3-2.5l-8-14a2 2 0 0 0-3.4 0ZM12 9v5m0 3h.01" /></>,
  monitor: <><rect x="3" y="4" width="18" height="13" rx="2" /><path d="M8 21h8m-4-4v4" /></>,
  external: <path d="M14 3h7v7m0-7L10 14M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5" />,
  stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
}

export function Icon({ name, size = 20, className = '' }: { name: IconName; size?: number; className?: string }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>{paths[name]}</svg>
}

export function BigBroAvatar({ size = 36 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 64 64" className="big-bro-avatar" aria-hidden="true">
    <rect width="64" height="64" rx="17" fill="#34432c" />
    <path d="M8 64v-5c0-10 12-15 24-15s24 5 24 15v5" fill="#18241e" />
    <path d="M25 41h14v10l-7 6-7-6" fill="#ba9777" />
    <path d="M18 23c0-12 28-12 28 0v12c0 10-8 15-14 15S18 44 18 35Z" fill="#d3b393" />
    <path d="M19 27c-6-1-6 10 1 10m25-10c6-1 6 10-1 10" fill="#c5a180" />
    <path d="M17 30V20C17 8 29 6 37 9c9-2 13 5 10 15l-3 7-2-12c-8 3-14 1-18-3l-3 14Z" fill="#202b25" />
    <path d="m23 26 7 2m5-1 7-2" stroke="#283128" strokeWidth="2.4" strokeLinecap="round" />
    <path d="M24 31h4m8 0h4" stroke="#283128" strokeWidth="1.8" strokeLinecap="round" />
    <path d="m32 31-1 7h3" fill="none" stroke="#aa8368" strokeWidth="1.5" strokeLinecap="round" />
    <path d="M21 38c3 7 6 10 11 10s9-4 11-10c-1 9-6 13-11 13s-10-5-11-13" fill="#485041" opacity=".55" />
    <path d="M27 42c4 1 7 1 11-1" fill="none" stroke="#725444" strokeWidth="1.7" strokeLinecap="round" />
    <path d="m22 49 10 8-6 4-6-11m22-1-10 8 6 4 6-11" fill="#455940" />
  </svg>
}

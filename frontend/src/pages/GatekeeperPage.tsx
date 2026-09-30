import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import type { GatekeeperState } from '../hooks/useGatekeeper'
import { BigBroAvatar, Icon } from '../components/Icon'
import { ProtectionPanel } from '../components/ProtectionPanel'
import type { ToolEvent } from '../services/api'

const starters = [
  { icon: 'book' as const, label: 'Learn something', prompt: 'I want to watch a tutorial about ' },
  { icon: 'search' as const, label: 'Research a topic', prompt: 'I’m researching ' },
  { icon: 'coffee' as const, label: 'Take a real break', prompt: 'I’m taking an intentional break. I plan to watch ' },
]

function toolLabel(event: ToolEvent): string {
  const names: Record<string, string> = { check_youtube_status: 'Status checked', grant_youtube_access: 'Access grant', deny_youtube_access: 'Access denied' }
  return names[event.name] ?? event.name.replaceAll('_', ' ')
}

export function GatekeeperPage({ state }: { state: GatekeeperState }) {
  const [draft, setDraft] = useState('')
  const textarea = useRef<HTMLTextAreaElement>(null)
  const messagesEnd = useRef<HTMLDivElement>(null)
  const hasMessages = state.messages.length > 0
  const unavailable = state.connectionError || (state.status && !state.status.model.available)

  useEffect(() => { messagesEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }) }, [state.messages, state.sending, state.chatError])

  const submit = async (event?: FormEvent) => {
    event?.preventDefault()
    if (!draft.trim() || state.sending || state.loadingConversation || state.conversationClosed) return
    const sent = draft
    setDraft('')
    const success = await state.sendMessage(sent)
    if (!success) setDraft(current => current || sent)
    textarea.current?.focus()
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      void submit()
    }
  }

  return <>
    <div className="gatekeeper-layout">
      <section className="chat-card" aria-label="Conversation with Big Bro">
        <div className="chat-header"><div className="chat-avatar"><BigBroAvatar size={40} /><span className={`avatar-status ${unavailable ? 'unavailable' : ''}`} /></div><div className="chat-header-info"><h1>Big Bro</h1><p>Stern by design. On your side.</p></div><button className="icon-button new-conversation" title="Start a new conversation" aria-label="Start a new conversation" disabled={state.sending || state.loadingConversation || !hasMessages} onClick={() => { state.newConversation(); setDraft(''); textarea.current?.focus() }}><Icon name="plus" size={19} /></button></div>
        <div className={`chat-body ${hasMessages ? 'has-messages' : ''}`} role="log" aria-label="Chat messages" aria-live="polite" aria-relevant="additions text">
          {state.loadingConversation ? <div className="conversation-loading"><span className="loading-ring" />Restoring your conversation…</div> : !hasMessages ? <div className="welcome-message">
            <article className="message assistant"><div className="message-avatar"><BigBroAvatar size={32} /></div><div className="message-content"><div className="message-author">BIG BRO</div><p>Alright. What do you need YouTube for?</p></div></article>
            <div className="starter-options">{starters.map(starter => <button key={starter.label} className="starter-chip" onClick={() => { setDraft(starter.prompt); textarea.current?.focus() }}><Icon name={starter.icon} size={16} />{starter.label}<Icon name="chevron" size={13} /></button>)}</div>
          </div> : <div className="message-list">{state.messages.map(message => <article key={message.id} className={`message ${message.role}`}>
            {message.role === 'assistant' && <div className="message-avatar"><BigBroAvatar size={32} /></div>}
            <div className="message-content"><div className="message-author">{message.role === 'assistant' ? 'BIG BRO' : 'YOU'}</div><p>{message.content}</p>
              {message.role === 'assistant' && message.decision && message.decision !== 'continue_questioning' && <span className={`decision-tag ${message.decision}`}><Icon name={message.decision === 'grant' ? 'clock' : 'lock'} size={13} />{message.decision === 'grant' ? 'Temporary access approved' : 'Request declined'}</span>}
              {message.tool_events && message.tool_events.length > 0 && <details className="tool-events"><summary><Icon name="shield" size={12} />{message.tool_events.length} verified tool {message.tool_events.length === 1 ? 'action' : 'actions'}</summary><ul>{message.tool_events.map((event, index) => <li key={index}><span>{toolLabel(event)}</span><span className="tool-status">{event.status}</span>{event.detail && <small>{event.detail}</small>}</li>)}</ul></details>}
            </div>
          </article>)}</div>}
          {state.sending && <div className="thinking" role="status"><span className="message-avatar"><BigBroAvatar size={32} /></span><span><strong>Big Bro is thinking</strong><span className="thinking-dots"><i /><i /><i /></span></span></div>}
          <div ref={messagesEnd} />
        </div>
        {state.chatError && <div className="chat-error" role="alert"><Icon name="warning" size={17} /><span>{state.chatError}</span></div>}
        {state.conversationClosed ? <div className="completed-request"><span>This request is complete.</span><button className="text-button" onClick={() => { state.newConversation(); setDraft('') }}><Icon name="plus" size={15} />Start a new request</button></div> : <form className="composer" onSubmit={event => void submit(event)}>
          <div className="composer-box"><label className="sr-only" htmlFor="chat-message">Your reason for using YouTube</label><textarea ref={textarea} id="chat-message" rows={2} value={draft} maxLength={4000} onChange={event => setDraft(event.target.value)} onKeyDown={onKeyDown} placeholder={hasMessages ? 'Make your case…' : 'I want to open YouTube because…'} disabled={state.sending || state.loadingConversation} /><button className="send-button" type="submit" title={state.chatError ? 'Retry your message' : 'Send message'} aria-label={state.chatError ? 'Retry your message' : 'Send message'} disabled={!draft.trim() || state.sending || state.loadingConversation}>{state.sending ? <span className="loading-ring" /> : <Icon name="arrow" size={21} />}</button></div>
          <div className="composer-caption"><span>Shift + Enter for a new line</span><span><kbd>↵</kbd> to send</span></div>
        </form>}
      </section>
      <ProtectionPanel state={state} />
    </div>
  </>
}

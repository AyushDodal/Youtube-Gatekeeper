import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, dateValue, request, type ChatResult, type Message, type Status, type Usage } from '../services/api'

const STORAGE_KEY = 'youtube-gatekeeper.conversation'

function savedConversation(): string | null {
  try { return localStorage.getItem(STORAGE_KEY) } catch { return null }
}

export function useGatekeeper() {
  const [status, setStatus] = useState<Status | null>(null)
  const [usage, setUsage] = useState<Usage | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [usageError, setUsageError] = useState<string | null>(null)
  const [chatError, setChatError] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [conversationId, setConversationId] = useState<string | null>(savedConversation)
  const [conversationClosed, setConversationClosed] = useState(false)
  const [loadingConversation, setLoadingConversation] = useState(Boolean(conversationId))
  const [sending, setSending] = useState(false)
  const [blocking, setBlocking] = useState(false)
  const [now, setNow] = useState(Date.now())
  const [serverOffset, setServerOffset] = useState(0)
  const pollInFlight = useRef(false)
  const sendInFlight = useRef(false)

  const refresh = useCallback(async () => {
    if (pollInFlight.current) return
    pollInFlight.current = true
    const [statusResult, usageResult] = await Promise.allSettled([
      request<Status>('/status'), request<Usage>('/usage'),
    ])
    if (statusResult.status === 'fulfilled') {
      setStatus(statusResult.value)
      setConnectionError(null)
      const serverNow = dateValue(statusResult.value.server_time)
      if (Number.isFinite(serverNow)) setServerOffset(serverNow - Date.now())
    } else {
      setConnectionError(statusResult.reason instanceof Error ? statusResult.reason.message : 'Local server unavailable.')
    }
    if (usageResult.status === 'fulfilled') {
      setUsage(usageResult.value)
      setUsageError(null)
    } else {
      setUsageError('Usage could not be loaded. Reconnect to the local server to refresh it.')
    }
    pollInFlight.current = false
  }, [])

  useEffect(() => {
    void refresh()
    const poll = window.setInterval(() => void refresh(), 5000)
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => { window.clearInterval(poll); window.clearInterval(timer) }
  }, [refresh])

  useEffect(() => {
    if (!conversationId) { setLoadingConversation(false); return }
    let cancelled = false
    request<{ messages: Message[]; status: string }>(`/conversations/${encodeURIComponent(conversationId)}`)
      .then(data => { if (!cancelled) { setMessages(data.messages.filter(message => message.role === 'user' || message.role === 'assistant')); setConversationClosed(data.status === 'closed') } })
      .catch(error => {
        if (cancelled) return
        if (error instanceof ApiError && error.status === 404) {
          setConversationId(null)
          try { localStorage.removeItem(STORAGE_KEY) } catch { /* Storage is optional. */ }
        } else setChatError(error instanceof Error ? error.message : 'Could not load your conversation.')
      })
      .finally(() => { if (!cancelled) setLoadingConversation(false) })
    return () => { cancelled = true }
  // Load the saved conversation once. New IDs are already represented by the chat response.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const sendMessage = useCallback(async (content: string): Promise<boolean> => {
    if (!content.trim() || sendInFlight.current || loadingConversation || conversationClosed) return false
    sendInFlight.current = true
    setSending(true)
    setChatError(null)
    const temporaryId = crypto.randomUUID()
    setMessages(previous => [...previous, { id: temporaryId, role: 'user', content, created_at: new Date().toISOString() }])
    try {
      const result = await request<ChatResult>('/chat', { message: content.trim(), ...(conversationId ? { conversation_id: conversationId } : {}) })
      setConversationId(result.conversation_id)
      setConversationClosed(result.decision !== 'continue_questioning')
      try { localStorage.setItem(STORAGE_KEY, result.conversation_id) } catch { /* Storage is optional. */ }
      setMessages(previous => [...previous, { id: crypto.randomUUID(), role: 'assistant', content: result.response, created_at: new Date().toISOString(), decision: result.decision, tool_events: result.tool_events }])
      // Only /status is authoritative for protection state and backend health.
      await refresh()
      return true
    } catch (error) {
      setMessages(previous => previous.filter(message => message.id !== temporaryId))
      if (error instanceof ApiError && error.status === 409) setConversationClosed(true)
      setChatError(error instanceof Error ? error.message : 'The Gatekeeper could not respond. Please try again.')
      await refresh()
      return false
    } finally {
      sendInFlight.current = false
      setSending(false)
    }
  }, [conversationId, conversationClosed, loadingConversation, refresh])

  const newConversation = useCallback(() => {
    if (sendInFlight.current) return
    setMessages([])
    setConversationId(null)
    setConversationClosed(false)
    setChatError(null)
    try { localStorage.removeItem(STORAGE_KEY) } catch { /* Storage is optional. */ }
  }, [])

  const block = useCallback(async () => {
    if (blocking || sendInFlight.current) return
    setBlocking(true)
    setChatError(null)
    try { await request('/admin/block', {}); await refresh() }
    catch (error) { setChatError(error instanceof Error ? error.message : 'Unable to block YouTube.'); await refresh() }
    finally { setBlocking(false) }
  }, [blocking, refresh])

  const secondsRemaining = status?.expires_at ? Math.max(0, Math.ceil((dateValue(status.expires_at) - now - serverOffset) / 1000)) : 0
  const expiredPending = Boolean(status && !status.blocked && status.expires_at && secondsRemaining === 0)
  const protection = connectionError || status?.error ? 'unknown' : !status ? 'connecting' : expiredPending ? 'pending' : status.blocked ? 'blocked' : 'unlocked'

  useEffect(() => { if (expiredPending) void refresh() }, [expiredPending, refresh])

  return { status, usage, connectionError, usageError, chatError, messages, conversationClosed, loadingConversation, sending, blocking, secondsRemaining, protection, refresh, sendMessage, newConversation, block }
}

export type GatekeeperState = ReturnType<typeof useGatekeeper>

export interface Session {
  id: string
  conversation_id: string
  reason: string
  started_at: string
  expires_at: string
  duration_minutes: number
  status: string
}

export interface Status {
  blocked: boolean
  expires_at: string | null
  session: Session | null
  error: string | null
  dry_run: boolean
  model: { name: string; available: boolean; error: string | null }
  limits: {
    min_session_minutes: number
    max_session_minutes: number
    daily_limit_minutes: number
    max_question_rounds: number
  }
  server_time: string
}

export interface Usage {
  today_minutes: number
  daily_limit_minutes: number
  remaining_minutes: number
  history: Session[]
  daily: { date: string; minutes: number }[]
}

export interface ToolEvent { name: string; status: string; detail: string }
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  decision?: 'continue_questioning' | 'deny' | 'grant'
  tool_events?: ToolEvent[]
}

export interface ChatResult {
  response: string
  decision: 'continue_questioning' | 'deny' | 'grant'
  conversation_id: string
  youtube_status: Partial<Status>
  tool_events?: ToolEvent[]
}

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}

export async function request<T>(path: string, body?: object): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), body ? 180_000 : 20_000)
  try {
    const response = await fetch(`/api${path}`, {
      method: body ? 'POST' : 'GET',
      headers: body ? { 'Content-Type': 'application/json', 'X-Gatekeeper-Request': '1' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
    const data = await response.json().catch(() => null)
    if (!response.ok) {
      const detail = data?.detail
      const message = typeof detail === 'string' ? detail : typeof detail?.message === 'string' ? detail.message : `The request failed (${response.status}). Please try again.`
      throw new ApiError(message, response.status)
    }
    return data as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('The local server took too long to respond. Check its status before trying again.')
    }
    throw new Error('Cannot reach the local server. Start the backend, then reconnect.')
  } finally {
    window.clearTimeout(timeout)
  }
}

export function dateValue(value: string): number {
  // Legacy timestamps without a timezone are stored as UTC by the backend.
  return Date.parse(/[zZ]$|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
}

export function minutes(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

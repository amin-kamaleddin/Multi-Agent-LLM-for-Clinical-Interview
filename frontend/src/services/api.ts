import type {
  ModuleInfo,
  CreateSessionRequest,
  CreateSessionResponse,
  AnswerResponse,
  NextResponse,
} from './types'

export const BASE_URL = import.meta.env.VITE_API_URL || ''

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || res.statusText)
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json() as Promise<T>
  // @ts-expect-error non-json
  return undefined
}

export const api = {
  async login(password: string) {
    return http<{ ok: boolean }>(`/auth/login`, {
      method: 'POST',
      body: JSON.stringify({ password }),
    })
  },

  async listModules(): Promise<ModuleInfo[]> {
    return http(`/modules`)
  },

  async createSession(payload: CreateSessionRequest): Promise<CreateSessionResponse> {
    return http(`/sessions`, { method: 'POST', body: JSON.stringify(payload) })
  },

  async submitAnswer(threadId: string, answer: string): Promise<AnswerResponse> {
    return http(`/sessions/${threadId}/answer`, { method: 'POST', body: JSON.stringify({ answer }) })
  },

  async goNext(threadId: string): Promise<NextResponse> {
    return http(`/sessions/${threadId}/next`, { method: 'POST' })
  },
}

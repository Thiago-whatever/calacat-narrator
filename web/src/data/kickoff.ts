import { useState } from 'react'
import type { Strings } from '../i18n'
import { MATCH_ID_PATTERN } from './live'

export type StartState =
  | { status: 'idle' | 'starting' | 'started' | 'joined' | 'daily_cap' | 'error' }
  | { status: 'busy'; retryMin: number }

/** Maps the `POST /api/matches` response (ADR-044) to what the console shows. */
export function readStartResponse(httpStatus: number, body: unknown): StartState & { matchId?: string } {
  const b = (typeof body === 'object' && body !== null ? body : {}) as Record<string, unknown>
  if (httpStatus === 202 && typeof b.match_id === 'string' && MATCH_ID_PATTERN.test(b.match_id)) {
    // "joined": a match was already live (or just started), so the server points us at it.
    return { status: b.status === 'joined' ? 'joined' : 'started', matchId: b.match_id }
  }
  if (httpStatus === 429 && b.error === 'daily_cap') return { status: 'daily_cap' }
  if (httpStatus === 429) {
    const seconds = typeof b.retry_after_s === 'number' && Number.isFinite(b.retry_after_s) ? b.retry_after_s : 60
    return { status: 'busy', retryMin: Math.max(1, Math.ceil(seconds / 60)) }
  }
  return { status: 'error' }
}

export function startMessage(t: Strings, state: StartState): string {
  switch (state.status) {
    case 'starting': return t.startingMatch
    case 'started': return t.matchStarted
    case 'joined': return t.matchJoined
    case 'busy': return t.matchesBusy.replace('{min}', String(state.retryMin))
    case 'daily_cap': return t.matchesDaily
    case 'error': return t.startFailed
    default: return ''
  }
}

/** The "Start live match" button: the server picks the seed and speed; on success the console follows the new match. */
export function useMatchStarter(apiBase: string, onStarted: (matchId: string) => void) {
  const [state, setState] = useState<StartState>({ status: 'idle' })
  const start = async () => {
    setState({ status: 'starting' })
    try {
      // No body and no custom headers: a simple CORS request, so no preflight.
      const res = await fetch(`${apiBase}/matches`, { method: 'POST', cache: 'no-store' })
      const result = readStartResponse(res.status, await res.json().catch(() => null))
      setState(result)
      if (result.matchId) onStarted(result.matchId)
    } catch {
      setState({ status: 'error' })
    }
  }
  return { state, start }
}

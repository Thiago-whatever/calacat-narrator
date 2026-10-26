import { useEffect, useMemo, useState } from 'react'
import type { Phase, Source } from '../types'
import { DEMO_FULL_TIME, demoCards, demoMatches, demoOutputs, demoPlayers, demoTeams } from './demo'

const TICK_MS = 300
const TICK_MATCH_SECONDS = 30

export type DemoRun = 'idle' | 'running' | 'paused' | 'finished'

/** Simulated match clock for the demo: 30 match-seconds every 300 ms, so 90 minutes take ~54 s. */
export function useDemoSource() {
  const [clock, setClock] = useState(0)
  const [requested, setRun] = useState<DemoRun>('idle')
  const run: DemoRun = requested === 'running' && clock >= DEMO_FULL_TIME ? 'finished' : requested

  useEffect(() => {
    if (run !== 'running') return
    const id = window.setInterval(() => setClock((c) => Math.min(c + TICK_MATCH_SECONDS, DEMO_FULL_TIME)), TICK_MS)
    return () => window.clearInterval(id)
  }, [run])

  const toggle = () => {
    if (run === 'running') return setRun('paused')
    if (run === 'finished') setClock(0)
    setRun('running')
  }

  const source = useMemo<Source>(() => {
    const phase: Phase = run === 'idle' ? 'pre' : run === 'finished' ? 'ft' : clock <= 2700 ? 'h1' : 'h2'
    return {
      teams: demoTeams,
      players: demoPlayers,
      matches: demoMatches,
      outputs: demoOutputs,
      cards: demoCards.filter((c) => c.clock <= clock),
      clock,
      phase,
    }
  }, [clock, run])

  return { source, run, toggle }
}

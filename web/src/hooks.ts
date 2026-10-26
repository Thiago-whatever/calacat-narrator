import { useEffect, useRef, useState, type PointerEvent, type RefObject } from 'react'
import type { CardDragHandlers } from './components/feed/FeedCard'
import type { ThemePrefs } from './theme/theme'
import type { Lang } from './types'

const PREFS_KEY = 'calacat.reporter.prefs'

interface Stored {
  lang: Lang
  prefs: ThemePrefs
}

// Per-viewer conveniences only; storage can be unavailable (private mode), so every access is guarded.
function loadStored(): Stored {
  const fallback: Stored = {
    lang: navigator.language.startsWith('es') ? 'es' : 'en',
    prefs: { highContrast: false, largeText: false, reduceMotion: false },
  }
  try {
    const raw = JSON.parse(localStorage.getItem(PREFS_KEY) ?? 'null') as Partial<Stored> | null
    const p: Partial<ThemePrefs> = raw?.prefs ?? {}
    return {
      lang: raw?.lang === 'es' || raw?.lang === 'en' ? raw.lang : fallback.lang,
      prefs: {
        highContrast: p.highContrast === true,
        largeText: p.largeText === true,
        reduceMotion: p.reduceMotion === true,
      },
    }
  } catch {
    return fallback
  }
}

/** Language and accessibility preferences, remembered per browser. */
export function usePrefs() {
  const [stored] = useState(loadStored)
  const [lang, setLang] = useState<Lang>(stored.lang)
  const [prefs, setPrefs] = useState<ThemePrefs>(stored.prefs)
  useEffect(() => {
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify({ lang, prefs }))
    } catch {
      // Storage unavailable: preferences just won't persist.
    }
  }, [lang, prefs])
  return { lang, setLang, prefs, setPrefs }
}

/** Re-renders every `ms` while `active`, for the countdown and the on-air timer. */
export function useNow(ms: number, active: boolean) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const id = window.setInterval(() => setNow(Date.now()), ms)
    return () => window.clearInterval(id)
  }, [ms, active])
  return now
}

export interface FeedDrag {
  id: string
  x: number
  y: number
  over: boolean
}

interface FeedDragOptions {
  target: RefObject<HTMLElement | null>
  /** Return false to refuse a drag (countdown running, card locked). */
  canDrag: (id: string) => boolean
  /** Drop point as percentages of the target. */
  onDrop: (id: string, xPct: number, yPct: number) => void
}

const DRAG_THRESHOLD_PX = 6

/**
 * Drag from the feed onto the monitor: a press only becomes a drag after it moves, and the click that
 * follows a drag is suppressed so it doesn't also toggle the selection.
 */
export function useFeedDrag({ target, canDrag, onDrop }: FeedDragOptions) {
  const [drag, setDrag] = useState<FeedDrag | null>(null)
  const press = useRef<{ id: string; x0: number; y0: number; moved: boolean } | null>(null)
  const suppressClick = useRef(false)

  const over = (x: number, y: number) => {
    const r = target.current?.getBoundingClientRect()
    return !!r && x >= r.left && x <= r.right && y >= r.top && y <= r.bottom
  }

  const handlers: CardDragHandlers = {
    down: (e: PointerEvent<HTMLButtonElement>, id: string) => {
      if (e.button !== 0 || !canDrag(id)) return
      press.current = { id, x0: e.clientX, y0: e.clientY, moved: false }
      e.currentTarget.setPointerCapture(e.pointerId)
    },
    move: (e: PointerEvent<HTMLButtonElement>) => {
      const p = press.current
      if (!p) return
      if (!p.moved && Math.hypot(e.clientX - p.x0, e.clientY - p.y0) < DRAG_THRESHOLD_PX) return
      p.moved = true
      setDrag({ id: p.id, x: e.clientX, y: e.clientY, over: over(e.clientX, e.clientY) })
    },
    up: (e: PointerEvent<HTMLButtonElement>) => {
      const p = press.current
      press.current = null
      setDrag(null)
      if (!p?.moved) return
      suppressClick.current = true
      window.setTimeout(() => { suppressClick.current = false }, 0)
      const r = target.current?.getBoundingClientRect()
      if (r && over(e.clientX, e.clientY)) onDrop(p.id, ((e.clientX - r.left) / r.width) * 100, ((e.clientY - r.top) / r.height) * 100)
    },
    cancel: () => {
      press.current = null
      setDrag(null)
    },
  }

  return { drag, handlers, isClickSuppressed: () => suppressClick.current }
}

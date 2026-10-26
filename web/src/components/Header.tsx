import { useEffect, useRef } from 'react'
import type { Strings } from '../i18n'
import type { Lang } from '../types'

export interface Prefs {
  hc: boolean
  lg: boolean
  rm: boolean
}

export interface OutputButton {
  id: string
  name: string
  score: string
  live: boolean
  pressed: boolean
  disabled: boolean
}

interface Props {
  t: Strings
  lang: Lang
  onLang: (lang: Lang) => void
  prefs: Prefs
  onPrefs: (prefs: Prefs) => void
  a11yOpen: boolean
  onA11yOpen: (open: boolean) => void
  /** Demo only: Start / Pause / Resume / Restart drives the simulated clock. Omitted in live mode. */
  run?: { label: string; running: boolean; onToggle: () => void }
  liveStatus?: string
  outputs: OutputButton[]
  onOutput: (id: string) => void
  period: string
}

export function Header({ t, lang, onLang, prefs, onPrefs, a11yOpen, onA11yOpen, run, liveStatus, outputs, onOutput, period }: Props) {
  const popRef = useRef<HTMLDivElement>(null)

  // Close the accessibility popover on an outside click.
  useEffect(() => {
    if (!a11yOpen) return
    const onDown = (e: PointerEvent) => {
      if (!popRef.current?.contains(e.target as Node)) onA11yOpen(false)
    }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [a11yOpen, onA11yOpen])

  return (
    <header className="hdr">
      <div className="brand">
        <span className="logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round">
            <path d="M5 19.5V8.5L7.5 4l3.2 3.5h2.6L16.5 4 19 8.5v11z" /><path d="M9.5 13h.01M14.5 13h.01" />
          </svg>
        </span>
        <div>
          <h1 className="disp brand-name">Calacat Narrator</h1>
          <div className="brand-sub">{t.sub}</div>
        </div>
      </div>

      <div className="outs" role="group" aria-labelledby="out-l">
        <span className="lbl" id="out-l">{t.output}</span>
        {outputs.map((o) => (
          <button key={o.id} type="button" className="out" aria-pressed={o.pressed} disabled={o.disabled} onClick={() => onOutput(o.id)}>
            <span className={`dot${o.live ? ' live' : ''}`} aria-hidden="true" />
            <span className="on">{o.name}</span>
            <span className="os">{o.score}</span>
            <span className="sr">{o.live ? t.outLive : t.outOff}</span>
          </button>
        ))}
        <span className="pill">{period}</span>
        {liveStatus && <span className="pill" role="status">{liveStatus}</span>}
      </div>

      <div className="row tools">
        {run && (
          <button type="button" className="btn primary run" onClick={run.onToggle}>
            <svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
              <path d={run.running ? 'M6 5h4v14H6zM14 5h4v14h-4z' : 'M7 4.5v15l12-7.5z'} />
            </svg>
            <span>{run.label}</span>
          </button>
        )}
        <label className="sr" htmlFor="lang-select">{t.lang}</label>
        <span className="selwrap">
          <select id="lang-select" className="btn" value={lang} onChange={(e) => onLang(e.target.value as Lang)}>
            <option value="en">English</option>
            <option value="es">Español</option>
          </select>
          <Chevron />
        </span>
        <div className="a11y" ref={popRef}>
          <button type="button" className="btn" aria-expanded={a11yOpen} aria-controls="a11y-panel" onClick={() => onA11yOpen(!a11yOpen)}>
            <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="4.5" r="1.8" /><path d="M5 8.5l7 1.6 7-1.6M12 10.1v4.9m0 0l-3.2 6m3.2-6l3.2 6" />
            </svg>
            <span>{t.a11y}</span>
          </button>
          {a11yOpen && (
            <div id="a11y-panel" className="panel pop" role="group" aria-label={t.a11y}>
              {(['hc', 'lg', 'rm'] as const).map((k) => (
                <label key={k} className="chk">
                  <input type="checkbox" checked={prefs[k]} onChange={(e) => onPrefs({ ...prefs, [k]: e.target.checked })} />
                  {t[k]}
                </label>
              ))}
              <p className="kbd">{t.shortcuts}</p>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

export function Chevron() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 6l4 4 4-4" />
    </svg>
  )
}

import type { Strings } from '../i18n'
import { SIZES } from '../state'

interface Props {
  t: Strings
  title: string
  sub: string
  mode: 'idle' | 'ready' | 'pending' | 'air'
  countdown: number
  width: number
  fixedHeight: boolean
  canEdit: boolean
  canSend: boolean
  canPull: boolean
  liveLabel: string
  onSize: (width: number) => void
  onSend: () => void
  onPull: () => void
  onGoNow: () => void
  onCancel: () => void
}

/** Always directly under the monitor. During the countdown, Go live / Pull become Go live now / Cancel (ADR-033). */
export function ControlBar(p: Props) {
  const { t } = p
  const pending = p.mode === 'pending'
  const barCls = pending ? ' pend' : p.mode === 'air' ? ' air' : ''
  return (
    <div className={`bar${barCls}`} role="region" aria-label={t.control}>
      <div className="status">
        {pending ? (
          <span className="cd disp" aria-hidden="true">{p.countdown}</span>
        ) : (
          <span className={`lamp${p.mode === 'air' ? ' air' : p.mode === 'ready' ? ' ready' : ''}`} aria-hidden="true" />
        )}
        <div className="status-text">
          <div className="tt">{p.title}</div>
          <div className="sub">{p.sub}</div>
        </div>
      </div>

      {pending ? (
        <>
          <div className="actions">
            <button type="button" className="btn xl outline" onClick={p.onGoNow}>{t.goNow}</button>
            <button type="button" className="btn xl solid" onClick={p.onCancel}>
              <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 14L4 9l5-5" /><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" />
              </svg>
              <span>{t.cancel}</span><kbd className="key">Esc</kbd>
            </button>
          </div>
          <span className="prog" aria-hidden="true" />
        </>
      ) : (
        <div className="actions">
          <div className="sizegrp">
            <span className="lbl" id="size-l">{t.size}</span>
            <div className="seg" role="group" aria-labelledby="size-l">
              {SIZES.map((z) => (
                <button
                  key={z.width}
                  type="button"
                  aria-pressed={p.width === z.width && !p.fixedHeight}
                  aria-label={t[z.key]}
                  disabled={!p.canEdit}
                  onClick={() => p.onSize(z.width)}
                >
                  {z.label}
                </button>
              ))}
            </div>
          </div>
          <button type="button" className="btn xl outline" disabled={!p.canPull} onClick={p.onPull}>
            <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><rect x="5" y="5" width="14" height="14" rx="2.5" /></svg>
            <span>{t.pull}</span>
          </button>
          <button type="button" className="btn xl primary" disabled={!p.canSend} onClick={p.onSend}>
            <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="2.5" fill="currentColor" /><path d="M7.5 7.5a6.4 6.4 0 0 0 0 9M16.5 7.5a6.4 6.4 0 0 1 0 9" />
            </svg>
            <span>{p.liveLabel}</span><kbd className="key">Enter</kbd>
          </button>
        </div>
      )}
    </div>
  )
}

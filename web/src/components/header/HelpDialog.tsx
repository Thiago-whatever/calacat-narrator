import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Tooltip, Typography } from '@mui/material'
import { useId, useState } from 'react'
import type { Strings } from '../../i18n'
import { InfoIcon } from '../ui/icons'

const WELCOMED_KEY = 'calacat.reporter.welcomed'

// Opens by itself on a first visit only; storage can be unavailable (private mode), so every access is guarded.
function firstVisit(): boolean {
  try {
    return localStorage.getItem(WELCOMED_KEY) !== '1'
  } catch {
    return false
  }
}

interface Props {
  t: Strings
  /** Label of the demo button, when it is shown. */
  demo?: string
  /** Label of the live-match button, when it is shown. */
  live?: string
  /** Label of the go-live button for the selected output, e.g. "Go live on TV 1". */
  goLive: string
  overlay: string
}

const fill = (text: string, label: string) => text.replace(/\{\w+\}/, `“${label}”`)

/** "How it works": demo versus live match, and the steps to put a card on air. Esc or Got it closes it. */
export function HelpDialog({ t, demo, live, goLive, overlay }: Props) {
  const [open, setOpen] = useState(firstVisit)
  const titleId = useId()
  const close = () => {
    setOpen(false)
    try {
      localStorage.setItem(WELCOMED_KEY, '1')
    } catch {
      // Storage unavailable: it opens again next visit.
    }
  }
  const section = { fontWeight: 700, mt: 2, mb: '4px' }
  return (
    <>
      {/* Icon only: the name lives in aria-label and the tooltip. */}
      <Tooltip title={t.help}>
        <Button
          aria-label={t.help}
          aria-haspopup="dialog"
          onClick={() => setOpen(true)}
          sx={(theme) => ({ minWidth: theme.custom.sizes.target, width: theme.custom.sizes.target, px: 0 })}
        >
          <InfoIcon />
        </Button>
      </Tooltip>
      <Dialog open={open} onClose={close} aria-labelledby={titleId} maxWidth="sm" fullWidth>
        <DialogTitle id={titleId} variant="display" sx={{ fontSize: '1.6em' }}>{t.helpTitle}</DialogTitle>
        <DialogContent>
          <Typography>{t.helpIntro}</Typography>
          {demo && (
            <>
              <Typography component="h3" sx={section}>{t.helpDemoTitle}</Typography>
              <Typography>{fill(t.helpDemo, demo)}</Typography>
            </>
          )}
          {live && (
            <>
              <Typography component="h3" sx={section}>{t.helpLiveTitle}</Typography>
              <Typography>{fill(t.helpLive, live)}</Typography>
            </>
          )}
          <Typography component="h3" sx={section}>{t.helpStepsTitle}</Typography>
          <Box component="ol" sx={{ m: 0, pl: 3, '& li + li': { mt: '4px' } }}>
            <li>{t.helpStep1}</li>
            <li>{t.helpStep2}</li>
            <li>{fill(t.helpStep3, goLive)}</li>
            <li>{fill(t.helpStep4, overlay)}</li>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button variant="contained" onClick={close}>{t.helpDone}</Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

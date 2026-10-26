import { Button, Checkbox, FormControlLabel, FormGroup, Popover, Typography } from '@mui/material'
import { useId, useState } from 'react'
import type { ThemePrefs } from '../../theme/theme'
import { AccessibilityIcon } from '../ui/icons'

interface Props {
  label: string
  options: Record<keyof ThemePrefs, string>
  shortcuts: string
  prefs: ThemePrefs
  onChange: (prefs: ThemePrefs) => void
}

/** Popover with high contrast, larger text and reduce motion, plus the shortcut list. Esc and outside click close it. */
export function AccessibilityMenu({ label, options, shortcuts, prefs, onChange }: Props) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const open = !!anchor
  const panelId = useId()
  return (
    <>
      <Button aria-expanded={open} aria-controls={panelId} onClick={(e) => setAnchor(open ? null : e.currentTarget)} startIcon={<AccessibilityIcon />} sx={{ width: { xs: '100%', sm: 'auto' } }}>
        {label}
      </Button>
      <Popover
        open={open}
        anchorEl={anchor}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { id: panelId, role: 'group', 'aria-label': label, sx: { mt: 1, maxWidth: 'calc(100vw - 32px)' } } }}
      >
        <FormGroup>
          {(Object.keys(options) as (keyof ThemePrefs)[]).map((key) => (
            <FormControlLabel
              key={key}
              control={<Checkbox checked={prefs[key]} onChange={(e) => onChange({ ...prefs, [key]: e.target.checked })} />}
              label={options[key]}
            />
          ))}
        </FormGroup>
        <Typography variant="hint" sx={{ mt: '6px' }}>{shortcuts}</Typography>
      </Popover>
    </>
  )
}

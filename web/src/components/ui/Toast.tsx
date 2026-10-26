import { Box, Snackbar } from '@mui/material'
import type { ReactNode } from 'react'
import { CheckIcon } from './icons'

interface Props {
  open: boolean
  title: string
  detail?: string
  action?: ReactNode
  onClose: () => void
  /** Auto-hide delay in ms. */
  duration: number
}

/** Success toast, bottom-right; announced through role="status". */
export function Toast({ open, title, detail, action, onClose, duration }: Props) {
  return (
    <Snackbar
      open={open}
      onClose={(_, reason) => reason !== 'clickaway' && onClose()}
      autoHideDuration={duration}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      sx={{ width: 'min(400px, calc(100% - 32px))' }}
      message={
        <>
          <Box
            component="span"
            aria-hidden
            sx={(theme) => ({ width: 36, height: 36, borderRadius: '50%', background: theme.custom.colors.live, display: 'grid', placeItems: 'center', flex: 'none' })}
          >
            <CheckIcon sx={{ width: 20, height: 20 }} />
          </Box>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box sx={{ fontWeight: 700 }}>{title}</Box>
            {detail && <Box sx={{ fontSize: '.88em', opacity: 0.85, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{detail}</Box>}
          </Box>
        </>
      }
      action={action}
      slotProps={{
        content: {
          role: 'status',
          sx: (theme) => ({
            width: '100%',
            // Action buttons sit on the dark toast: outlined in the toast's own text color.
            '& .MuiSnackbarContent-action .MuiButton-root': {
              background: 'transparent', color: 'inherit', borderColor: 'currentColor',
              '&:hover': { background: 'transparent', borderColor: theme.custom.colors.onBrand },
            },
          }),
        },
      }}
    />
  )
}

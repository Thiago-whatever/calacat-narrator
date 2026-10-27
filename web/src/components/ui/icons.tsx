import { SvgIcon, type SvgIconProps } from '@mui/material'

// One icon set for the console. Icons are decorative (aria-hidden) and inherit currentColor.

function strokeIcon(paths: string[], width = 2, viewBox = '0 0 24 24') {
  return function StrokeIcon(props: SvgIconProps) {
    return (
      <SvgIcon aria-hidden viewBox={viewBox} {...props} sx={{ fill: 'none', stroke: 'currentColor', strokeWidth: width, strokeLinecap: 'round', strokeLinejoin: 'round', ...props.sx }}>
        {paths.map((d) => <path key={d} d={d} />)}
      </SvgIcon>
    )
  }
}

function fillIcon(d: string) {
  return function FillIcon(props: SvgIconProps) {
    return <SvgIcon aria-hidden {...props}><path d={d} /></SvgIcon>
  }
}

export const PlayIcon = fillIcon('M7 4.5v15l12-7.5z')
export const PauseIcon = fillIcon('M6 5h4v14H6zM14 5h4v14h-4z')
export const ChevronIcon = strokeIcon(['M4 6l4 4 4-4'], 2, '0 0 16 16')
export const CloseIcon = strokeIcon(['M4 4l8 8M12 4l-8 8'], 2.4, '0 0 16 16')
export const MoveIcon = strokeIcon(['M8 1.5v13M1.5 8h13M5.5 4L8 1.5 10.5 4M5.5 12L8 14.5l2.5-2.5M4 5.5L1.5 8 4 10.5M12 5.5L14.5 8 12 10.5'], 2, '0 0 16 16')
export const AccessibilityIcon = strokeIcon(['M5 8.5l7 1.6 7-1.6M12 10.1v4.9m0 0l-3.2 6m3.2-6l3.2 6', 'M12 2.7a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6z'], 1.8)
export const StopIcon = strokeIcon(['M7.5 5h9A2.5 2.5 0 0 1 19 7.5v9a2.5 2.5 0 0 1-2.5 2.5h-9A2.5 2.5 0 0 1 5 16.5v-9A2.5 2.5 0 0 1 7.5 5z'], 2.2)
export const BroadcastIcon = strokeIcon(['M7.5 7.5a6.4 6.4 0 0 0 0 9M16.5 7.5a6.4 6.4 0 0 1 0 9', 'M12 9.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5z'])
export const UndoIcon = strokeIcon(['M9 14L4 9l5-5', 'M4 9h10.5a5.5 5.5 0 0 1 0 11H11'], 2.2)
export const InfoIcon = strokeIcon(['M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18z', 'M12 11v5.5M12 7.5h.01'], 2)
export const CheckIcon = strokeIcon(['M5 12.5l4.5 4.5L19 7.5'], 2.6)
export const LogoIcon = strokeIcon(['M5 19.5V8.5L7.5 4l3.2 3.5h2.6L16.5 4 19 8.5v11z', 'M9.5 13h.01M14.5 13h.01'], 1.8)

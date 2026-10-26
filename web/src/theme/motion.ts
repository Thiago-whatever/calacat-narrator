import { keyframes } from '@emotion/react'

// All animations live here; reduce motion (toggle or OS setting) removes them globally (see GlobalStyles).
export const blink = keyframes`50% { opacity: .25; }`
export const pop = keyframes`from { opacity: 0; transform: translateY(-12px) scale(.98); } to { opacity: 1; transform: none; }`
export const rise = keyframes`from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; }`
export const emit = keyframes`0% { opacity: .9; inset: -.3cqw; } 100% { opacity: 0; inset: -2.6cqw; }`
export const drain = keyframes`from { width: 100%; } to { width: 0; }`

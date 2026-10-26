import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Self-hosted fonts: no runtime third-party request, and the CSP can stay 'self'.
import '@fontsource/antonio/600.css'
import '@fontsource/antonio/700.css'
import '@fontsource/instrument-sans/400.css'
import '@fontsource/instrument-sans/500.css'
import '@fontsource/instrument-sans/600.css'
import '@fontsource/instrument-sans/700.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

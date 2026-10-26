/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Function API base: `/api` behind the Static Web Apps linked backend (ADR-036). */
  readonly VITE_API_BASE_URL?: string
}

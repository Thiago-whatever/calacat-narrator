/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Function API base, e.g. https://<function-app-host>/api from a repository variable (ADR-043). */
  readonly VITE_API_BASE_URL?: string
}

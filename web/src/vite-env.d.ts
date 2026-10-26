/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Function App origin serving GET /negotiate, e.g. https://fn-calacat.azurewebsites.net */
  readonly VITE_API_BASE_URL?: string
}

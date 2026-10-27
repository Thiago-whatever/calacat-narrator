import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// GitHub Pages serves this repo's site under /calacat-narrator/ (ADR-043).
const PAGES_BASE = '/calacat-narrator/'

/** Origin of the API for the CSP's connect-src; empty for same-origin or demo-only builds. */
function apiOrigin(apiBaseUrl: string | undefined): string {
  try {
    return apiBaseUrl ? new URL(apiBaseUrl).origin : ''
  } catch {
    return '' // a relative URL such as /api is same-origin
  }
}

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Dev only: forward /api to a deployed Function App so a local console talks to Azure same-origin (no CORS).
  const proxyTarget = env.API_PROXY_TARGET
  // Pages can only set security headers through <meta>; frame-ancestors is not expressible there (ADR-043).
  const csp = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'", // Emotion (MUI) injects <style> tags at runtime
    "font-src 'self'",
    "img-src 'self' data:",
    ['connect-src', "'self'", apiOrigin(env.VITE_API_BASE_URL), 'wss://*.webpubsub.azure.com'].filter(Boolean).join(' '),
    "base-uri 'self'",
    "form-action 'none'",
    "object-src 'none'",
  ].join('; ')

  return {
    base: command === 'build' ? PAGES_BASE : '/',
    plugins: [
      react(),
      {
        // Build only: the dev server needs an inline React refresh preamble that this CSP would block.
        name: 'content-security-policy',
        apply: 'build',
        transformIndexHtml: () => [
          { tag: 'meta', attrs: { 'http-equiv': 'Content-Security-Policy', content: csp }, injectTo: 'head-prepend' },
        ],
      },
    ],
    server: {
      // The live feed reuses the backend's packaged team/player catalog as its single source of truth.
      fs: { allow: ['.', '../src/calacat_narrator/data'] },
      proxy: proxyTarget ? { '/api': { target: proxyTarget, changeOrigin: true } } : undefined,
    },
    build: {
      rolldownOptions: {
        output: {
          // Framework code changes rarely; a separate chunk keeps it cached across app deploys.
          codeSplitting: {
            groups: [
              { name: 'react', test: /node_modules[\\/](react|react-dom|scheduler)[\\/]/ },
              { name: 'mui', test: /node_modules[\\/](@mui|@emotion|@babel[\\/]runtime|stylis|react-transition-group|@popperjs|clsx|prop-types|react-is|hoist-non-react-statics)[\\/]/ },
            ],
          },
        },
      },
    },
  }
})

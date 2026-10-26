import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  // Dev only: forward /api to a deployed Function App so a local console talks to Azure same-origin (no CORS).
  const proxyTarget = loadEnv(mode, process.cwd(), '').API_PROXY_TARGET

  return {
    plugins: [react()],
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

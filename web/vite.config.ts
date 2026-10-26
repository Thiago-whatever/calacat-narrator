import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  // The live feed reuses the backend's packaged team/player catalog as its single source of truth.
  server: { fs: { allow: ['.', '../src/calacat_narrator/data'] } },
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
})

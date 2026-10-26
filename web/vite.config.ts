import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  // The live feed reuses the backend's packaged team/player catalog as its single source of truth.
  server: { fs: { allow: ['.', '../src/calacat_narrator/data'] } },
})

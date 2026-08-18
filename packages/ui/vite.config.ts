import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxies /api to the local FastAPI server (packages/server) so the
// browser only ever talks to one origin — matching the plan's
// local-first, no-external-network posture (docs/plan §1 platform note).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})

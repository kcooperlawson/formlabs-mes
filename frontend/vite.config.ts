import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Proxies /api to the FastAPI backend (see api/main.py) so the browser only
// ever talks to one origin (:5173) during development - no CORS headers
// needed anywhere, and cookies behave exactly as they will in production,
// where FastAPI serves this app's own build output from the same origin.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// Proxies /api to the FastAPI backend (see api/main.py) so the browser only
// ever talks to one origin (:5173) during development - no CORS headers
// needed anywhere, and cookies behave exactly as they will in production,
// where FastAPI serves this app's own build output from the same origin.
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // Precaches the built app shell (JS/CSS/index.html) so the page still
    // loads with no signal at all - offline/queue.ts covers writes made
    // once it's open, this covers opening it in the first place. manifest:
    // false because index.html already links a hand-written
    // manifest.webmanifest (name/icons/theme-color); this only adds the
    // service worker half of "installable," not a second manifest.
    VitePWA({
      manifest: false,
      registerType: 'autoUpdate',
      workbox: {
        // vite-plugin-pwa registers a Workbox NavigationRoute by default so
        // a hard refresh or a bookmark on a client-side route (e.g. /tv)
        // still boots index.html and lets React Router take it from there -
        // needed, and left alone. Its blind spot: EVERY top-level navigation
        // matches that route by default, PDF links included, so opening the
        // Handbook/Operator Guide/Update Guide (plain <a target="_blank">
        // links, a real navigation, not a fetch) served the app shell
        // instead of the PDF - invisible on desktop where the file just
        // opened in the same tab underneath, but on a phone that "opened"
        // tab is the one this fallback hijacks, landing back on whatever
        // the app's default view is instead of the document. PDFs (there's
        // no client-side route that would ever end in .pdf) are excluded so
        // the navigation reaches the real file.
        navigateFallbackDenylist: [/\.pdf$/],
        // GET only, and never /api or /ws - a cached POST response or a
        // stale reference lookup served instead of a live one would be
        // actively wrong, not just unavailable. NetworkFirst rather than
        // CacheFirst for the reference data: same-shift changes (a resin
        // spec edited in IT Admin) should win the moment there's a
        // connection, with the cache only as the last resort.
        runtimeCaching: [
          {
            urlPattern: ({ url, request }) =>
              request.method === 'GET' && url.pathname.startsWith('/api/reference/'),
            handler: 'NetworkFirst',
            options: { cacheName: 'mes-reference-data', networkTimeoutSeconds: 4 },
          },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // useRealtimeInvalidate's WebSocket (api/main.py's /ws/updates) -
      // needs its own entry since Vite doesn't upgrade a plain proxy
      // connection unless told to.
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})

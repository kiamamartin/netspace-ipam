import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies API calls to the FastAPI backend (see backend/.env for the
// port). Override the target with NETSPACE_BACKEND_URL when running the API on
// another port (e.g. when :8000 is taken).
const backendUrl = process.env.NETSPACE_BACKEND_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: backendUrl, changeOrigin: true },
      '/health': { target: backendUrl, changeOrigin: true },
    },
  },
})

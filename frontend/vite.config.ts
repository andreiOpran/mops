import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In Docker Compose the backend is reachable as http://backend:8000.
const backendUrl = process.env.BACKEND_URL ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    proxy: {
      '/api': backendUrl,
    },
  },
})

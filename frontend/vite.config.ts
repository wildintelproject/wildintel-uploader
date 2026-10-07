import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // The wizard's long walks take a few seconds each when every test file runs at once.
    testTimeout: 20000,
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8769',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', (_err, _req, res) => {
            const r = res as import('http').ServerResponse
            r.writeHead(503, { 'Content-Type': 'application/json' })
            r.end(JSON.stringify({ detail: 'Backend not available on port 8769. Is the server running?' }))
          })
        },
      },
    },
  },
})

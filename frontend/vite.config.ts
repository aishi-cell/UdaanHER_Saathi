import path from 'node:path';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    // Same-origin API: with VITE_API_BASE_URL='' the frontend fetches
    // relative /api and /health, and the dev server forwards them to the
    // backend. One public tunnel URL then serves the whole app.
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
    // Cloudflare quick tunnels (share-the-demo links) present their own
    // Host header; Vite rejects unknown hosts by default.
    allowedHosts: ['.trycloudflare.com'],
  },
});

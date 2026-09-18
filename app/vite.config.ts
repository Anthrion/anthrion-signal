import { defineConfig } from 'vite'
import type { Plugin } from 'vite'
import react from '@vitejs/plugin-react'

// Pages cannot send headers, so the shipped page carries its own policy. Everything
// the dashboard needs is same-origin; inline styles are React's, never page markup.
const POLICY = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "base-uri 'none'",
  "form-action 'none'",
  "object-src 'none'",
  // No frame-ancestors: browsers honour it only as a header, which Pages cannot send.
].join('; ')

// Build only: the dev server needs its own websocket and inline module preamble.
const contentSecurityPolicy: Plugin = {
  name: 'anthrion-content-security-policy',
  apply: 'build',
  transformIndexHtml: () => [
    {
      tag: 'meta',
      attrs: { 'http-equiv': 'Content-Security-Policy', content: POLICY },
      injectTo: 'head-prepend',
    },
  ],
}

export default defineConfig({
  plugins: [react(), contentSecurityPolicy],
  base: process.env.VITE_BASE_PATH || '/anthrion-signal/',
  // Data is polled by the app. Watching individual JSON files prevents atomic replacement on Windows.
  server: { watch: { ignored: ['**/public/data/**'] } },
  build: { chunkSizeWarningLimit: 600 },
})

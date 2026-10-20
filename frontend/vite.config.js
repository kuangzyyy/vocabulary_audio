import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    // Expose the dev server on the local network so a phone on the same Wi-Fi
    // can open it. The API is still proxied to the PC-local backend below.
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
});

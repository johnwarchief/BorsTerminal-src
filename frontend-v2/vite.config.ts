import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';

const backend = process.env.BORS_BACKEND || process.env.BORS_BACKEND_GO || 'http://127.0.0.1:8198';
// borsd یک توکنِ per-launch می‌خواهد. در dev، همان مقدار را به هر دو پروسه
// بدهید تا پروکسی آن را به‌عنوان Bearer بفرستد؛ در نصبِ واقعی SPA کوکی می‌گیرد.
const apiToken = process.env.BORS_API_TOKEN || '';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@app': fileURLToPath(new URL('./src/app', import.meta.url)),
      '@shared': fileURLToPath(new URL('./src/shared', import.meta.url)),
      '@features': fileURLToPath(new URL('./src/features', import.meta.url)),
    },
  },
  server: {
    port: Number(process.env.BORS_VITE_PORT) || 5180,
    strictPort: true,
    proxy: {
      '/api': {
        target: backend,
        // Host باید 127.0.0.1:<port> باشد؛ guard هر Host غیرِ loopback را رد می‌کند.
        changeOrigin: true,
        headers: apiToken ? { Authorization: `Bearer ${apiToken}` } : undefined,
      },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
});

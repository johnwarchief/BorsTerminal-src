import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';

const backend = process.env.BORS_BACKEND || 'http://127.0.0.1:8101';
const backendGo = process.env.BORS_BACKEND_GO;
// مسیرهایِ تازهٔ مهاجرت (Go) می‌توانند جدا از بک‌اندِ پایتون پروکسی شوند؛
// کلیدهایِ خاص باید پیش از '/api' بیایند. بی‌تنظیم‌بودنِ BORS_BACKEND_GO یعنی
// همان رفتارِ تک‌بک‌اندیِ قبلی.
const goProxy: Record<string, { target: string; changeOrigin: boolean }> = backendGo ? {
  '/api/fundamental': { target: backendGo, changeOrigin: false },
  '/api/screener': { target: backendGo, changeOrigin: false },
  '/api/market': { target: backendGo, changeOrigin: false },
  '/api/sync/codal': { target: backendGo, changeOrigin: false },
} : {};

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
      ...goProxy,
      '/api': { target: backend, changeOrigin: false },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
});

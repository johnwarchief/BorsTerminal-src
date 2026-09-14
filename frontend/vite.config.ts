import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

const root = import.meta.dirname;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // فاز 7: SPA از ریشه سرو می‌شود (app.py mount /)؛ base دیگر /app/ نیست
  base: '/',
  resolve: {
    alias: {
      '@contracts': path.resolve(root, 'src/contracts'),
      '@shared': path.resolve(root, 'src/shared'),
      '@app': path.resolve(root, 'src/app'),
      '@features': path.resolve(root, 'src/features'),
      '@widgets': path.resolve(root, 'src/widgets'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8012',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});

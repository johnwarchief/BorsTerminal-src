import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

const root = import.meta.dirname;

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@contracts': path.resolve(root, 'src/contracts'),
      '@shared': path.resolve(root, 'src/shared'),
      '@app': path.resolve(root, 'src/app'),
      '@features': path.resolve(root, 'src/features'),
      '@widgets': path.resolve(root, 'src/widgets'),
      '@vendor': path.resolve(root, 'src/vendor'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/__tests__/setup.ts'],
    // تجمیع کندل و فرمتِ جلالی بر اساسِ UTC ساخته شده‌اند؛ بدونِ پین‌کردنِ
    // منطقهٔ زمانی، نتایجِ تست به منطقهٔ زمانیِ ماشینِ اجرا بستگی می‌کرد.
    env: { TZ: 'Asia/Tehran' },
  },
});

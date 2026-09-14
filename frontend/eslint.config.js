import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import boundaries from 'eslint-plugin-boundaries';
import globals from 'globals';

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      globals: { ...globals.browser },
    },
    plugins: {
      boundaries,
    },
    settings: {
      'boundaries/include': ['src/app', 'src/shared', 'src/contracts', 'src/widgets', 'src/features'],
      'boundaries/elements': [
        { type: 'app', pattern: 'src/app/**' },
        { type: 'shared', pattern: 'src/shared/**' },
        { type: 'contracts', pattern: 'src/contracts/**' },
        { type: 'widgets', pattern: 'src/widgets/**' },
        { type: 'market', pattern: 'src/features/market/**' },
        { type: 'fundamental', pattern: 'src/features/fundamental/**' },
        { type: 'technical', pattern: 'src/features/technical/**' },
        { type: 'portfolio', pattern: 'src/features/portfolio/**' },
        { type: 'master', pattern: 'src/features/master/**' },
      ],
    },
    rules: {
      // B1: هیچ فیچری از فیچر دیگر import نمی‌کند
      'boundaries/element-types': [
        'error',
        {
          default: 'disallow',
          rules: [
            { from: ['market', 'fundamental', 'technical', 'portfolio', 'master'], allow: ['shared', 'contracts'] },
            { from: 'widgets', allow: ['shared', 'contracts', 'master', 'fundamental', 'technical', 'portfolio'] },
            { from: 'shared', allow: ['contracts'] },
            { from: 'contracts', allow: [] },
            { from: 'app', allow: ['shared', 'contracts', 'widgets', 'market', 'fundamental', 'technical', 'portfolio', 'master'] },
          ],
        },
      ],
      // B5: fetch فقط در api/ یا http.ts
      'no-restricted-syntax': [
        'error',
        {
          selector: "CallExpression[callee.name='fetch']",
          message: 'fetch بی‌سرویس ممنوع — از shared/api/http.ts یا api/ فیچر استفاده کن.',
        },
      ],
    },
  },
  {
    // B5: مسیرهای مجاز fetch -- فقط http.ts مشترک و api/ هر فیچر
    files: ['src/shared/api/**/*.ts', 'src/features/*/api/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-syntax': 'off',
    },
  },
  {
    ignores: ['dist', 'node_modules', 'coverage', 'public'],
  },
);

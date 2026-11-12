import { fileURLToPath } from 'node:url';

// The legacy v1 tree resolves `@shared` to ITS OWN shared layer. Running the
// measurement under frontend-v2's config would silently load the v2 helper of
// the same name, so the alias is pinned to the legacy tree here.
//
// A plain object, not defineConfig(): this file lives outside frontend-v2, so
// vite's config bundler cannot resolve the `vite` package from here.
const repoRoot = fileURLToPath(new URL('../../', import.meta.url));

export default {
  root: repoRoot,
  resolve: {
    alias: {
      '@shared': fileURLToPath(new URL('../../frontend/src/shared', import.meta.url)),
    },
  },
  server: { fs: { allow: [repoRoot], strict: false } },
};
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// The Observatory (every page except /viewer) is the only part of the project
// with a build step. `npm run build` writes it into the FastAPI static folder, so
// the server serves it with no Node at runtime.
//
// `npm run dev` serves it from / instead, with hot reload, and forwards data and
// the no-build 360-degree viewer to a FastAPI server on :8000.
export default defineConfig(({ command }) => ({
  plugins: [svelte()],
  // Built files live under /static/site/ on the FastAPI server; in dev they are
  // served from the root so the page paths (/explore, /insights…) work directly.
  base: command === 'build' ? '/static/site/' : '/',
  build: {
    outDir: '../app/static/site',
    emptyOutDir: true,
    // Pages are code-split (see App.svelte), so the Overview loads ~60 kB. The
    // two big chunks are the map libraries themselves — MapLibre on the Explorer
    // (~1.1 MB, ~290 kB gzipped) and three.js on the 3D view — which splitting
    // cannot shrink further. They load only on the pages that need them.
    chunkSizeWarningLimit: 1200,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/photos': 'http://localhost:8000',
      '/viewer': 'http://localhost:8000',   // the 360-degree viewer and its assets
      '/static': 'http://localhost:8000',
    },
  },
}));

import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// The 3D map is the only part of the project with a build step. It builds into
// the FastAPI static folder, so the server serves it at /map with no Node at
// runtime — `npm` is only needed to change the map, not to run the app.
export default defineConfig({
  plugins: [svelte()],
  base: '/static/map/',
  build: {
    outDir: '../app/static/map',
    emptyOutDir: true,
    // three.js alone is ~600 kB minified (~160 kB gzipped). This is one page
    // served from the local FastAPI app, so splitting it would add complexity
    // without making anything faster for the person using it.
    chunkSizeWarningLimit: 700,
  },
  // `npm run dev` proxies data calls to a FastAPI server on :8000.
  server: { proxy: { '/api': 'http://localhost:8000', '/photos': 'http://localhost:8000' } },
});

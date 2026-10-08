/* A very small pathname router: no dependency, works with the browser's back and
 * forward buttons, and leaves external links and new-tab clicks alone. FastAPI
 * serves the same index.html for every Observatory path (see app/main.py). */
import { writable } from 'svelte/store';

export const path = writable(normalise(window.location.pathname));

function normalise(p: string): string {
  return p.replace(/\/+$/, '') || '/';
}

export function navigate(to: string): void {
  const url = new URL(to, window.location.origin);
  if (url.origin !== window.location.origin) { window.location.href = to; return; }
  history.pushState({}, '', url.pathname + url.search + url.hash);
  path.set(normalise(url.pathname));
  window.scrollTo(0, 0);
}

window.addEventListener('popstate', () => path.set(normalise(window.location.pathname)));

/** Paths the Svelte app handles; anything else (e.g. /viewer) is a full page load. */
export const APP_PATHS = new Set(['/', '/explore', '/insights', '/map', '/methods', '/sources', '/about']);

export function interceptLinks(event: MouseEvent): void {
  const a = (event.target as HTMLElement).closest('a');
  if (!a || a.target || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
  const url = new URL(a.href, window.location.origin);
  if (url.origin !== window.location.origin || !APP_PATHS.has(normalise(url.pathname))) return;
  event.preventDefault();
  navigate(url.pathname + url.search);
}

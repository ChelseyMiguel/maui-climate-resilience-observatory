// Analysis state shared by the Map Explorer, the 3D view and the Analysis
// workspace, so a threshold or period set in one is what the others show.
// Kept for the browser session only; storage failures are ignored.
import { writable } from 'svelte/store';
import { RESEARCH_THRESHOLD } from './threshold.js';

const KEY = 'observatory-analysis';
const DEFAULTS = { threshold: RESEARCH_THRESHOLD, index: 'dndvi', from: null, to: null, year: 2023 };

function initial() {
  try { return { ...DEFAULTS, ...JSON.parse(sessionStorage.getItem(KEY) || '{}') }; } catch { return { ...DEFAULTS }; }
}
export const analysis = writable(initial());
analysis.subscribe((v) => { try { sessionStorage.setItem(KEY, JSON.stringify(v)); } catch { /* private mode */ } });

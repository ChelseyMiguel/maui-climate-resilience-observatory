/* Data access for the map. Same rule as the viewer: fetch() only rejects on
 * network failure, so non-2xx responses become Errors carrying the API's own
 * `detail` message, which says what to run to fix it. */
async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = String(res.status);
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    throw new Error(`${url}: ${detail}`);
  }
  return res.json();
}

/* The elevation grid is raw Int16 little-endian. Read it through a DataView so
 * the byte order is explicit rather than whatever the machine happens to use. */
async function getTerrain() {
  const meta = await getJson('/api/layers/terrain');
  const res = await fetch('/api/layers/terrain.bin');
  if (!res.ok) throw new Error(`/api/layers/terrain.bin: ${res.status}`);
  const view = new DataView(await res.arrayBuffer());
  const grid = new Int16Array(meta.width * meta.height);
  for (let i = 0; i < grid.length; i++) grid[i] = view.getInt16(i * 2, true);
  return { meta, grid };
}

export async function loadAll() {
  const [terrain, browning, fires, sites, studyArea, drought] = await Promise.all([
    getTerrain(),
    getJson('/api/layers/browning'),
    getJson('/api/layers/fires'),
    getJson('/api/layers/sites'),
    getJson('/api/layers/study-area'),
    getJson('/api/layers/drought'),
  ]);
  return { terrain, browning, fires, sites, studyArea, drought };
}

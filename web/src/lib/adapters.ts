/* Data adapters: the only code that knows the API's shapes. Each turns a raw
 * response into the typed interfaces in types.ts. To connect a new or real source,
 * add an adapter here — pages never fetch directly. */
import type {
  DroughtGreenness, DroughtMapInfo, InfrastructureFeature, InfrastructureKind, InfrastructureLayerInfo,
  Observation, RegionInsights, TimeseriesPoint,
} from './types.ts';

async function getJson<T = unknown>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = String(res.status);
    try { detail = (await res.json()).detail || detail; } catch { /* not JSON */ }
    throw new Error(`${url}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const INFRA_KINDS: InfrastructureKind[] = [
  'fire_stations', 'ems_stations', 'hospitals', 'public_schools', 'private_schools',
];

export async function infrastructureCatalog(): Promise<InfrastructureLayerInfo[]> {
  return getJson('/api/layers/context');
}

export async function infrastructure(kind: InfrastructureKind): Promise<InfrastructureFeature[]> {
  const fc = await getJson<{ features: any[] }>(`/api/layers/context/${kind}`);
  return fc.features
    .filter((f) => f.geometry?.type === 'Point')
    .map((f) => ({
      kind, name: f.properties.name,
      lon: f.geometry.coordinates[0], lat: f.geometry.coordinates[1],
      attributes: f.properties.attributes ?? {},
    }));
}

export const regionsGeoJson = () => getJson<GeoJSON.FeatureCollection>('/api/layers/regions');
export const firesGeoJson = () => getJson<GeoJSON.FeatureCollection>('/api/layers/fires');
export const browningGeoJson = () => getJson<GeoJSON.FeatureCollection>('/api/layers/browning');
export const studyArea = () => getJson<{ lat: number; lon: number; radius_m: number; browned_fraction: number }>('/api/layers/study-area');

export async function droughtMaps(): Promise<DroughtMapInfo[]> {
  return getJson('/api/layers/drought-maps');
}
export const droughtMap = (year: number) =>
  getJson<GeoJSON.FeatureCollection>(`/api/layers/drought-maps/${year}`);

export async function observations(): Promise<Observation[]> {
  const rows = await getJson<any[]>('/api/layers/observations');
  return rows.map((r) => ({
    landCoverId: r.land_cover_id, siteName: r.site_name, label: r.label,
    lat: r.lat, lon: r.lon, date: r.date, complete: r.complete,
  }));
}

const series = (rows: { date: string; value?: number; dsci?: number }[]): TimeseriesPoint[] =>
  rows.map((r) => ({ date: r.date, value: (r.value ?? r.dsci) as number }));

export async function regionInsights(key: string): Promise<RegionInsights> {
  const r = await getJson<any>(`/api/layers/insights/${key}`);
  const v = r.vegetation;
  return {
    key: r.key, name: r.name, kind: r.kind, geoid: r.geoid, landKm2: r.land_km2,
    vegetation: v.available
      ? {
          available: true, analysisArea: v.analysis_area, overlap: v.overlap, note: v.note,
          ndvi: series(v.ndvi), nbr: series(v.nbr),
          drySeasonNdvi: v.dry_season_ndvi, drySeasonNbr: v.dry_season_nbr,
        }
      : { available: false, overlap: v.overlap, reason: v.reason },
    drought: { scope: r.drought.scope, source: r.drought.source, weekly: series(r.drought.weekly) },
    fire: r.fire.available
      ? { available: true, nearestFire: r.fire.nearest_fire, acres: r.fire.acres,
          overlapsRegion: r.fire.overlaps_region, distanceKm: r.fire.distance_km }
      : { available: false },
  };
}

export async function droughtGreenness(): Promise<DroughtGreenness> {
  const r = await getJson<any>('/api/layers/drought-greenness');
  return {
    indices: r.indices,
    drySeason: r.dry_season.map((d: any) => ({
      year: d.year, months: d.months, dsci: d.dsci, ndvi: d.ndvi, nbrMonths: d.nbr_months, nbr: d.nbr,
    })),
    notes: r.notes,
  };
}

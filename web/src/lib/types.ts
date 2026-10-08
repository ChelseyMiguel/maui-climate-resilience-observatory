/* Typed interfaces for the Observatory's data. Presentation code depends on these,
 * never on raw API responses, so a data source can be swapped behind an adapter
 * (src/lib/adapters.ts) without touching the UI. */

/** How a dataset reached the app. There is no synthetic/demo data anywhere in the
 *  app: anything not available is shown as an empty state, never invented. */
export type Provenance = 'verified-public' | 'project-analysis';

export interface DatasetMetadata {
  id: string;
  name: string;
  provider: string;
  provenance: Provenance;
  spatialResolution: string;
  coverage: string;
  temporal: string;
  /** In the publisher's own words where possible, e.g. "as of December 2025". */
  currency: string;
  license: string;
  link: string;
  caveat?: string;
}

export interface Region {
  key: 'pukalani' | 'makawao' | 'kula';
  name: string;
  kind: string;            // "2020 Census Designated Place"
  geoid: string | null;
  landKm2: number | null;
}

export interface TimeseriesPoint {
  date: string;            // ISO date
  value: number;
}

export interface DryRun {
  mean: number;
  /** How many dry-season months fed the mean (max 5). Fewer = less trustworthy. */
  months: number;
}

export interface RegionInsights extends Region {
  vegetation:
    | {
        available: true;
        analysisArea: string;
        overlap: number;
        note: string;
        ndvi: TimeseriesPoint[];
        nbr: TimeseriesPoint[];
        drySeasonNdvi: Record<string, DryRun>;
        drySeasonNbr: Record<string, DryRun>;
      }
    | { available: false; overlap: number; reason: string };
  drought: { scope: string; source: string; weekly: TimeseriesPoint[] };
  fire:
    | { available: true; nearestFire: string; acres: number | null; overlapsRegion: boolean; distanceKm: number }
    | { available: false };
}

export type InfrastructureKind =
  | 'fire_stations' | 'ems_stations' | 'hospitals' | 'public_schools' | 'private_schools';

export interface InfrastructureFeature {
  kind: InfrastructureKind;
  name: string;
  lon: number;
  lat: number;
  /** The publisher's raw attributes, shown as-is in the feature card. */
  attributes: Record<string, unknown>;
}

export interface InfrastructureLayerInfo {
  id: InfrastructureKind | 'regions';
  title: string;
  count: number;
  source: string;
  currency: string | null;
}

export interface RasterLayerMetadata {
  id: 'dndvi' | 'dnbr';
  title: string;
  period: string;
  epsg: number;
  pixelMetres: number;
  width: number;
  height: number;
  /** Bounding box in the raster's own projected metres. */
  utmBbox: [number, number, number, number];
  /** Four corners in lon/lat for a map image source: TL, TR, BR, BL. */
  corners: [[number, number], [number, number], [number, number], [number, number]];
  /** Share of valid pixels below the browning threshold. */
  shareBelowThreshold: number;
}

export interface DroughtMapInfo {
  year: number;
  week: string;            // the USDM map date nearest 8 August that year
  categories: number[];
}

export interface Observation {
  landCoverId: string;
  siteName: string;
  label: string;
  lat: number;
  lon: number;
  date: string | null;
  complete: boolean;
}

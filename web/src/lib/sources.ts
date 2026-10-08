/* The provenance table. Every link here was checked to resolve (Oct 2026).
 * Licence wording is deliberately conservative: where the exact terms were not
 * confirmed, it says "see provider terms" rather than asserting a licence. The
 * Hawaii GIS layers' currency is filled in at runtime from the publisher's own
 * layer descriptions (/api/layers/context). */
import type { DatasetMetadata } from './types.ts';

export const DATASETS: DatasetMetadata[] = [
  {
    id: 'dndvi', name: 'dNDVI / dNBR change rasters', provider: 'This project (author’s analysis)',
    provenance: 'project-analysis', spatialResolution: '10 m', coverage: '1.5 km circle centred in Pukalani',
    temporal: 'Dry season (May–Sep) 2022 minus 2019', currency: 'Fixed analysis period',
    license: 'Author’s work; built on Copernicus Sentinel-2 data',
    link: 'https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED',
    caveat: 'Change in greenness/moisture — not a measure of fuel load or fire risk.',
  },
  {
    id: 'series', name: 'Monthly NDVI / NBR series', provider: 'This project (author’s analysis)',
    provenance: 'project-analysis', spatialResolution: 'Area mean of 10 m pixels', coverage: 'Same 1.5 km circle',
    temporal: 'Monthly, Dec 2018 – Dec 2023 (11 months without usable imagery)', currency: 'Fixed analysis period',
    license: 'Author’s work; built on Copernicus Sentinel-2 data',
    link: 'https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED',
  },
  {
    id: 'patches', name: 'Browning patches', provider: 'This project (author’s analysis)',
    provenance: 'project-analysis', spatialResolution: 'Vectorised 10 m pixels', coverage: 'Same 1.5 km circle',
    temporal: '2019 → 2022', currency: 'Fixed analysis period',
    license: 'Author’s work', link: 'https://observer.globe.gov/',
    caveat: '879 patches where dNDVI < −0.10; 298.6 ha total.',
  },
  {
    id: 'globe', name: 'GLOBE Observer land cover observations', provider: 'NASA / The GLOBE Program',
    provenance: 'verified-public', spatialResolution: 'Point sites (100 m footprint), 6 photos each',
    coverage: 'Hawaiʻi, clipped from the worldwide public API', temporal: '2017 – present',
    currency: 'As of the last ingest (scripts/ingest_maui.py)', license: 'See provider terms',
    link: 'https://www.globe.gov/globe-data',
    caveat: 'Citizen science: GPS accuracy ranges from 3 m to over 1 km.',
  },
  {
    id: 'fires', name: 'Wildfire perimeters', provider: 'National Interagency Fire Center (WFIGS)',
    provenance: 'verified-public', spatialResolution: 'Mapped incident perimeters', coverage: 'Maui',
    temporal: '2019, 2023, 2024 incidents', currency: 'As published by NIFC',
    license: 'U.S. government open data — see provider terms', link: 'https://data-nifc.opendata.arcgis.com/',
    caveat: 'Final mapped extents; not progression or ignition data.',
  },
  {
    id: 'usdm', name: 'U.S. Drought Monitor (maps and DSCI)', provider: 'National Drought Mitigation Center, UNL (with USDA, NOAA)',
    provenance: 'verified-public', spatialResolution: 'Drought-category polygons; county index',
    coverage: 'Maui (maps); Maui County (DSCI)', temporal: 'Weekly; one map per year shown (week nearest 8 Aug)',
    currency: 'As published weekly', license: 'Free to use; cite the U.S. Drought Monitor',
    link: 'https://droughtmonitor.unl.edu/DmData/GISData.aspx',
    caveat: 'Expert-blended assessment at broad scale; not a field measurement for any one place.',
  },
  {
    id: 'lcms', name: 'LCMS land change (v2024-10)', provider: 'USDA Forest Service',
    provenance: 'verified-public', spatialResolution: '30 m (shown here as county totals)', coverage: 'Maui County',
    temporal: 'Annual, 2018–2024', currency: 'Dashboard reports generated July 2026',
    license: 'U.S. government data — see provider terms', link: 'https://research.fs.usda.gov/rmrs/centers/lcms',
    caveat: 'County-wide totals, not values for any one site.',
  },
  {
    id: 'terrain', name: 'Terrain elevation', provider: 'AWS Terrain Tiles (Tilezen); largely USGS 3DEP in Hawaiʻi',
    provenance: 'verified-public', spatialResolution: '~19 m tiles, resampled to a 320 × 293 grid',
    coverage: 'Upcountry Maui', temporal: 'Static', currency: 'As published',
    license: 'Mixed sources — see Tilezen attribution', link: 'https://github.com/tilezen/joerd/blob/master/docs/attribution.md',
    caveat: 'Matches GLOBE observers’ recorded elevations to a median of 1 m at 30 sites.',
  },
  {
    id: 'hawaii-gis', name: 'Fire & EMS stations, hospitals, schools', provider: 'Hawaiʻi Statewide GIS Program',
    provenance: 'verified-public', spatialResolution: 'Point locations', coverage: 'Upcountry Maui',
    temporal: 'Varies by layer', currency: 'Per layer — see below', license: 'See provider terms',
    link: 'https://geoportal.hawaii.gov/',
    caveat: 'Locations only. Says nothing about whether a facility is open, staffed, or in use as a shelter.',
  },
  {
    id: 'cdp', name: 'Pukalani, Makawao, Kula boundaries', provider: 'U.S. Census Bureau, via Hawaiʻi Statewide GIS Program',
    provenance: 'verified-public', spatialResolution: 'Census Designated Place polygons', coverage: 'The three places',
    temporal: '2020 Census', currency: '2020 decennial boundaries', license: 'U.S. government data',
    link: 'https://www.census.gov/programs-surveys/geography/about/glossary.html',
    caveat: 'Statistical areas, not legal town limits.',
  },
];

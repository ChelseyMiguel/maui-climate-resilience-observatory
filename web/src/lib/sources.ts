/* The provenance table. Every link here was checked to resolve (Oct 2026).
 * Licence wording is deliberately conservative: where the exact terms were not
 * confirmed, it says "see provider terms" rather than asserting a licence. The
 * Hawaii GIS layers' currency is filled in at runtime from the publisher's own
 * layer descriptions (/api/layers/context). */
import type { DatasetMetadata } from './types.ts';

export const DATASETS: DatasetMetadata[] = [
  {
    id: 'dndvi', kind: 'Satellite-derived index', name: 'dNDVI / dNBR change rasters', provider: 'This project (author’s analysis)',
    provenance: 'project-analysis', spatialResolution: '10 m', coverage: '1.5 km circle centred in Pukalani',
    temporal: 'Dry season (May–Sep) 2022 minus 2019', currency: 'Fixed analysis period',
    license: 'Author’s work; built on Copernicus Sentinel-2 data',
    link: 'https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED',
    caveat: 'Change in greenness/moisture — not a measure of fuel load or fire risk.',
  },
  {
    id: 'series', kind: 'Satellite-derived index', name: 'Monthly NDVI / NBR series', provider: 'This project (author’s analysis)',
    provenance: 'project-analysis', spatialResolution: 'Area mean of 10 m pixels', coverage: 'Same 1.5 km circle',
    temporal: 'Monthly, Dec 2018 – Dec 2023 (11 months without usable imagery)', currency: 'Fixed analysis period',
    license: 'Author’s work; built on Copernicus Sentinel-2 data',
    link: 'https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED',
  },
  {
    id: 'patches', kind: 'Satellite-derived index', name: 'Browning patches', provider: 'This project (author’s analysis)',
    provenance: 'project-analysis', spatialResolution: 'Vectorised 10 m pixels', coverage: 'Same 1.5 km circle',
    temporal: '2019 → 2022', currency: 'Fixed analysis period',
    license: 'Author’s work', link: 'https://observer.globe.gov/',
    caveat: '879 patches where dNDVI < −0.10; 298.6 ha total.',
  },
  {
    id: 'globe', kind: 'In-situ observation', name: 'GLOBE Observer land cover observations', provider: 'NASA / The GLOBE Program',
    provenance: 'verified-public', spatialResolution: 'Point sites (100 m footprint), 6 photos each',
    coverage: 'Hawaiʻi, clipped from the worldwide public API', temporal: '2017 – present',
    currency: 'As of the last ingest (scripts/ingest_maui.py)', license: 'See provider terms',
    link: 'https://www.globe.gov/globe-data',
    caveat: 'Citizen science: GPS accuracy ranges from 3 m to over 1 km.',
  },
  {
    id: 'fires', kind: 'Mapped observation', name: 'Wildfire perimeters', provider: 'National Interagency Fire Center (WFIGS)',
    provenance: 'verified-public', spatialResolution: 'Mapped incident perimeters', coverage: 'Maui',
    temporal: '2019, 2023, 2024 incidents', currency: 'As published by NIFC',
    license: 'U.S. government open data — see provider terms', link: 'https://data-nifc.opendata.arcgis.com/',
    caveat: 'Final mapped extents; not progression or ignition data.',
  },
  {
    id: 'usdm', kind: 'Expert synthesis', name: 'U.S. Drought Monitor (maps and DSCI)', provider: 'National Drought Mitigation Center, UNL (with USDA, NOAA)',
    provenance: 'verified-public', spatialResolution: 'Drought-category polygons; county index',
    coverage: 'Maui (maps); Maui County (DSCI)', temporal: 'Weekly; one map per year shown (week nearest 8 Aug)',
    currency: 'As published weekly', license: 'Free to use; cite the U.S. Drought Monitor',
    link: 'https://droughtmonitor.unl.edu/DmData/GISData.aspx',
    caveat: 'Expert-blended assessment at broad scale; not a field measurement for any one place.',
  },
  {
    id: 'lcms', kind: 'Modelled classification', name: 'LCMS land change (v2024-10)', provider: 'USDA Forest Service',
    provenance: 'verified-public', spatialResolution: '30 m (shown here as county totals)', coverage: 'Maui County',
    temporal: 'Annual, 2018–2024', currency: 'Dashboard reports generated July 2026',
    license: 'U.S. government data — see provider terms', link: 'https://research.fs.usda.gov/rmrs/centers/lcms',
    caveat: 'County-wide totals, not values for any one site.',
  },
  {
    id: 'terrain', kind: 'Elevation model', name: 'Terrain elevation', provider: 'AWS Terrain Tiles (Tilezen); largely USGS 3DEP in Hawaiʻi',
    provenance: 'verified-public', spatialResolution: '3D view and offline relief: ~19 m tiles resampled to a 320 × 293 grid (~68 m). Map Explorer 3D, hillshade, profiles, pixel elevations: terrarium tiles at z14 (~9 m pixels), bilinear',
    coverage: 'Upcountry Maui', temporal: 'Static', currency: 'As published',
    license: 'Mixed sources — see Tilezen attribution', link: 'https://github.com/tilezen/joerd/blob/master/docs/attribution.md',
    caveat: 'Matches GLOBE observers’ recorded elevations to a median of 1 m at 30 sites.',
  },
  {
    id: 'hawaii-gis', kind: 'Reference / administrative', name: 'Fire & EMS stations, hospitals, schools', provider: 'Hawaiʻi Statewide GIS Program',
    provenance: 'verified-public', spatialResolution: 'Point locations', coverage: 'Upcountry Maui',
    temporal: 'Varies by layer', currency: 'Per layer — see below', license: 'See provider terms',
    link: 'https://geoportal.hawaii.gov/',
    caveat: 'Locations only. Says nothing about whether a facility is open, staffed, or in use as a shelter.',
  },
  {
    id: 'cdp', kind: 'Reference / administrative', name: 'Pukalani, Makawao, Kula boundaries', provider: 'U.S. Census Bureau, via Hawaiʻi Statewide GIS Program',
    provenance: 'verified-public', spatialResolution: 'Census Designated Place polygons', coverage: 'The three places',
    temporal: '2020 Census', currency: '2020 decennial boundaries', license: 'U.S. government data',
    link: 'https://www.census.gov/programs-surveys/geography/about/glossary.html',
    caveat: 'Statistical areas, not legal town limits.',
  },
  // Added Oct 21, 2026. These links could not be re-checked from the build
  // environment (no route to the hosts), so linkChecked is false.
  {
    id: 'chirps', kind: 'Satellite + gauge estimate', name: 'CHIRPS daily rainfall (summed to months)', provider: 'UC Santa Barbara Climate Hazards Center, via Google Earth Engine',
    provenance: 'verified-public', spatialResolution: '0.05° (~5.5 km); one pixel at the study-area centre', coverage: 'Quasi-global land 50°S–50°N',
    temporal: 'Monthly sums 2018–2024 (daily product from 1981)', currency: 'As exported (scripts/gee/rainfall_monthly.js)', license: 'See provider terms',
    link: 'https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY', linkChecked: false,
    caveat: 'One coarse pixel: the area’s rainfall regime, not a gauge reading at Pukalani.',
  },
  {
    id: 'terraclimate', kind: 'Climate model (interpolated)', name: 'TerraClimate monthly precipitation', provider: 'University of Idaho (Abatzoglou et al.), via Google Earth Engine',
    provenance: 'verified-public', spatialResolution: '~4.6 km; one pixel', coverage: 'Global land', temporal: 'Monthly 2018–2024 (product from 1958)',
    currency: 'As exported', license: 'See provider terms', link: 'https://developers.google.com/earth-engine/datasets/catalog/IDAHO_EPSCOR_TERRACLIMATE', linkChecked: false,
    caveat: 'Climatically aided interpolation, not a direct measurement. Other water-balance variables (e.g. climatic water deficit) are not exported yet.',
  },
  {
    id: 'imerg', kind: 'Satellite estimate', name: 'GPM IMERG V07 monthly precipitation', provider: 'NASA Goddard (GPM), via Google Earth Engine',
    provenance: 'verified-public', spatialResolution: '0.1° (~11 km); one pixel', coverage: 'Global', temporal: 'Monthly 2018–2024',
    currency: 'As exported', license: 'NASA open data — see provider terms', link: 'https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_MONTHLY_V07', linkChecked: false,
    caveat: 'Monthly mean rate (mm/h) × hours in the month = mm.',
  },
  {
    id: 'era5land', kind: 'Reanalysis', name: 'ERA5-Land monthly total precipitation', provider: 'ECMWF / Copernicus Climate Change Service, via Google Earth Engine',
    provenance: 'verified-public', spatialResolution: '0.1° (~11 km); one pixel', coverage: 'Global land', temporal: 'Monthly 2018–2024',
    currency: 'As exported', license: 'Copernicus licence — see provider terms', link: 'https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_MONTHLY_AGGR', linkChecked: false,
    caveat: 'Model reanalysis: physically consistent but not an observation; coarse over steep terrain.',
  },
  {
    id: 's2cloudless', kind: 'Basemap imagery', name: 'Sentinel-2 cloudless 2019 and 2022 (basemap)', provider: 'EOX IT Services GmbH (modified Copernicus Sentinel data)',
    provenance: 'verified-public', spatialResolution: '10 m', coverage: 'Global', temporal: 'Annual cloud-free mosaics', currency: 'Per year',
    license: 'CC BY-NC-SA 4.0 (2018 onward)', link: 'https://s2maps.eu', linkChecked: false,
    caveat: 'A visual whole-year mosaic for context and the before/after swipe. Not the study’s May–Sep median composite and never used in any number.',
  },
  {
    id: 'usgs-basemaps', kind: 'Basemap imagery', name: 'USGS National Map imagery and topographic basemaps', provider: 'U.S. Geological Survey',
    provenance: 'verified-public', spatialResolution: 'Up to ~1 m imagery (varies)', coverage: 'United States', temporal: 'Capture date varies by tile',
    currency: 'As served', license: 'Public domain (U.S. government)', link: 'https://www.usgs.gov/programs/national-geospatial-program/national-map', linkChecked: false,
    caveat: 'Context only; imagery dates are not matched to 2019 or 2022.',
  },
  {
    id: 'carto', kind: 'Basemap cartography', name: 'Minimal dark basemap', provider: 'CARTO, with OpenStreetMap data',
    provenance: 'verified-public', spatialResolution: 'Vector-rendered tiles', coverage: 'Global', temporal: 'Current', currency: 'As served',
    license: '© OpenStreetMap contributors (ODbL), © CARTO — see provider terms', link: 'https://carto.com/attributions', linkChecked: false,
  },
  // Added Oct 21, 2026 with scripts/remote_sensing/ (fetched from the public AWS
  // archives; links not re-checked from the build environment).
  {
    id: 's2-aws', kind: 'Satellite imagery (reflectance)', name: 'Sentinel-2 Level-2A surface reflectance (COGs)',
    provider: 'ESA Copernicus; archive by Element 84 on AWS Open Data (sentinel-cogs)',
    provenance: 'verified-public', spatialResolution: '10 m (B2-B4, B8), 20 m (B12, SCL)', coverage: 'Tile 4QGJ (Upcountry Maui)',
    temporal: 'Dry seasons (May–Sep) 2017–2025; 2023 before/after the fires', currency: 'Archive as of Oct 2026',
    license: 'Copernicus Sentinel data, free and open (see provider terms)', link: 'https://registry.opendata.aws/sentinel-2-l2a-cogs/', linkChecked: false,
    caveat: 'Cloud-masked (SCL 1, 3, 8, 9, 10) median composites, tile cloud < 60 %. Rebuilt 2022 − 2019 dNDVI matches the study raster: r = 0.854, 77 % same class at −0.10. Some residual cloud upslope; a few pixels never clear.',
  },
  {
    id: 'lidar-3dep', kind: 'Lidar point cloud', name: '2022–2023 NOAA/USGS lidar, Maui (QL1)',
    provider: 'USGS 3D Elevation Program / NOAA; Entwine point tiles on AWS (usgs-lidar-public, HI_NOAAMauiOahu_2)',
    provenance: 'verified-public', spatialResolution: '~5 points/m² used (of ~8 nominal); 2 m grids', coverage: 'The 3 km study box',
    temporal: 'Flown 19 Feb – 30 Mar 2023 (from point GPS times)', currency: 'As published', license: 'Public domain (3DEP)',
    link: 'https://www.fisheries.noaa.gov/inport/item/75941', linkChecked: false,
    caveat: 'Height above ground includes buildings (not classified separately here). Ground is ~5 m above the AWS terrain tiles at a test point — a vertical-datum difference; each elevation is labelled with its source.',
  },
  {
    id: 'worldcover', kind: 'Land-cover classification', name: 'ESA WorldCover 2021 v200',
    provider: 'European Space Agency (WorldCover consortium); AWS Open Data (esa-worldcover)',
    provenance: 'verified-public', spatialResolution: '10 m', coverage: 'Terrain box (tile N18W159)', temporal: '2021',
    currency: 'v200', license: 'CC BY 4.0', link: 'https://esa-worldcover.org/', linkChecked: false,
    caveat: 'A modelled classification from Sentinel-1/2, not a field survey; resampled to the study grid by nearest neighbour.',
  },
  {
    id: 'copdem', kind: 'Elevation model', name: 'Copernicus DEM GLO-90 (locator inset)',
    provider: 'ESA / Airbus (Copernicus); AWS Open Data (copernicus-dem-90m)', provenance: 'verified-public',
    spatialResolution: '90 m', coverage: 'Maui', temporal: '2011–2015 acquisitions', currency: 'As published',
    license: 'Copernicus DEM licence (free, attribution) — see provider terms', link: 'https://registry.opendata.aws/copernicus-dem/', linkChecked: false,
    caveat: 'Only used to draw the island in the locator inset.',
  },
  {
    id: 'landsat-pc', kind: 'Satellite imagery (reflectance)', name: 'Landsat 5/7/8/9 Collection 2 Level-2 surface reflectance',
    provider: 'USGS; hosted free by Microsoft Planetary Computer (landsat-c2-l2)', provenance: 'verified-public',
    spatialResolution: '30 m', coverage: 'Path 063 / row 046 (study area)', temporal: 'Dry seasons (May–Sep) 2000–2025, Tier 1 only',
    currency: 'Archive as of Oct 2026', license: 'Public domain (USGS); Planetary Computer terms of use',
    link: 'https://planetarycomputer.microsoft.com/dataset/landsat-c2-l2', linkChecked: true,
    caveat: 'Same method as the Earth Engine notebook (QA bits 1, 3, 4 masked). No Landsat 5 over this scene in 2000–2011; Landsat 8/9 (2013 on) read NDVI higher than Landsat 7 — 2014 stands out for that reason.',
  },
];

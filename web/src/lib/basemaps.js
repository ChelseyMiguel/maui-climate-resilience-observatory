// Basemaps for the Map Explorer. Each one states what it is, when it was
// captured and how sharp it is, because none of them is the study's own
// dry-season composite. Remote tiles can fail (offline, blocked, rate-limited):
// the Explorer then falls back to the local relief and says which one failed.

const EOX_ATTR = (y) => `Sentinel-2 cloudless ${y} by EOX IT Services GmbH (contains modified Copernicus Sentinel data ${y}), CC BY-NC-SA 4.0`;
const eox = (y) => `https://tiles.maps.eox.at/wms?service=WMS&request=GetMap&version=1.1.1&layers=s2cloudless-${y}_3857&styles=&format=image/jpeg&srs=EPSG:3857&bbox={bbox-epsg-3857}&width=256&height=256`;
const usgs = (svc) => `https://basemap.nationalmap.gov/arcgis/rest/services/${svc}/MapServer/tile/{z}/{y}/{x}`;

export const BASEMAPS = [
  { id: 'relief', label: 'Terrain (offline)', kind: 'Elevation tint',
    note: 'Elevation tint from the app’s own 68 m DEM grid (AWS Terrain Tiles). Works with no connection.' },
  // CARTO's dark tiles now carry an "API key required" watermark; Esri's dark
  // canvas needs no key.
  { id: 'dark', label: 'Minimal dark', kind: 'Reference map',
    tiles: ['https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}'], maxzoom: 16,
    attribution: 'Esri, HERE, Garmin, © OpenStreetMap contributors, and the GIS user community',
    note: 'Roads and coastlines on a dark canvas, no imagery (Esri World Dark Gray Canvas).' },
  { id: 'imagery', label: 'Satellite (USGS)', kind: 'Aerial / satellite imagery', tiles: [usgs('USGSImageryOnly')], maxzoom: 16,
    attribution: 'USGS The National Map: Orthoimagery (public domain)',
    note: 'High-resolution orthoimagery; capture date varies by tile and is not matched to 2019 or 2022.' },
  { id: 'topo', label: 'Topographic (USGS)', kind: 'Topographic map', tiles: [usgs('USGSTopo')], maxzoom: 16,
    attribution: 'USGS The National Map (public domain)', note: 'USGS topographic base: contours, roads, names.' },
  { id: 's2-2019', label: 'Sentinel-2 2019', kind: 'Annual cloud-free mosaic', tiles: [eox(2019)], maxzoom: 14, attribution: EOX_ATTR(2019),
    note: '10 m Sentinel-2 cloud-free mosaic of 2019 — a whole-year composite, not the study’s May–Sep median.' },
  { id: 's2-2022', label: 'Sentinel-2 2022', kind: 'Annual cloud-free mosaic', tiles: [eox(2022)], maxzoom: 14, attribution: EOX_ATTR(2022),
    note: '10 m Sentinel-2 cloud-free mosaic of 2022 — a whole-year composite, not the study’s May–Sep median.' },
];

export const DEM_TILES = {
  type: 'raster-dem', tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
  encoding: 'terrarium', tileSize: 256, maxzoom: 15,
  attribution: 'Elevation: AWS Terrain Tiles (Mapzen/Tilezen, terrarium)',
};

export const basemapById = (id) => BASEMAPS.find((b) => b.id === id) ?? BASEMAPS[0];

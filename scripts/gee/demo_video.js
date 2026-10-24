// demo_video.js
// Paste into a NEW script tab at code.earthengine.google.com and press Run.
//
// The NASA SEES analysis, live: Sentinel-2 dry-season (May-Sep) 2019 vs 2022 around
// Pukalani Park. Same method as the study: SCL cloud mask, tile cloud < 60 %,
// median composites, NDVI = (B8-B4)/(B8+B4), dNDVI = 2022 - 2019, browned = dNDVI < -0.10.
//
// Check against the study (10 m, EPSG:32604): 70,280 valid pixels, 30,037 browned (42.7 %).
// Earth Engine's composite can differ by a few pixels or tenths of a percent; if it is
// far off, say so rather than forcing a match.
//
// Chelsey Miguel | NASA SEES

var AOI = ee.Geometry.Point([-156.344856, 20.838722]).buffer(1500);
var PROJ = 'EPSG:32604';

function maskS2(img) {
  var scl = img.select('SCL');
  var bad = scl.eq(1).or(scl.eq(3)).or(scl.eq(8)).or(scl.eq(9)).or(scl.eq(10));
  return img.updateMask(bad.not()).divide(10000).copyProperties(img, ['system:time_start']);
}

function dry(year) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(AOI)
    .filterDate(year + '-05-01', year + '-10-01')
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60))
    .map(maskS2);
}

var c19 = dry(2019), c22 = dry(2022);
var m19 = c19.median(), m22 = c22.median();
var ndvi19 = m19.normalizedDifference(['B8', 'B4']).rename('NDVI_2019');
var ndvi22 = m22.normalizedDifference(['B8', 'B4']).rename('NDVI_2022');
var d = ndvi22.subtract(ndvi19).rename('dNDVI').clip(AOI);
var browned = d.lt(-0.10).selfMask().rename('browned');

// ---- Map layers (toggle these on camera, in this order) ----
Map.setOptions('SATELLITE');
Map.centerObject(AOI, 14);
var tc = {bands: ['B4', 'B3', 'B2'], min: 0.02, max: 0.28};
var veg = {min: 0.1, max: 0.8, palette: ['#7a4b1f', '#c9a66b', '#e8e0a0', '#8fbf5a', '#2e7d32', '#0b4d1a']};
Map.addLayer(m19.clip(AOI), tc, '1  True colour, dry season 2019');
Map.addLayer(m22.clip(AOI), tc, '2  True colour, dry season 2022', false);
Map.addLayer(ndvi19.clip(AOI), veg, '3  NDVI 2019', false);
Map.addLayer(ndvi22.clip(AOI), veg, '4  NDVI 2022', false);
Map.addLayer(d, {min: -0.4, max: 0.2, palette: ['#8c2d04', '#fd8d3c', '#f7f7f7', '#41b6c4', '#0c2c84']}, '5  Change in NDVI (2022 - 2019)', false);
Map.addLayer(browned, {palette: ['#ff7a00']}, '6  Browned: dNDVI < -0.10', false);
Map.addLayer(ee.Image().byte().paint(AOI, 1, 2), {palette: ['#ffffff']}, 'Study area (1.5 km)');

// ---- Numbers (appear in the Console) ----
var valid = d.mask().rename('valid').reduceRegion({
  reducer: ee.Reducer.sum(), geometry: AOI, scale: 10, crs: PROJ, maxPixels: 1e9}).get('valid');
var nb = browned.unmask(0).reduceRegion({
  reducer: ee.Reducer.sum(), geometry: AOI, scale: 10, crs: PROJ, maxPixels: 1e9}).get('browned');
print('Scenes used, dry season 2019:', c19.size());
print('Scenes used, dry season 2022:', c22.size());
print('Valid 10 m pixels:', valid);
print('Browned pixels (dNDVI < -0.10):', nb);
print('Share browned (%):', ee.Number(nb).divide(ee.Number(valid)).multiply(100));
print('Browned area (ha):', ee.Number(nb).multiply(100).divide(10000));
print('Mean NDVI 2019:', ndvi19.reduceRegion({reducer: ee.Reducer.mean(), geometry: AOI, scale: 10, crs: PROJ}).get('NDVI_2019'));
print('Mean NDVI 2022:', ndvi22.reduceRegion({reducer: ee.Reducer.mean(), geometry: AOI, scale: 10, crs: PROJ}).get('NDVI_2022'));

// ---- Chart: monthly NDVI, 2018-2025, for the "2022 dips" shot ----
var months = ee.List.sequence(0, 95);
var start = ee.Date('2018-01-01');
var series = ee.FeatureCollection(months.map(function (m) {
  var t0 = start.advance(m, 'month');
  var col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(AOI)
    .filterDate(t0, t0.advance(1, 'month'))
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60)).map(maskS2);
  var v = ee.Algorithms.If(col.size().gt(0),
    col.median().normalizedDifference(['B8', 'B4']).reduceRegion({
      reducer: ee.Reducer.mean(), geometry: AOI, scale: 10, maxPixels: 1e9}).get('nd'), null);
  return ee.Feature(null, {'system:time_start': t0.millis(), NDVI: v});
})).filter(ee.Filter.notNull(['NDVI']));
print(ui.Chart.feature.byFeature(series, 'system:time_start', 'NDVI').setOptions({
  title: 'Pukalani Park area: monthly median NDVI (Sentinel-2)',
  lineWidth: 2, pointSize: 3, colors: ['#ff7a00'],
  vAxis: {title: 'NDVI'}, hAxis: {title: 'Month'}, legend: {position: 'none'}}));

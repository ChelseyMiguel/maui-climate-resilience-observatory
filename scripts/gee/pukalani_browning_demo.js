var aoi = ee.Geometry.Point([-156.344856, 20.838722]).buffer(1500);

function cleanImage(img) {
  var scl = img.select('SCL');
  var bad = scl.eq(1).or(scl.eq(3)).or(scl.eq(8)).or(scl.eq(9)).or(scl.eq(10));
  return img.updateMask(bad.not()).divide(10000);
}

function drySeason(year) {
  return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(aoi)
    .filterDate(year + '-05-01', year + '-10-01')
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60))
    .map(cleanImage);
}

var scenes2019 = drySeason(2019);
var scenes2022 = drySeason(2022);
var image2019 = scenes2019.median();
var image2022 = scenes2022.median();

var ndvi2019 = image2019.normalizedDifference(['B8', 'B4']).rename('ndvi2019');
var ndvi2022 = image2022.normalizedDifference(['B8', 'B4']).rename('ndvi2022');
var change = ndvi2022.subtract(ndvi2019).rename('change').clip(aoi);
var browned = change.lt(-0.10).selfMask().rename('browned');

var trueColor = {bands: ['B4', 'B3', 'B2'], min: 0.02, max: 0.28};
var greenness = {min: 0.1, max: 0.8, palette: ['#7a4b1f', '#c9a66b', '#e8e0a0', '#8fbf5a', '#2e7d32', '#0b4d1a']};
var changeColors = {min: -0.4, max: 0.2, palette: ['#8c2d04', '#fd8d3c', '#f7f7f7', '#41b6c4', '#0c2c84']};

Map.setOptions('SATELLITE');
Map.centerObject(aoi, 14);
Map.addLayer(image2019.clip(aoi), trueColor, '1  True colour 2019');
Map.addLayer(image2022.clip(aoi), trueColor, '2  True colour 2022', false);
Map.addLayer(ndvi2019.clip(aoi), greenness, '3  NDVI 2019', false);
Map.addLayer(ndvi2022.clip(aoi), greenness, '4  NDVI 2022', false);
Map.addLayer(change, changeColors, '5  Change in NDVI', false);
Map.addLayer(browned, {palette: ['#ff7a00']}, '6  Browned', false);
Map.addLayer(ee.Image().byte().paint(aoi, 1, 2), {palette: ['#ffffff']}, 'Study area');

function total(image, name) {
  return image.reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: aoi,
    scale: 10,
    crs: 'EPSG:32604',
    maxPixels: 1e9
  }).get(name);
}

var validPixels = total(change.mask().rename('valid'), 'valid');
var brownedPixels = total(browned.unmask(0), 'browned');

print('Scenes used, dry season 2019:', scenes2019.size());
print('Scenes used, dry season 2022:', scenes2022.size());
print('Valid 10 m pixels:', validPixels);
print('Browned pixels (change < -0.10):', brownedPixels);
print('Share browned (%):', ee.Number(brownedPixels).divide(validPixels).multiply(100));
print('Browned area (ha):', ee.Number(brownedPixels).multiply(100).divide(10000));

var firstMonth = ee.Date('2018-01-01');
var monthly = ee.FeatureCollection(ee.List.sequence(0, 95).map(function (i) {
  var start = firstMonth.advance(i, 'month');
  var scenes = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(aoi)
    .filterDate(start, start.advance(1, 'month'))
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60))
    .map(cleanImage);
  var ndvi = ee.Algorithms.If(
    scenes.size().gt(0),
    scenes.median().normalizedDifference(['B8', 'B4']).reduceRegion({
      reducer: ee.Reducer.mean(),
      geometry: aoi,
      scale: 10,
      maxPixels: 1e9
    }).get('nd'),
    null
  );
  return ee.Feature(null, {'system:time_start': start.millis(), ndvi: ndvi});
})).filter(ee.Filter.notNull(['ndvi']));

print(ui.Chart.feature.byFeature(monthly, 'system:time_start', 'ndvi').setOptions({
  title: 'Pukalani Park area: monthly NDVI',
  lineWidth: 2,
  pointSize: 3,
  colors: ['#ff7a00'],
  legend: {position: 'none'},
  vAxis: {title: 'NDVI'},
  hAxis: {title: 'Month'}
}));

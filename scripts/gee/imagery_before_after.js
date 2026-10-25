var BBOX = ee.Geometry.Rectangle([-156.45, 20.70, -156.24, 20.88], 'EPSG:4326', false);

function maskS2(img) {
  var scl = img.select('SCL');
  var bad = scl.eq(3).or(scl.eq(8)).or(scl.eq(9)).or(scl.eq(10)).or(scl.eq(1));
  return img.updateMask(bad.not()).divide(10000);
}

function composite(start, end, label) {
  var c = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(BBOX).filterDate(start, end)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60))
    .map(maskS2);
  print(label + ' — scenes used:', c.size());

  return c.median().select(['B4', 'B3', 'B2'])
    .visualize({min: 0.0, max: 0.30, gamma: 1.3});
}

var before = composite('2023-05-01', '2023-08-08', 'Before (May 1 - Aug 7, 2023)');

var after = composite('2023-08-15', '2023-11-01', 'After (Aug 15 - Oct 31, 2023)');

Map.centerObject(BBOX, 12);
Map.addLayer(before, {}, 'Before');
Map.addLayer(after, {}, 'After');

['before', 'after'].forEach(function (name) {
  Export.image.toDrive({
    image: name === 'before' ? before : after,
    description: name + '_2023',
    region: BBOX,
    crs: 'EPSG:4326',
    dimensions: '2048x1877',
    fileFormat: 'GeoTIFF',
    maxPixels: 1e9
  });
});

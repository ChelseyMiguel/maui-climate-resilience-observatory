// imagery_before_after.js
// Paste into a NEW script tab at code.earthengine.google.com
//
// True-colour Sentinel-2 images of Upcountry Maui from BEFORE and AFTER the
// 8 August 2023 fires, for draping on the Observatory's 3D terrain (/map).
// Burn scars are real surface change visible in the imagery — not a model.
//
// The export grid matches the 3D map exactly: the terrain bounding box, in
// EPSG:4326 (linear in lat/lon), 2048 x 1877 px. Do not change crs, region or
// dimensions, or the image will not line up with the terrain.
//
// After exporting, put the two files in the project at:
//   data/imagery/before_2023.tif
//   data/imagery/after_2023.tif
//
// Chelsey Miguel | NASA SEES

// Same box as data/terrain/upcountry_dem.json
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
  // Median of cloud-masked scenes, then an 8-bit true-colour visualisation.
  return c.median().select(['B4', 'B3', 'B2'])
    .visualize({min: 0.0, max: 0.30, gamma: 1.3});
}

// Before: the 2023 dry season up to the day before the fires.
var before = composite('2023-05-01', '2023-08-08', 'Before (May 1 - Aug 7, 2023)');
// After: from a week after ignition, once smoke has cleared, to end of October.
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

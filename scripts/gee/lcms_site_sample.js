var sites = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Point([-156.44900, 20.74890]), {site: '04QGH656964'}),
  ee.Feature(ee.Geometry.Point([-156.43800, 20.70490]), {site: '04QGH668915'}),
  ee.Feature(ee.Geometry.Point([-156.33350, 20.72540]), {site: '04QGH777940'}),
  ee.Feature(ee.Geometry.Point([-156.33280, 20.74120]), {site: '04QGH777957'}),
  ee.Feature(ee.Geometry.Point([-156.33240, 20.74270]), {site: '04QGH777959'}),
  ee.Feature(ee.Geometry.Point([-156.32970, 20.75880]), {site: '04QGH780977'}),
  ee.Feature(ee.Geometry.Point([-156.34520, 20.83810]), {site: '04QGJ762065'}),
  ee.Feature(ee.Geometry.Point([-156.34459, 20.83841]), {site: '04QGJ763065'}),
  ee.Feature(ee.Geometry.Point([-156.34395, 20.83800]), {site: '04QGJ764064'}),
  ee.Feature(ee.Geometry.Point([-156.34400, 20.83860]), {site: '04QGJ764065'}),
  ee.Feature(ee.Geometry.Point([-156.34360, 20.84050]), {site: '04QGJ764067'}),
  ee.Feature(ee.Geometry.Point([-156.31680, 20.85070]), {site: '04QGJ792079'}),
  ee.Feature(ee.Geometry.Point([-156.31660, 20.85120]), {site: '04QGJ792080'}),
  ee.Feature(ee.Geometry.Point([-156.29400, 20.84160]), {site: '04QGJ816069'}),
  ee.Feature(ee.Geometry.Point([-156.29300, 20.84280]), {site: '04QGJ817071'})
]);

var lcms = ee.ImageCollection('projects/gtac-data-publish/assets/LCMS/Product_Version/2025-11')
  .filterBounds(sites);
print('LCMS images over the sites (must be > 0):', lcms.size());
print('Bands:', ee.Image(lcms.first()).bandNames());

print('LCMS years available:',
  lcms.aggregate_array('system:time_start').map(function (t) { return ee.Date(t).get('year'); }).distinct().sort());

var first = ee.Image(lcms.first());
print('Change class names:', first.get('Change_class_names'));
print('Land_Cover class names:', first.get('Land_Cover_class_names'));

var years = ee.List.sequence(2018, 2024);

var samples = ee.FeatureCollection(years.map(function (y) {
  y = ee.Number(y).int();

  var img = lcms.filterDate(ee.Date.fromYMD(y, 1, 1), ee.Date.fromYMD(y.add(1), 1, 1)).mosaic()
    .select(['Change', 'Land_Cover', 'Land_Use']);

  return img.sampleRegions({
    collection: sites.map(function (f) { return f.set('year', y); }),
    scale: 30,
    geometries: false
  });
}).flatten());

function withName(band) {
  var values = ee.List(first.get(band + '_class_values'));
  var names = ee.List(first.get(band + '_class_names'));
  var lookup = ee.Dictionary.fromLists(
    values.map(function (v) { return ee.Number(v).format('%d'); }), names);
  return function (f) {
    return f.set(band + '_name', lookup.get(ee.Number(f.get(band)).format('%d'), 'unknown'));
  };
}
var labelled = samples
  .map(withName('Change'))
  .map(withName('Land_Cover'))
  .map(withName('Land_Use'));

print('Sample rows (sites x years):', labelled.size());
print('First rows:', labelled.limit(5));

Export.table.toDrive({
  collection: labelled,
  description: 'lcms_site_classes',
  fileFormat: 'CSV',
  selectors: ['site', 'year', 'Change', 'Change_name', 'Land_Cover', 'Land_Cover_name',
              'Land_Use', 'Land_Use_name']
});

var aoi = ee.Geometry.Point([-156.344856, 20.838722]).buffer(1500);
Map.centerObject(aoi, 14);

var change2022 = ee.Image(lcms.filter(ee.Filter.eq('year', 2022)).first())
  .select('Change').clip(aoi);
Map.addLayer(change2022, {}, 'LCMS Change 2022');
Map.addLayer(sites, {color: 'red'}, 'GLOBE sites');

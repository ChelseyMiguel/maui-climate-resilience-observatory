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

var WC_NAMES = ee.Dictionary({
  '10': 'Tree cover', '20': 'Shrubland', '30': 'Grassland', '40': 'Cropland',
  '50': 'Built-up', '60': 'Bare / sparse vegetation', '70': 'Snow and ice',
  '80': 'Permanent water bodies', '90': 'Herbaceous wetland', '95': 'Mangroves',
  '100': 'Moss and lichen'
});

function worldcover(id, year) {
  var img = ee.ImageCollection(id).first().select('Map');
  return img.sampleRegions({collection: sites, scale: 10, geometries: false})
    .map(function (f) {
      var v = ee.Number(f.get('Map')).int();
      return f.set({product: 'worldcover', year: year, class_value: v,
                    class_name: WC_NAMES.get(v.format('%d'), 'unknown')});
    });
}

var DW_NAMES = ee.List(['water', 'trees', 'grass', 'flooded_vegetation', 'crops',
                        'shrub_and_scrub', 'built', 'bare', 'snow_and_ice']);

function dynamicWorld(year) {
  var s = ee.Date.fromYMD(year, 1, 1);

  var modal = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
    .filterBounds(sites).filterDate(s, s.advance(1, 'year'))
    .select('label').mode();
  return modal.sampleRegions({collection: sites, scale: 10, geometries: false})
    .filter(ee.Filter.notNull(['label']))
    .map(function (f) {
      var v = ee.Number(f.get('label')).int();
      return f.set({product: 'dynamicworld', year: year, class_value: v,
                    class_name: DW_NAMES.get(v)});
    });
}

var all = worldcover('ESA/WorldCover/v100', 2020).merge(worldcover('ESA/WorldCover/v200', 2021));
[2018, 2019, 2020, 2021, 2022, 2023, 2024].forEach(function (y) { all = all.merge(dynamicWorld(y)); });

print('Rows (expect ~15 sites x 9 maps):', all.size());
print('First rows:', all.limit(10));

Export.table.toDrive({
  collection: all,
  description: 'landcover_site_classes',
  fileFormat: 'CSV',
  selectors: ['site', 'product', 'year', 'class_value', 'class_name']
});

Map.centerObject(sites, 12);
Map.addLayer(ee.ImageCollection('ESA/WorldCover/v200').first(), {bands: ['Map']}, 'WorldCover 2021');
Map.addLayer(sites, {color: 'red'}, 'GLOBE sites');

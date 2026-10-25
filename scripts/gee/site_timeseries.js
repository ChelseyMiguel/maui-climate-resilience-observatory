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

var SITE_BUFFER_M = 30;

function maskS2(img) {
  var scl = img.select('SCL');
  var bad = scl.eq(3).or(scl.eq(8)).or(scl.eq(9)).or(scl.eq(10)).or(scl.eq(1));
  return img.updateMask(bad.not()).divide(10000)
            .copyProperties(img, ['system:time_start']);
}

var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(sites)
  .filterDate('2018-01-01', '2027-01-01')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60))
  .map(maskS2)
  .map(function (img) {
    var ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI');
    var nbr  = img.normalizedDifference(['B8', 'B12']).rename('NBR');
    return img.addBands(ndvi).addBands(nbr);
  });

var start = ee.Date('2018-01-01');
var nMonths = 108;

var rows = ee.FeatureCollection(
  sites.toList(sites.size()).map(function (f) {
    f = ee.Feature(f);
    var region = f.geometry().buffer(SITE_BUFFER_M);
    var name = f.get('site');

    return ee.FeatureCollection(
      ee.List.sequence(0, nMonths - 1).map(function (m) {
        var t0 = start.advance(m, 'month');
        var monthly = s2.filterDate(t0, t0.advance(1, 'month'));
        var n = monthly.size();

        return ee.Feature(ee.Algorithms.If(
          n.gt(0),
          ee.Feature(null, {
            site: name,
            date: t0.format('YYYY-MM-dd'),
            ndvi: monthly.select('NDVI').median().reduceRegion({
              reducer: ee.Reducer.mean(), geometry: region, scale: 10, maxPixels: 1e9
            }).get('NDVI'),
            nbr: monthly.select('NBR').median().reduceRegion({
              reducer: ee.Reducer.mean(), geometry: region, scale: 10, maxPixels: 1e9
            }).get('NBR'),
            n_pixels: monthly.select('NDVI').median().reduceRegion({
              reducer: ee.Reducer.count(), geometry: region, scale: 10, maxPixels: 1e9
            }).get('NDVI')
          }),

          ee.Feature(null, {site: name, date: t0.format('YYYY-MM-dd'),
                            ndvi: -9999, nbr: -9999, n_pixels: 0})
        ));
      })
    );
  })
).flatten();

Export.table.toDrive({
  collection: rows,
  description: 'globe_site_monthly',
  fileFormat: 'CSV',
  selectors: ['site', 'date', 'ndvi', 'nbr', 'n_pixels']
});

var centre = ee.Geometry.Point([-156.344856, 20.838722]);
var start = ee.Date('2018-01-01');
var nMonths = 84;
var MISSING = -9999;

var chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY').select('precipitation');
var terra  = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE').select('pr');
var imerg  = ee.ImageCollection('NASA/GPM_L3/IMERG_MONTHLY_V07').select('precipitation');
var era5   = ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR').select('total_precipitation_sum');

[['CHIRPS daily', chirps], ['TerraClimate', terra], ['IMERG monthly V07', imerg], ['ERA5-Land monthly', era5]]
  .forEach(function (p) {
    var c = p[1].filterDate(start, start.advance(nMonths, 'month'));
    print(p[0], 'images in window:', c.size(),
          'first:', ee.Date(c.aggregate_min('system:time_start')).format('YYYY-MM-dd'),
          'last:', ee.Date(c.aggregate_max('system:time_start')).format('YYYY-MM-dd'));
  });

function at(img, band, scale) {
  return ee.Dictionary(img.reduceRegion({
    reducer: ee.Reducer.first(), geometry: centre, scale: scale
  })).get(band, MISSING);
}

var rows = ee.FeatureCollection(ee.List.sequence(0, nMonths - 1).map(function (m) {
  var s = start.advance(m, 'month');
  var e = s.advance(1, 'month');
  var hours = e.difference(s, 'hour');

  var days = chirps.filterDate(s, e);
  return ee.Feature(null, {
    date: s.format('YYYY-MM-dd'),

    chirps_mm: at(days.sum(), 'precipitation', 5566),
    chirps_days: days.size(),
    terraclimate_mm: at(terra.filterDate(s, e).mean(), 'pr', 4638),

    imerg_mm: at(imerg.filterDate(s, e).mean().multiply(hours), 'precipitation', 11132),

    era5land_mm: at(era5.filterDate(s, e).mean().multiply(1000), 'total_precipitation_sum', 11132)
  });
}));

print('First rows:', rows.limit(6));
print(ui.Chart.feature.byFeature(rows, 'date', ['chirps_mm', 'terraclimate_mm', 'imerg_mm', 'era5land_mm'])
  .setOptions({title: 'Monthly rainfall at the Pukalani study area (mm)', vAxis: {viewWindow: {min: 0}}}));

Export.table.toDrive({
  collection: rows,
  description: 'pukalani_rainfall_monthly',
  fileFormat: 'CSV',
  selectors: ['date', 'chirps_mm', 'chirps_days', 'terraclimate_mm', 'imerg_mm', 'era5land_mm']
});

Map.centerObject(centre, 11);
Map.addLayer(centre.buffer(1500), {color: 'red'}, 'Study area (1.5 km)');

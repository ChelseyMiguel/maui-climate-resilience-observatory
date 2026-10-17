// rainfall_monthly.js
// Paste into a NEW script tab at code.earthengine.google.com, press Run, then
// open the Tasks tab and run the export.
//
// Monthly rainfall at the Pukalani study area from FOUR independent gridded
// products, 2018-01 to 2024-12. Why four: Upcountry Maui rainfall changes a lot
// over a few km (trade winds hit Haleakala's slope), and every global product is
// coarser than that. Where the products agree, the rainfall signal is real; where
// they disagree, no single one should be trusted at this spot.
//
// The question it answers for the Observatory: the drought index (DSCI) is
// county-wide and expert-blended. Rain is measured. If greenness tracks rain more
// closely than it tracks DSCI, that helps explain why the project's DSCI-NDVI
// correlation depends so much on method (see docs/evidence-claims.md).
//
// Exports: pukalani_rainfall_monthly.csv ->
//   date, chirps_mm, chirps_days, terraclimate_mm, imerg_mm, era5land_mm
//   -9999 = no data for that month (same sentinel as the NDVI/NBR CSVs).
//   Save it as data/research/pukalani_rainfall_monthly.csv
//
// SCALE CAVEAT: each value is the ONE pixel containing the study-area centre.
// Pixels are ~5.5 km (CHIRPS), ~4.6 km (TerraClimate), ~11 km (IMERG, ERA5-Land),
// all far larger than the 1.5 km study area. These are the area's rainfall regime,
// not a gauge reading at Pukalani.
//
// Written without access to Earth Engine, so it has not been run. If a line
// errors, the message names the dataset or band; the catalog page for that ID
// shows the current name. The prints below show each product's date range first.
//
// Chelsey Miguel | NASA SEES

var centre = ee.Geometry.Point([-156.344856, 20.838722]);   // same as every script here
var start = ee.Date('2018-01-01');
var nMonths = 84;                                            // 2018-01 .. 2024-12
var MISSING = -9999;

var chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY').select('precipitation');      // mm/day
var terra  = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIMATE').select('pr');             // mm/month
var imerg  = ee.ImageCollection('NASA/GPM_L3/IMERG_MONTHLY_V07').select('precipitation'); // mm/hour, monthly mean
var era5   = ee.ImageCollection('ECMWF/ERA5_LAND/MONTHLY_AGGR').select('total_precipitation_sum'); // metres

// Show what each product actually covers before trusting the table.
[['CHIRPS daily', chirps], ['TerraClimate', terra], ['IMERG monthly V07', imerg], ['ERA5-Land monthly', era5]]
  .forEach(function (p) {
    var c = p[1].filterDate(start, start.advance(nMonths, 'month'));
    print(p[0], 'images in window:', c.size(),
          'first:', ee.Date(c.aggregate_min('system:time_start')).format('YYYY-MM-dd'),
          'last:', ee.Date(c.aggregate_max('system:time_start')).format('YYYY-MM-dd'));
  });

// Value of a (possibly band-less) image at the centre pixel, or MISSING.
// An empty month reduces to an image with no bands, which yields an empty
// dictionary, so the default is what comes back.
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
    // CHIRPS is daily: sum the month and keep the day count, so a part month
    // (at the end of the record) is visible instead of looking like a dry month.
    chirps_mm: at(days.sum(), 'precipitation', 5566),
    chirps_days: days.size(),
    terraclimate_mm: at(terra.filterDate(s, e).mean(), 'pr', 4638),
    // IMERG monthly is a mean RATE in mm/hour; times the hours in the month = mm.
    imerg_mm: at(imerg.filterDate(s, e).mean().multiply(hours), 'precipitation', 11132),
    // ERA5-Land monthly sum is in metres.
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

// Visual check: the study-area centre on the map.
Map.centerObject(centre, 11);
Map.addLayer(centre.buffer(1500), {color: 'red'}, 'Study area (1.5 km)');

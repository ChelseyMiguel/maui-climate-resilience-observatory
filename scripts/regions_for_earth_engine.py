from __future__ import annotations

import json
from pathlib import Path

from fires_for_earth_engine import polygons, simplify

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "context" / "regions.geojson"
OUT = ROOT / "scripts" / "gee" / "region_timeseries.js"

TEMPLATE = r"""

__REGIONS__

function maskS2(img) {
  var scl = img.select('SCL');
  var bad = scl.eq(3).or(scl.eq(8)).or(scl.eq(9)).or(scl.eq(10)).or(scl.eq(1));
  return img.updateMask(bad.not()).divide(10000).copyProperties(img, ['system:time_start']);
}

var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(regions)
  .filterDate('2018-01-01', '2027-01-01')
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 60))
  .map(maskS2)
  .map(function (img) {
    return img.addBands(img.normalizedDifference(['B8', 'B4']).rename('NDVI'))
              .addBands(img.normalizedDifference(['B8', 'B12']).rename('NBR'));
  });

var start = ee.Date('2018-01-01');
var nMonths = 108;

var rows = ee.FeatureCollection(regions.toList(regions.size()).map(function (f) {
  f = ee.Feature(f);
  return ee.FeatureCollection(ee.List.sequence(0, nMonths - 1).map(function (m) {
    var t0 = start.advance(m, 'month');
    var monthly = s2.filterDate(t0, t0.advance(1, 'month'));
    var n = monthly.size();
    return ee.Feature(ee.Algorithms.If(n.gt(0),
      ee.Feature(null, {
        region: f.get('name'), date: t0.format('YYYY-MM-dd'),
        ndvi: monthly.select('NDVI').median().reduceRegion({reducer: ee.Reducer.mean(), geometry: f.geometry(), scale: 10, maxPixels: 1e10}).get('NDVI'),
        nbr: monthly.select('NBR').median().reduceRegion({reducer: ee.Reducer.mean(), geometry: f.geometry(), scale: 10, maxPixels: 1e10}).get('NBR'),
        n_pixels: monthly.select('NDVI').median().reduceRegion({reducer: ee.Reducer.count(), geometry: f.geometry(), scale: 10, maxPixels: 1e10}).get('NDVI')
      }),
      ee.Feature(null, {region: f.get('name'), date: t0.format('YYYY-MM-dd'), ndvi: -9999, nbr: -9999, n_pixels: 0})));
  }));
})).flatten();

Export.table.toDrive({
  collection: rows, description: 'region_monthly', fileFormat: 'CSV',
  selectors: ['region', 'date', 'ndvi', 'nbr', 'n_pixels']
});

Map.centerObject(regions, 11);
Map.addLayer(regions, {color: '1f6f73'}, 'Pukalani, Makawao, Kula (2020 Census places)');
"""


def main() -> None:
    entries = []
    for f in json.loads(SRC.read_text())["features"]:
        polys = []
        for poly in polygons(f["geometry"]):
            lat0 = poly[0][0][1]
            polys.append([[list(p) for p in simplify([(round(x, 6), round(y, 6)) for x, y in ring], lat0)]
                          for ring in poly])
        geom = json.dumps(polys, separators=(",", ":"))
        entries.append(f"  ee.Feature(ee.Geometry.MultiPolygon({geom}), {{name: '{f['properties']['name']}'}})")
    block = "var regions = ee.FeatureCollection([\n" + ",\n".join(entries) + "\n]);"
    OUT.write_text(TEMPLATE.replace("__REGIONS__", block))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB, {len(entries)} regions)")


if __name__ == "__main__":
    main()

# GLOBE API — what is verified, and how

Checked 2026-10-15 from a sandbox whose network blocks `globe.gov` hosts
(DNS and proxy), so **nothing here was re-confirmed against the live API**.
Evidence comes from web search results and from reading open-source GLOBE code.
The earlier live confirmation (2026-09) is the one recorded in
`lib/globe_api/client.py`.

## Corroborated

| Client assumption | Evidence |
|---|---|
| Endpoint `https://api.globe.gov/search/v1/measurement/protocol/measureddate/`, trailing slash | [IGES-Geospatial/globe-mosquitoes-notebook](https://github.com/IGES-Geospatial/globe-mosquitoes-notebook) `mosquitoes.py` `call()` builds exactly this URL. It is a community copy of GLOBE's own Python notebook ([GLOBE Data User Guide: Python Notebook Samples](https://www.globe.gov/globe-data/globe-data-user-guide/-/wiki/Main/Python+Notebook+Samples)), not an official repository. |
| Params `protocols`, `startdate`, `enddate`, `geojson`, `sample` | Same function. |
| Booleans are uppercase `TRUE`/`FALSE` | Same: `'&sample=' + str(sample).upper()`, `'&geojson=FALSE'`. |
| No key, token or auth for reading | Same: a bare `requests.get(url)`. |
| Output as JSON/GeoJSON, 1,000,000 records per query cap | [GLOBE API page](https://www.globe.gov/globe-data/globe-api) as summarised by search. |
| `sample=FALSE` returns all data, not a bounded sample | Same page. |
| Land cover is six photos: N, E, S, W, up, down | [GLOBE Observer land cover protocol](https://observer.globe.gov/get-data) as summarised by search. |
| Field names are `<protocol without underscores><CamelCaseField>` (e.g. `landcoversMeasuredAt`) | Pattern only: the notebook uses `mosquitohabitatmapperMeasuredAt`, `mosquitohabitatmapperLarvaeCount`. |

`tests/unit/test_globe_client.py::test_request_matches_the_documented_public_globe_api_contract`
pins the request shape so it cannot drift from this.

## Not verified

- **Land cover field names** (`landcoversNorthPhotoUrl`, `landcoversLocationAccuracyM`, …):
  no public document or code found that lists them. Only the live API (or
  Peder Nelson's land-cover tools) can confirm them. The client already tolerates
  absent fields, but a rename would silently produce empty photos.
- **Rate limits:** nothing documented. The notebook has no throttling or retry
  code, which is consistent with none being enforced but does not prove it.
- **Value types:** GLOBE's data guide notes that API-out variables once returned
  as strings are now ints, floats and booleans (2020). The client's `_clean`
  stringifies everything, so it handles both, but this was not tested against
  real responses here.

## Worth trying when the network is available

The notebook also calls a **`country/` variant**:
`.../measureddate/country/?protocols=...&startdate=...&enddate=...&countrycode=<id>`
with ids from `https://api.globe.gov/search/dev/country/all/`. `client.py`
says geographic params on the base endpoint are ignored, so it downloads
~16k observations/year worldwide and clips to Hawaii locally. If the country
endpoint really filters server-side, a US-only pull would be a fraction of that.
Not implemented: the id format and behaviour for `land_covers` are unconfirmed,
and it must be tried live before the client depends on it.

Also unconfirmed: whether the dataset page's `observer.globe.gov/get-data`
sample scripts exist for land cover. A search of the GLOBE Data User Guide found
Python notebooks for Mosquito Habitat Mapper and a dust tutorial, none for land
cover.

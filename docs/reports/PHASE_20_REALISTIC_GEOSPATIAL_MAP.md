# Phase 20 — Realistic Geospatial Disaster Map

## Scope

This milestone upgrades PRISM's geographical visualization only. E1–E6
calculations, scenario execution, simulation state, allocation plans,
authority overrides, and audit writes were not redesigned or bypassed.

## Before and after

The previous `MapViewer` rendered a hand-projected SVG diagram using a fixed
longitude/latitude bounding box. It drew simplified polygons, lines, and
circles over a dark grid and assumed only the first polygon ring and selected
line coordinates. That presentation was useful as a schematic, but it was
not a geographically recognizable map and could not accurately represent
multi-part GeoJSON geometries.

The new viewer is MapLibre GL JS. It renders a Web Mercator map canvas with
provider-backed raster basemaps and PRISM's GeoJSON intelligence layers above
them. The backend remains the source of truth for all disaster and entity
geometry.

## Mapping technology and provider strategy

MapLibre was selected because it was already a frontend dependency, supports
raster and GeoJSON sources natively, provides GPU-rendered style layers, and
has the controls required for navigation, fullscreen, scale, and attribution.

The provider-neutral style supports:

- Satellite: Esri World Imagery raster tiles.
- Hybrid: Esri World Imagery plus Esri boundaries/places reference tiles.
- Streets fallback: OpenStreetMap raster tiles.

The endpoints are configurable through `apps/web/.env.example`:

- `NEXT_PUBLIC_MAP_SATELLITE_TILES`
- `NEXT_PUBLIC_MAP_STREETS_TILES`
- `NEXT_PUBLIC_MAP_LABEL_TILES`

No API key or provider secret is committed. Visible attribution is included in
the map and the default endpoints are public/demo-oriented services whose
usage, rate limits, and licensing must be reviewed before any operational
deployment.

## Geographical data now rendered

`GET /api/v1/dashboard/overview` now exposes additional read-only map layers
alongside the existing contract:

- `study_area_boundary`: the backend StudyArea polygon.
- `flood_polygons`: current flood extent.
- `predicted_flood_polygons`: existing prediction extent, including horizon,
  confidence, and method metadata when present.
- `red_zones`: backend risk geometry.
- `habitations`: backend habitation polygons.
- `habitation_points`: backend habitation centroids for stable labels/markers.
- `destinations`: backend evacuation destinations.
- `road_segments`: backend road and bridge geometry, including operational
  status and bridge properties.
- `active_routes`: backend route geometry and viability properties.

The added boundary, prediction, and centroid features are read-model
extensions. They do not alter hazard, routing, capacity, population, or
simulation calculations.

## Visual layers and interaction

The map uses distinct opacity, outline, and ordering rules for current flood,
predicted flood, high-risk zones, roads, closed road segments, evacuation
routes, habitation polygons/points, destinations, and the study boundary.
Closed roads are shown with a red dashed treatment; bridges retain a separate
visual emphasis. The map fits to backend geometry rather than a hardcoded
geographic extent.

The dedicated GIS workspace provides page-level visibility toggles for flood,
predicted flood, risk, habitations, destinations, roads, and routes. The map
also provides basemap selection, navigation, fullscreen, scale, north
indicator, legend, attribution, and feature popups. Popup content is escaped
before insertion into the MapLibre popup DOM.

## Coordinate handling

The dashboard API serializes map geometries as WGS84 GeoJSON (`EPSG:4326`),
consistent with the StudyArea contract. The frontend recursively walks
Point, MultiPoint, LineString, MultiLineString, Polygon, and MultiPolygon
coordinates for bounds calculation; it does not assume `coordinates[0]` is
always a ring or line. MapLibre performs display projection to Web Mercator
internally. Backend metric computations and the configured computational CRS
(`EPSG:32643`) remain unchanged.

## Files changed

- `apps/api/app/api/v1/dashboard.py`: adds read-only spatial layers to the
  existing dashboard response.
- `apps/web/src/components/MapViewer.tsx`: replaces the SVG schematic with a
  MapLibre source/layer map and provider-aware controls.
- `apps/web/src/app/map/page.tsx`: wires new layers and predicted-flood
  visibility into the dedicated workspace.
- `apps/web/src/app/globals.css`: styles escaped feature popups.
- `apps/web/.env.example`: documents provider endpoint configuration.

## Verification

- Backend module compilation passed.
- Focused backend regression suite passed: 6 tests.
- Dashboard endpoint manually verified with `SNAP_BASE_001`: all nine map
  layer collections returned, including one study boundary, one current flood
  feature, one predicted extent, and four habitation points.
- Frontend production build passed before the final layout correction. A
  subsequent local Next build encountered a Windows EPERM lock in generated
  `.next` output from the pre-existing development process; source typecheck
  and the earlier production build were successful. The stale process was
  replaced and the current dev server was browser-verified.
- Browser verification passed at `/map`: satellite imagery, streets fallback,
  layer controls, MapLibre navigation/fullscreen/scale/attribution controls,
  backend overlays, study boundary, labels, and entity markers rendered.
- No backend engine behavior or database writes were changed by this
  milestone.

## Known limitations

1. The current Vayu River Basin geometry and hazard values remain synthetic
   demonstration data; a realistic basemap does not make them real-world
   observations.
2. Public raster endpoints depend on network availability and provider
   policies. A deployment should use an approved, monitored tile provider or
   self-hosted cache and retain required attribution.
3. The current API exposes high-risk/red-zone geometry but does not yet expose
   independently styled moderate/low risk collections, observation stations,
   or bridge point features. The UI only displays layers actually supported by
   the API.
4. Basemap switching is client-side style visibility switching; it does not
   add offline tiles or guarantee imagery availability.
5. Popup verification is limited by the synthetic geometry and current
   browser viewport, but the click handlers and escaped popup path are wired
   to all supported feature layers.

## Follow-up boundary

Future work may add provider health telemetry, cached/offline tiles,
multi-resolution vector tiles, richer risk-class collections, and automated
map interaction tests. Those are intentionally outside this visualization-only
milestone and must not change the authoritative E1–E6 data flow without a
separate design review.

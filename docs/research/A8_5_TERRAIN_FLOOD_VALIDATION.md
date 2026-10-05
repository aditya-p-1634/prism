# PRISM Phase A.8.5 — Terrain & Historical Flood Validation Research Report
### Epistemic Audit, Cross-Source Spatial Consistency & Validation Readiness Decision

> **Epistemological Classification Guide:**
> - **[OBSERVED]**: Directly measured in the physical world by instruments or field observers.
> - **[SOURCE-DERIVED]**: Extracted directly from external reference files without algorithmic transformation.
> - **[COMPUTED]**: Deterministically calculated via mathematical or spatial operations on ingested data.
> - **[INFERRED]**: Formulated based on patterns, correlations, or scientific reasoning (not proven facts).
> - **[UNKNOWN]**: Critical parameters or semantics lacking verifiable documentation or empirical grounding.

---

## 1. Purpose
This research harness audits the historical evidence of the catastrophic December 2015 Chennai flood disaster. Its objective is to rigorously characterize FABDEM bare-earth terrain against independent empirical evidence (NRSC satellite/hydrodynamic flood layers, GCC municipal incident points, OSM flooded road networks, and municipal stagnation logs), evaluate spatial consistency across sources, and determine whether a terrain-aware experimental flood model is scientifically defensible.

**Strict Research Boundary**: This phase is an isolated research harness. It does **not** predict operational floods, does **not** alter PRISM production engines E1–E6, and does **not** convert unverified gauge stage into absolute water surface elevations.

## 2. Dataset Inventory
| Dataset Key | Filename | Provider | Geometry Type | Feature Count | Format |
|---|---|---|---|---|---|
| `fabdem` | `N13E080_FABDEM_V1-2.tif` | University of Bristol / FATHOM (FABDEM v1-2) | Raster / GeoTIFF | 12960000 | GeoTIFF |
| `nrsc_kml` | `7cb3cecf-a95a-4786-8032-9c7417655d24.kml` | National Remote Sensing Centre (NRSC) / Indian Space Research Organisation (ISRO) | Vector | 4001 | KML |
| `gcc_kml` | `31523c86-0ad1-42f5-b4d1-297daa4bbcd6.kml` | Greater Chennai Corporation (GCC) | Vector | 327 | KML |
| `kancheepuram_kml` | `3746a11e-620f-40e4-94a1-21ea8fe2a35e.kml` | Tamil Nadu District Administration (Kancheepuram District) | Vector | 139 | KML |
| `tiruvallur_kml` | `d8d3ac1d-b486-4446-bc76-3dff0af8cbdb.kml` | Tamil Nadu District Administration (Tiruvallur District) | Vector | 200 | KML |
| `stagnation_kml` | `db3840ff-9f33-43a3-b826-2f9dae1bcb78.kml` | Greater Chennai Corporation / Smart City Initiative | Vector | 753 | KML |
| `roads_kml` | `46d6c279-ae09-43a8-8691-7a5386f69e3a.kml` | OpenStreetMap / Disaster GIS Volunteer Community (Chennai 2015) | Vector | 7894 | KML |
| `reference_pdf` | `Adayar &Cooum Rivers.pdf` | National Remote Sensing Centre (NRSC) / Indian Space Research Organisation (ISRO) | Technical Report / PDF | 8 | PDF |

## 3. Provenance & Cryptographic Audit
| Filename | SHA-256 Checksum | Size (bytes) | Status |
|---|---|---|---|
| `N13E080_FABDEM_V1-2.tif` | `720c8ce4b994126ef1f369fb602aa5760ca2ef7128f363b55d016681bed3c7f9` | 6613279 | **AVAILABLE** |
| `7cb3cecf-a95a-4786-8032-9c7417655d24.kml` | `fa6943b2916d625dbc4de3b43cbe4d768a956b2f584fa3c73244fae32cee7a2a` | 5474779 | **AVAILABLE** |
| `31523c86-0ad1-42f5-b4d1-297daa4bbcd6.kml` | `19d579591cd74785ba9a40b1e36464a89dfabf129057c87589784bc25a86d2d0` | 288081 | **AVAILABLE** |
| `3746a11e-620f-40e4-94a1-21ea8fe2a35e.kml` | `97b31cef79a339f778dd0eb5e84fb770ea5fbfce5483cc31be5034ebdb351359` | 126033 | **AVAILABLE** |
| `d8d3ac1d-b486-4446-bc76-3dff0af8cbdb.kml` | `f89a2e53bfc43cdefe1f9a0d606e7fdd323669e973104fada61215f1bc10a3ec` | 140964 | **AVAILABLE** |
| `db3840ff-9f33-43a3-b826-2f9dae1bcb78.kml` | `5b7d79bc3ba0b59ef5b14b79d8eba65caa905eaf0f5f468b33a6177ffb16704e` | 513049 | **AVAILABLE** |
| `46d6c279-ae09-43a8-8691-7a5386f69e3a.kml` | `eb396c38f243ae4f54fd8dde40c6c5daabface91fb3e17b0975aa3964c9f167f` | 5502138 | **AVAILABLE** |
| `Adayar &Cooum Rivers.pdf` | `60f3d39454180a21731d72ecae64f1cc7be9dcec9cfab95aaffadd8f1ae4526b` | 859050 | **AVAILABLE** |

**Source Immutability Rule [COMPUTED]**: All source files remain 100% read-only and unaltered. No filenames, attributes, or records were overwritten.

## 4. CRS and Geometry QA
- **Source CRS [SOURCE-DERIVED]**: All ingested vector layers declare `EPSG:4326` (WGS 84 geographic coordinates).
- **Projected Metric CRS [COMPUTED]**: `EPSG:32644` (WGS 84 / UTM zone 44N).
  - *Justification*: Chennai (~80.2°E, 13.0°N) is centrally located in UTM Zone 44N (78°E to 84°E). Metric distance and area calculations achieve minimal distortion (<0.1%).
- **Area Calculation Rule [COMPUTED]**: Areas are strictly calculated in metric projection (m² and km²), never in square geographic degrees.

| Dataset | Total | Valid Geoms | Invalid | Empty/Null | Coordinates Sane? | Duplicate Points |
|---|---|---|---|---|---|---|
| `nrsc_raw` | 4001 | 4001 | 0 | 0/0 | Yes (Chennai Envelope) | 0 |
| `NRSC_PIXELVALUE_1` | 3392 | 3392 | 0 | 0/0 | Yes (Chennai Envelope) | 0 |
| `NRSC_PIXELVALUE_13` | 607 | 607 | 0 | 0/0 | Yes (Chennai Envelope) | 0 |
| `NRSC_NONZERO_COMPOSITE` | 3999 | 3999 | 0 | 0/0 | Yes (Chennai Envelope) | 0 |
| `gcc_hotspots` | 327 | 327 | 0 | 0/0 | Yes (Chennai Envelope) | 0 |
| `kancheepuram_hotspots` | 139 | 139 | 0 | 0/0 | Yes (Chennai Envelope) | 0 |
| `tiruvallur_hotspots` | 200 | 200 | 0 | 0/0 | Yes (Chennai Envelope) | 39 |
| `chennai_stagnation` | 753 | 753 | 0 | 0/0 | Yes (Chennai Envelope) | 0 |
| `road_network` | 7894 | 7894 | 0 | 0/0 | Yes (Chennai Envelope) | 0 |

## 5. NRSC Pixelvalue Findings
The public metadata accompanying the NRSC 2015 inundation layer identifies the vector polygons as the Chennai flood inundation zone, but **does NOT document the semantic meaning of `pixelvalue` 1 versus 13**.

- **[SOURCE-DERIVED] Observed raw counts**:
  - `pixelvalue = 1`: **3392** polygons
  - `pixelvalue = 13`: **607** polygons
  - `pixelvalue = 0`: **2** polygons

- **[UNKNOWN] Semantics**: Whether `13` represents deeper water, standing water, urban flood corridors, or high-confidence satellite detections is unverified.
- **[SCIENTIFIC MANDATE]**: Never assume `1 = flood` and `13 = permanent water` or vice versa. All analyses preserve the raw attributes.

## 6. NRSC Mask Sensitivity Analysis
Three explicitly named, source-derived masks were constructed:
1. `NRSC_PIXELVALUE_1`: Features where `pixelvalue == 1`
2. `NRSC_PIXELVALUE_13`: Features where `pixelvalue == 13`
3. `NRSC_NONZERO_COMPOSITE`: Composite where `pixelvalue in {1, 13}`

| Metric | Mask A (`NRSC_PIXELVALUE_1`) | Mask B (`NRSC_PIXELVALUE_13`) | Mask C (`NRSC_NONZERO_COMPOSITE`) |
|---|---|---|---|
| **Feature Count [SOURCE-DERIVED]** | 3392 | 607 | 3999 |
| **Valid Geometries [COMPUTED]** | 3392 | 607 | 3999 |
| **Invalid Geometries [COMPUTED]** | 0 | 0 | 0 |
| **Projected Metric Area [COMPUTED]** | 248.1575 km² | 68.3759 km² | 316.5335 km² |
| **FABDEM Overlap (km²) [COMPUTED]** | 91.1998 km² | 61.1698 km² | 152.3696 km² |
| **Chennai Core Overlap (km²) [COMPUTED]** | 40.2104 km² | 68.3759 km² | 108.5863 km² |

## 7. GCC Hotspot Point Spatial Consistency Analysis
Spatial containment testing of 327 GCC flood hotspot points across the three NRSC source-derived masks. Governed strictly by **Spatial Consistency Analysis** (NOT accuracy against ground truth).

### Overall Mask Consistency
| Mask | Total GCC Points | Inside Mask | Outside Mask | Hit Rate (%) |
|---|---|---|---|---|
| `NRSC_PIXELVALUE_1` | 327 | 13 | 314 | **3.98%** |
| `NRSC_PIXELVALUE_13` | 327 | 98 | 229 | **29.97%** |
| `NRSC_NONZERO_COMPOSITE` | 327 | 105 | 222 | **32.11%** |

### Stratified by GCC Inundation Category
| Inundation Category | Total Points | Inside Mask 1 (%) | Inside Mask 13 (%) | Inside Composite (%) |
|---|---|---|---|---|
| **<2 ft** | 202 | 4.95% | 30.2% | **32.18%** |
| **2–3 ft** | 1 | 0.0% | 0.0% | **0.0%** |
| **3–5 ft** | 86 | 3.49% | 24.42% | **27.91%** |
| **>5 ft** | 38 | 0.0% | 42.11% | **42.11%** |

- **[INFERRED] Spatial Consistency Observation**: Mask 13 shows substantially greater spatial consistency with the available urban GCC flood-hotspot and water-stagnation observations than Mask 1. The semantic meaning of source pixelvalue 1 versus 13 remains unresolved because the public source metadata does not define these classes.

## 8. FABDEM Terrain Characterization
FABDEM elevation was sampled at each GCC hotspot. Tile `N13E080_FABDEM_V1-2.tif` bounds terminate at latitude 13.00014°N. Consequently, **233** points fall within the tile and **94** points (in southern Chennai suburbs such as Velachery, Madipakkam, Tambaram) fall south of 13.0°N in the adjacent tile `N12E080`.

### GCC Hotspot Elevation Distribution by Category (meters)
| Inundation Category | Valid Samples | Min | Max | Mean | Median | Std Dev | p05 | p25 | p75 | p95 |
|---|---|---|---|---|---|---|---|---|---|---|
| **<2 ft** | 140 | 2.3m | 16.84m | 8.51m | 8.9m | 3.14m | 3.45m | 5.84m | 10.76m | 13.52m |
| **2–3 ft** | 1 | 15.63m | 15.63m | 15.63m | 15.63m | 0.0m | 15.63m | 15.63m | 15.63m | 15.63m |
| **3–5 ft** | 73 | 1.18m | 16.36m | 8.65m | 9.2m | 3.74m | 2.33m | 5.87m | 11.49m | 14.0m |
| **>5 ft** | 19 | 2.13m | 17.85m | 7.92m | 7.49m | 3.67m | 2.96m | 5.42m | 9.56m | 13.38m |
| **ALL SAMPLES** | 233 | 1.18m | 17.85m | 8.54m | 8.81m | 3.41m | 3.15m | 5.76m | 11.03m | 13.92m |

### NRSC Mask FABDEM Distribution: Inside vs Outside Study Area
To test whether a simple global elevation threshold could demarcate flooding, elevations inside each mask were compared against outside areas within the regional study box:
| Zone | Mask | Sample Count | Mean Elev | Median Elev | p05 | p95 |
|---|---|---|---|---|---|---|
| **Inside Mask** | `NRSC_PIXELVALUE_1` | 98753 | 16.66m | 15.88m | 2.63m | 32.86m |
| **Outside Study Area** | `NRSC_PIXELVALUE_1` | 1269858 | 15.73m | 14.22m | 0.0m | 32.75m |
| **Inside Mask** | `NRSC_PIXELVALUE_13` | 66205 | 8.38m | 8.79m | 2.9m | 12.49m |
| **Outside Study Area** | `NRSC_PIXELVALUE_13` | 1302406 | 16.17m | 15.0m | 0.0m | 32.95m |
| **Inside Mask** | `NRSC_NONZERO_COMPOSITE` | 164380 | 13.35m | 10.08m | 2.73m | 31.5m |
| **Outside Study Area** | `NRSC_NONZERO_COMPOSITE` | 1204231 | 16.13m | 15.0m | 0.0m | 32.96m |

- **[SCIENTIFIC MANDATE] Elevation Threshold Defensibility**: Inundated elevations inside Mask C range from -12m to 42m (mean 13.35m, median 10.08m), while dry areas outside range from 0m to 45m (mean 16.13m, median 15.00m). The observed elevation distributions demonstrate substantial overlap between historical inundation and surrounding terrain; therefore a single global DEM elevation threshold is not considered scientifically defensible for this study area.

## 9. Nandambakkam CheckDam Station Context Analysis
- **Station Code [SOURCE-DERIVED]**: `NANDAMBAKKAM_CHECKDAM`
- **River Basin [SOURCE-DERIVED]**: Adyar
- **Coordinates [SOURCE-DERIVED]**: 13.01611111° N, 80.18277778° E (`EPSG:4326`)
- **FABDEM Elevation at Station [COMPUTED]**: **5.1 m**
- **Proximity to NRSC Masks [COMPUTED]**:
  - Nearest Mask A (`NRSC_PIXELVALUE_1`): **14.26 m** (Point inside: False)
  - Nearest Mask B (`NRSC_PIXELVALUE_13`): **1320.85 m** (Point inside: False)
  - Nearest Mask C (`NRSC_NONZERO_COMPOSITE`): **14.26 m**
- **Nearby GCC Hotspots by Radius [COMPUTED]**:
  - Within 250 m: **0** points
  - Within 500 m: **1** points
  - Within 1000 m: **5** points
  - Within 2000 m: **10** points

**Strict Boundary Enforcement**:
1. The 3.25 m observed in telemetry is **gauge stage**, not Water Surface Elevation (WSE).
2. The vertical datum / gauge-zero elevation remains **unverified**.
3. Gauge stage must **never** be converted to WSE or subtracted from FABDEM elevation.
4. Gauge station flooding cannot be inferred merely from proximity to mask polygons.

## 10. Flooded-Road Network Cross-Check
Spatial consistency analysis between the Chennai 2015 road network (7894 features) and the NRSC source-derived masks.

| Mask | Flooded Roads Intersecting | Flooded Intersection Rate (%) | Non-Flooded Intersecting | Non-Flooded Rate (%) |
|---|---|---|---|---|
| `NRSC_PIXELVALUE_1` | 983 / 7884 | **12.47%** | 1 / 10 | **10.0%** |
| `NRSC_PIXELVALUE_13` | 2962 / 7884 | **37.57%** | 5 / 10 | **50.0%** |
| `NRSC_NONZERO_COMPOSITE` | 3827 / 7884 | **48.54%** | 6 / 10 | **60.0%** |

- **[SOURCE-DERIVED] Limitation**: Severe class imbalance exists (7,884 flooded vs 10 non-flooded segments). While Composite Mask intersects 48.6% of flooded road segments, this cross-check is descriptive consistency, not ground-truth validation.

## 11. Water-Stagnation Cross-Check
Testing 753 Chennai municipal water stagnation points against NRSC masks.

| Mask | Stagnation Points Inside | Outside | Hit Rate (%) |
|---|---|---|---|
| `NRSC_PIXELVALUE_1` | 21 | 732 | **2.79%** |
| `NRSC_PIXELVALUE_13` | 202 | 551 | **26.83%** |
| `NRSC_NONZERO_COMPOSITE` | 222 | 531 | **29.48%** |

- **[INFERRED] Insight**: Stagnation points represent localized urban drainage blockages and micro-ponding. Mask 13 shows substantially greater spatial consistency with the available urban GCC flood-hotspot and water-stagnation observations than Mask 1. The semantic meaning of source pixelvalue 1 versus 13 remains unresolved because the public source metadata does not define these classes.

## 12. Limitations
1. **Uncalibrated Hydrodynamic Simulation**: NRSC Version 1.2 reference document explicitly acknowledges lack of downstream discharge calibration data.
2. **Undocumented NRSC Pixelvalue Semantics**: The semantic meaning of pixelvalue 1 versus 13 remains unverified in public metadata.
3. **Unverified Gauge Datum**: Nandambakkam CheckDam stage of 3.25 m cannot be converted to absolute WSE because gauge zero is unverified.
4. **DEM Resolution Limits**: FABDEM 30 m spatial resolution cannot resolve roadside curbs, culverts, storm drains, or micro-embankments.
5. **Spatial Tile Truncation**: Tile N13E080 truncates at 13.00014°N, leaving 94 southern Chennai GCC hotspots outside the DEM footprint.
6. **Reporting Bias**: Road and GCC layers reflect crowdsourced or municipal reporting bias during active disaster conditions.

## 13. Scientific Interpretation
1. **Mask 1 vs Mask 13 Spatial Consistency**: Mask 13 shows substantially greater spatial consistency with the available urban GCC flood-hotspot and water-stagnation observations than Mask 1. The semantic meaning of source pixelvalue 1 versus 13 remains unresolved because the public source metadata does not define these classes.
2. **Global Elevation Threshold Defensibility**: The observed elevation distributions demonstrate substantial overlap between historical inundation and surrounding terrain; therefore a single global DEM elevation threshold is not considered scientifically defensible for this study area.
3. **Prohibition of Pseudo-IoU**: Calculating Intersection-over-Union (IoU) between two external reference layers and presenting it as model performance is scientifically indefensible. IoU must only be reported when evaluating an actual model prediction against verified benchmarks.

## 14. Validation Readiness Decision
### Final Machine-Readable Status: `CONDITIONAL_TERRAIN_EXPERIMENT`

**Scientific Rationale**:
> The historical evidence base is sufficient for terrain characterization and spatial consistency testing, but strictly INSUFFICIENT for operational flood forecasting or calibrated depth prediction. Validation status is CONDITIONAL upon preserving separate NRSC class masks, maintaining unverified gauge datum disclaimers, and avoiding global elevation bathtub models.

### Evidence Checklist
- **[PASS] dataset_availability**: All 8 research datasets located, hashed (SHA-256), and validated.
- **[PASS] spatial_qa**: All vector layers adhere to EPSG:4326 source CRS and fall within Chennai geographical coordinates.
- **[CONDITIONAL / RESTRICTED] nrsc_semantics_resolved**: Mask 13 shows substantially greater spatial consistency with the available urban GCC flood-hotspot and water-stagnation observations than Mask 1. The semantic meaning of source pixelvalue 1 versus 13 remains unresolved because the public source metadata does not define these classes.
- **[CONDITIONAL / RESTRICTED] gauge_datum_verified**: Nandambakkam CheckDam stage reading of 3.25 m cannot be converted to absolute Water Surface Elevation (WSE) because the station gauge-zero elevation relative to WGS84/EGM96 vertical datum is unverified. Direct subtraction from FABDEM is scientifically prohibited.
- **[PASS] independent_point_evidence**: 327 GCC hotspot points provide independent municipal point evidence; Composite NRSC mask encompasses 105 points (32.1% consistency rate).
- **[PASS] terrain_suitability**: FABDEM 30 m elevation successfully sampled for 233 points. 94 points in southern Chennai fall south of latitude 13.00014°N outside tile N13E080. 30 m resolution lacks street-level micro-drainage barriers, confirming that elevation alone cannot predict flooding.
- **[CONDITIONAL / RESTRICTED] prediction_mask_present**: No PRISM predicted inundation mask currently exists. NRSC polygons are historical reference layers, not model predictions. Reporting Intersection-over-Union (IoU) at this phase would constitute pseudo-accuracy.

### Explicit Boundary Prohibitions
- DO NOT report IoU as a model accuracy metric without a PRISM prediction mask.
- DO NOT convert Nandambakkam 3.25 m gauge stage to WSE without verified gauge zero.
- DO NOT subtract telemetry stage from FABDEM elevations.
- DO NOT create a single elevation threshold bathtub flood model.
- DO NOT claim NRSC polygons or GCC hotspots constitute absolute ground truth.
- DO NOT modify production E1-E6 decision logic based on experimental research outputs.

## 15. What Remains Unknown
1. **[UNKNOWN]** The exact elevation of Nandambakkam CheckDam gauge zero relative to EGM96 / WGS84 vertical datum.
2. **[UNKNOWN]** The exact algorithmic provenance of NRSC pixelvalue 1 versus 13 (whether 13 denotes radar backscatter threshold, water depth, or urban landcover overlay).
3. **[UNKNOWN]** Continuous water depth measurements across the GCC municipal hotspot points.
4. **[UNKNOWN]** Micro-topographic elevations for the 94 GCC points located in southern Chennai tile N12E080.

## 16. Recommended Next Phase (A.8.6 Proposal)
Before implementing a terrain-aware experimental flood model in PRISM Phase A.8.6, the following prerequisites are required:


- 1. Acquire surveyed gauge-zero elevation for Adyar River Nandambakkam CheckDam.
- 2. Acquire southern FABDEM tile N12E080 to cover the remaining 94 GCC hotspot points.
- 3. Obtain official NRSC metadata clarifying pixelvalue 1 versus 13 semantics.
- 4. Incorporate hydrodynamic river network connectivity rather than flat-plane elevation slicing.

**Production Safety Guarantee**: Experimental modeling in A.8.6 must remain strictly isolated within `app.research`, read-only, and completely detached from operational E1 red-zone generation and E2–E6 baseline snapshots.

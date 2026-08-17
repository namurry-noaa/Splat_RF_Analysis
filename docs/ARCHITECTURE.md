# Architecture & Phased Plan -- Splat_RF_Analysis

This document captures the design decisions and the staged build plan so the
project doesn't balloon and so future-you (or an agent) can pick up cleanly.

---

## Guiding principles

1. **Wrap the engine, don't rebuild it.** SPLAT! implements Longley-Rice/ITM
   correctly. We orchestrate it; we never reimplement propagation physics.
2. **One engine, frequency as a parameter.** VHF through UHF/GMRS is handled by
   ITM with frequency as input -- NOT a distinct model per band.
3. **Foliage/clutter is a separate, frequency-specific correction layer.** ITM
   models terrain only. Vegetation loss (large at UHF, band-dependent) is
   layered on top via empirical models (Weissberger, ITU-R P.833).
4. **PostGIS is the persistence + query keystone.** Compute in Python/SPLAT!,
   store spatially in PostGIS, visualize in QGIS (native connection).
5. **Open tool / private regional data**, enforced by `.gitignore` from day 0.

---

## Component responsibilities

| Component | Role |
|---|---|
| **SPLAT!** (system binary) | ITM terrain propagation: path profiles, coverage, diffraction. |
| **`srtm2sdf` / `usgs2sdf`** | Convert SRTM `.hgt` DEM tiles to SPLAT! `.sdf`. |
| **`splat_rf` (Python)** | Presets, drive SPLAT! (build `.qth`/`.lrp`, invoke, parse output), apply foliage correction, PostGIS I/O, batch/sweep. |
| **`models/foliage.py`** | Frequency-specific vegetation attenuation. |
| **PostGIS (`rf_analysis` schema)** | Terrain raster, sites, path profiles, coverage as queryable geometry. |
| **QGIS** | Visualization; connects natively to PostGIS. |

---

## Where frequency actually matters (the "models per band" question)

Not a separate propagation model per band. The breakdown:

- **ITM engine** -- frequency is an input parameter (valid ~20 MHz-20 GHz).
- **Fresnel zone size** -- scales with wavelength; clearance requirements
  differ by band (2 m zones are physically much larger than UHF). Computed,
  not modeled separately.
- **Diffraction** -- lower frequency diffracts around obstacles better; ITM
  handles this inherently.
- **Foliage / clutter attenuation** -- THIS is the genuinely band-specific
  piece, applied as a correction layer:
  - Higher freq (UHF/GMRS): more foliage loss -> ITU-R P.833.
  - Lower freq (VHF/2 m/rail): less loss, better penetration -> Weissberger.

So the per-band configuration lives in `config/bands.*.yml` (ITM params +
which foliage model), and the correction math lives in `models/foliage.py`.

---

## PostGIS schema (see `sql/01_schema.sql`)

Namespaced under `rf_analysis` in the existing `gis_dev` DB (PostGIS 3.6.4).
Geometry in SRID 4326 (WGS84, SRTM-native).

- `sites` (POINT) -- transmitters, targets, candidate relay spots.
  `antenna_height_m` (AGL) is flagged as the dominant LOS variable.
- `terrain_dem` (RASTER) -- optional SRTM in-DB for SQL terrain queries /
  viewsheds / slope (SPLAT! itself uses `.sdf` on disk).
- `path_profiles` (LINESTRING) -- point-to-point results: ITM loss, diffraction,
  layered foliage loss, Fresnel clearance, verdict (clear/marginal/obstructed).
- `coverage` (MULTIPOLYGON) -- area coverage contours per site/band/threshold.
- `viable_relays` (VIEW) -- example spatial payoff: candidate relay spots with
  a usable shot at a target, ordered by total loss. This is exactly the
  "which parking spot bridges me to the riverside repeater" query.

---

## Phased build plan

### Phase 0 -- Environment & smoke test  *(current)*
- [x] SPLAT! + utils installed (system: `splat` 1.4.2, `srtm2sdf`, etc.).
- [x] PostGIS available (`gis_dev`, PostGIS 3.6.4), GDAL present.
- [x] Repo scaffold, `.gitignore` (open/private separation), env, schema, configs.
- [ ] `conda env create -f environment.yml`.
- [ ] `psql -d gis_dev -f sql/01_schema.sql`.
- [ ] Acquire a few SRTM `.hgt` tiles for the AOI; `srtm2sdf` -> `.sdf`.
- [ ] Manual SPLAT! point-to-point run between two coords to prove the pipeline.

### Phase 1 -- Thin Python wrapper
- Load `*.local.yml` presets (sites/antennas/bands/database).
- Build SPLAT! inputs programmatically: `.qth` (site), `.lrp` (Longley-Rice
  params from band preset), `.az`/`.el` (antenna pattern) as needed.
- Invoke `splat`/`splat-hd`, parse the site/path report output.
- Goal: replace 15 CLI flags with `splat-rf path --tx home_repeater --rx riverside_repeater --band gmrs`.

### Phase 2 -- PostGIS integration
- SRTM tile fetcher (`requests`) -> `data/srtm/` -> `srtm2sdf` -> `data/sdf/`.
- Optional: load DEM into `terrain_dem` via `raster2pgsql`.
- Write path/coverage results into `path_profiles` / `coverage`.
- Confirm QGIS reads the `rf_analysis` layers.

### Phase 3 -- Foliage / clutter correction layer
- Implement ITU-R P.833 (currently a Weissberger-backed stub).
- Estimate foliage depth along a path (from land-cover data or manual segments).
- Add `total_loss_db = itm_loss + foliage_loss` into results; verdicts reflect it.

### Phase 4 -- Batch / sweep + public repo
- Sweep many candidate relay positions, rank by viability (`viable_relays`).
- Coverage-difference analyses (e.g., 2 m vs 70 cm over same area).
- Once the tool has shape and private data is cleanly separated -> GitHub
  (SSH auth; create remote when ready).

---

## Immediate next actions (for the setup agent)

1. `conda env create -f environment.yml && conda activate splat_rf`.
2. `psql -d gis_dev -f sql/01_schema.sql` (creates `rf_analysis` schema).
3. Fetch SRTM `.hgt` tile(s) covering the AOI; run `srtm2sdf` into `data/sdf/`.
4. Smoke test: a manual `splat` point-to-point path profile using two coords
   inside the loaded tiles; confirm terrain is read and a report/plot emits.

## Notes for later (operator follow-ups, not agent tasks)

- Run the real **riverside -> wooded AOI** path profile once terrain is loaded.
- Sweep candidate **mobile-relay parking spots** for a clear shot at riverside.
- Model any future **tower/mast height** change here before committing hardware
  (height is the dominant variable).

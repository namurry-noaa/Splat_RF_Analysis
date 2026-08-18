# Splat_RF_Analysis

Terrain-aware RF propagation analysis for VHF/UHF (amateur, GMRS, rail) using
real elevation data. A Python orchestration layer around **SPLAT!**
(Longley-Rice / Irregular Terrain Model) with a **per-band foliage/clutter
correction layer** and **PostGIS** persistence for spatial querying and QGIS
visualization.

## Why this exists

For VHF/UHF work in hilly, wooded terrain, coverage is **line-of-sight
limited** and dominated by **terrain geometry and antenna height** -- *not*
transmitter power. (Example: 20 W -> 45 W is only ~3.5 dB / ~half an S-unit,
while a single blocking ridge can cost 20-40+ dB of diffraction loss, and
foliage at 460 MHz adds several to many dB on top.) Answering "will site A
actually hit site B over these ridges?" requires software that reads real
terrain and computes path viability -- not eyeballing a paper map.

## Approach: wrap the engine, don't rebuild it

- **SPLAT!** already implements the Longley-Rice/ITM physics correctly.
  Rewriting it would be a months-long trap with no payoff. We drive it.
- **Frequency is a parameter**, not a separate model. One ITM engine handles
  2 m through 70 cm / GMRS by parameter.
- **Foliage/clutter is genuinely frequency-specific** and ITM does NOT model
  vegetation -- so it is applied as a **separate correction layer** on top of
  ITM output (Weissberger / ITU-R P.833). See `splat_rf/models/foliage.py`.
- **PostGIS is the keystone.** It turns ad-hoc runs into a queryable regional
  RF system: terrain as raster, sites/results as geometry, spatial queries
  (e.g., "which candidate relay spots have a usable shot at the repeater"),
  and native QGIS visualization.

```
SRTM tiles ──► PostGIS (raster terrain)
                   │
Python layer ──────┤ reads terrain, drives SPLAT!, applies foliage model
                   │
SPLAT! (ITM) ──► results ──► PostGIS (coverage/path geometry)
                                   │
                              QGIS (native PostGIS connection)
```

## Status

Early scaffold (Phase 0/1). SPLAT! is installed system-wide; PostGIS is
available locally. See `docs/ARCHITECTURE.md` for the phased plan.

## Layout

```
splat_rf/            Python package (orchestration layer)
  models/foliage.py  Frequency-specific foliage correction models
config/              Presets. *.example.* tracked; *.local.* PRIVATE/gitignored
  sites.example.yml      Sites, transmitters, relay candidates (COORDS PRIVATE)
  antennas.example.yml   Antenna presets (from public datasheets)
  bands.example.yml      Band / ITM parameter presets + foliage model choice
  database.example.yml   PostGIS connection template
sql/01_schema.sql    PostGIS schema (rf_analysis namespace)
data/srtm/           SRTM .hgt tiles (gitignored -- re-fetchable)
data/sdf/            SPLAT! .sdf terrain (gitignored -- derived)
outputs/             Path profiles, coverage maps, KML (gitignored)
docs/                Architecture / design notes
```

## Open tool / private data separation

The reusable tooling is public-friendly. **Your actual site coordinates,
operating locations, callsign, and DB credentials are private** and live only
in `*.local.*` files and the gitignored `data/` tree. Only `*.example.*`
templates are committed. This is enforced by `.gitignore` from day one so it
never has to be retrofitted before going public.

## Prerequisites (system)

- **SPLAT!** -- `sudo apt install splat` (provides `splat`, `splat-hd`,
  `srtm2sdf`, `usgs2sdf`). Verified installed: 1.4.2.
- **PostgreSQL + PostGIS** -- verified: PostGIS 3.6.4, DB `gis_dev`.
- **GDAL** -- verified: `gdalinfo`, `gdal_translate` present.

## Setup

```bash
# 1. Python environment
conda env create -f environment.yml
conda activate splat_rf

# 2. Database schema (into existing gis_dev, namespaced under rf_analysis)
psql -d gis_dev -f sql/01_schema.sql

# 3. Local config (COPY templates, fill in real values -- these stay private)
cp config/database.example.yml config/database.local.yml
cp config/sites.example.yml     config/sites.local.yml
cp config/antennas.example.yml  config/antennas.local.yml
cp config/bands.example.yml     config/bands.local.yml
# edit *.local.yml ...

# 4. Terrain data (Phase 1 fetcher -- see ARCHITECTURE.md)
#    Acquire SRTM .hgt tiles for the AOI -> convert to .sdf via srtm2sdf.
```

## License

**MIT License** — see [`LICENSE`](LICENSE). Copyright (c) 2026 Nate Murry.

Note on SPLAT!: this project *invokes* SPLAT! (`splat` / `splat-hd`) as a
separate command-line binary; it does not incorporate or link SPLAT!'s source
code. SPLAT! is independently licensed under the GNU GPL v2 by its author
(John Magliacane, KD2BD). Running a separately-licensed binary as an external
process does not extend SPLAT!'s copyleft to this MIT-licensed orchestration
layer.

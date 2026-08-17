-- ============================================================================
-- 01_schema.sql  --  PostGIS schema for Splat_RF_Analysis
-- ----------------------------------------------------------------------------
-- Creates the `rf_analysis` schema and core spatial tables. Run against the
-- target database (default: gis_dev, which already has PostGIS 3.6.4):
--
--   psql -d gis_dev -f sql/01_schema.sql
--
-- Design: keep all RF tables namespaced under rf_analysis so they don't
-- collide with other GIS work in the same database. Geometry stored in
-- SRID 4326 (WGS84) to match SRTM natively; reproject on the fly for
-- distance/area operations.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;

CREATE SCHEMA IF NOT EXISTS rf_analysis;
SET search_path TO rf_analysis, public;

-- ----------------------------------------------------------------------------
-- sites: transmitters, targets, candidate relay spots (POINT geometry)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rf_analysis.sites (
    id                SERIAL PRIMARY KEY,
    key               TEXT UNIQUE NOT NULL,      -- matches sites.local.yml key
    description       TEXT,
    role              TEXT,                       -- repeater|relay|mobile|target|candidate
    antenna_height_m  DOUBLE PRECISION,           -- AGL -- dominant LOS variable
    antenna_key       TEXT,                        -- -> antennas preset
    azimuth_deg       DOUBLE PRECISION,            -- boresight (true N), directional
    erp_watts         DOUBLE PRECISION,
    band_key          TEXT,                        -- -> bands preset
    geom              GEOMETRY(POINT, 4326) NOT NULL,
    created_at        TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sites_geom_gix ON rf_analysis.sites USING GIST (geom);

-- ----------------------------------------------------------------------------
-- terrain_dem: SRTM elevation as PostGIS raster (optional; SPLAT! uses .sdf,
-- but storing DEM here enables SQL-side terrain queries, viewsheds, slope).
-- Load via raster2pgsql; one row per tile.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rf_analysis.terrain_dem (
    id     SERIAL PRIMARY KEY,
    tile   TEXT,                                   -- e.g. 'N39W077'
    rast   RASTER,
    loaded_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS terrain_dem_rast_gix
    ON rf_analysis.terrain_dem USING GIST (ST_ConvexHull(rast));

-- ----------------------------------------------------------------------------
-- path_profiles: point-to-point analysis results (LINESTRING tx->rx)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rf_analysis.path_profiles (
    id                 SERIAL PRIMARY KEY,
    tx_site_key        TEXT NOT NULL,
    rx_site_key        TEXT NOT NULL,
    band_key           TEXT,
    frequency_mhz      DOUBLE PRECISION,
    distance_km        DOUBLE PRECISION,
    -- ITM / SPLAT! results:
    path_loss_db       DOUBLE PRECISION,           -- ITM predicted loss
    free_space_loss_db DOUBLE PRECISION,
    obstruction_db     DOUBLE PRECISION,           -- diffraction over terrain
    -- layered correction:
    foliage_loss_db    DOUBLE PRECISION,           -- from foliage model
    foliage_model      TEXT,
    total_loss_db      DOUBLE PRECISION,           -- ITM + foliage
    -- Fresnel:
    fresnel_clearance_ok BOOLEAN,                   -- 60% F1 clearance met?
    worst_fresnel_pct  DOUBLE PRECISION,
    -- verdict:
    los_status         TEXT,                        -- clear|marginal|obstructed
    geom               GEOMETRY(LINESTRING, 4326),
    run_at             TIMESTAMPTZ DEFAULT now(),
    notes              TEXT
);
CREATE INDEX IF NOT EXISTS path_profiles_geom_gix
    ON rf_analysis.path_profiles USING GIST (geom);

-- ----------------------------------------------------------------------------
-- coverage: area coverage footprints from SPLAT! (POLYGON / MULTIPOLYGON)
-- One row per coverage run; store the signal-level contour as geometry.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rf_analysis.coverage (
    id            SERIAL PRIMARY KEY,
    site_key      TEXT NOT NULL,
    band_key      TEXT,
    frequency_mhz DOUBLE PRECISION,
    signal_dbuv   DOUBLE PRECISION,                -- contour threshold level
    erp_watts     DOUBLE PRECISION,
    foliage_model TEXT,
    geom          GEOMETRY(MULTIPOLYGON, 4326),
    run_at        TIMESTAMPTZ DEFAULT now(),
    notes         TEXT
);
CREATE INDEX IF NOT EXISTS coverage_geom_gix
    ON rf_analysis.coverage USING GIST (geom);

-- ----------------------------------------------------------------------------
-- Convenience view: candidate relay spots with a usable shot at a target.
-- (Populated once path_profiles are computed; example of the SQL payoff.)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW rf_analysis.viable_relays AS
SELECT p.rx_site_key AS target,
       p.tx_site_key AS relay_candidate,
       p.distance_km,
       p.total_loss_db,
       p.los_status,
       s.geom
FROM rf_analysis.path_profiles p
JOIN rf_analysis.sites s ON s.key = p.tx_site_key
WHERE s.role = 'candidate'
  AND p.los_status IN ('clear', 'marginal')
ORDER BY p.total_loss_db ASC;

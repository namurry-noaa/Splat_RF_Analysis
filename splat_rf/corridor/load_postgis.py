#!/usr/bin/env python3
"""Load the Muddy Run corridor study into the gis_dev PostGIS instance
(rf_analysis schema) so it's queryable and QGIS-loadable.

Loads:
  * sites        : comm wagon (TX) + 16 HT waypoints (POINT geom)
  * path_profiles: 48 wagon->HT links (LINESTRING geom, per-band metrics +
                   foliage-corrected dBm and verdicts)

Idempotent: clears prior rows for this study's keys before inserting.
DB connection from config/database.local.yml (peer/.pgpass auth).
"""
from __future__ import annotations
import csv
import os
import yaml
import psycopg2
from psycopg2.extras import execute_values

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV = os.path.join(REPO, "studies", "muddy_run_corridor", "results.csv")
DBCFG = os.path.join(REPO, "config", "database.local.yml")

WAGON = {"key": "muddyrun_wagon", "lat": 39.8059656, "lon": -76.2963533,
         "height_m": 2.0, "role": "mobile", "desc": "Comm wagon mobile repeat TX, Muddy Run riverside"}


def connect():
    with open(DBCFG) as f:
        cfg = yaml.safe_load(f)["database"]
    conn = psycopg2.connect(
        host=cfg.get("host", "localhost"), port=cfg.get("port", 5432),
        dbname=cfg["dbname"], user=cfg["user"],
        password=cfg.get("password") or None)
    return conn, cfg.get("schema", "rf_analysis"), cfg.get("srid", 4326)


def main():
    with open(CSV) as f:
        rows = list(csv.DictReader(f))
    conn, schema, srid = connect()
    cur = conn.cursor()
    cur.execute(f"SET search_path TO {schema}, public;")

    # --- sites: wagon + waypoints ---
    site_keys = [WAGON["key"]]
    # clear prior study rows
    cur.execute("DELETE FROM sites WHERE key LIKE 'muddyrun_%';")
    cur.execute(
        "INSERT INTO sites (key, description, role, antenna_height_m, band_key, geom) "
        "VALUES (%s,%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),%s));",
        (WAGON["key"], WAGON["desc"], WAGON["role"], WAGON["height_m"], "multi",
         WAGON["lon"], WAGON["lat"], srid))

    seen = set()
    site_vals = []
    for r in rows:
        if not r["rx_lat"] or not r["rx_lon"]:
            continue
        key = f"muddyrun_ht_{r['direction'][0].lower()}{r['waypoint']}"
        if key in seen:
            continue
        seen.add(key)
        site_vals.append((key, f"HT waypoint {r['direction']} {r['waypoint']} ({r['path_km']} km)",
                          "target", 1.5, float(r["rx_lon"]), float(r["rx_lat"]), srid))
    execute_values(cur,
        "INSERT INTO sites (key, description, role, antenna_height_m, geom) VALUES %s",
        site_vals,
        template="(%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),%s))")

    # --- path_profiles: 48 links ---
    cur.execute("DELETE FROM path_profiles WHERE tx_site_key = %s;", (WAGON["key"],))
    pp_vals = []
    for r in rows:
        if not r["rx_lat"] or not r["rx_lon"]:
            # interpolated point w/o geom: still store metrics, no geom line
            geom = None
        else:
            geom = (WAGON["lon"], WAGON["lat"], float(r["rx_lon"]), float(r["rx_lat"]))
        rx_key = f"muddyrun_ht_{r['direction'][0].lower()}{r['waypoint']}"
        def n(v):
            return float(v) if v not in ("", None) else None
        pp_vals.append((
            WAGON["key"], rx_key, r["band"], n(r["freq_mhz"]), n(r["path_km"]),
            n(r["itwom_loss_db"]), n(r["terrain_shield_db"]),
            n(r["dbm_terrain"]), n(r["dbm_summer"]), n(r["dbm_leafoff"]),
            r["verdict_terrain"], r["verdict_summer"], r["verdict_leafoff"],
            r["prop_mode"], r["interpolated"] == "True",
            geom))
    # Extend path_profiles with study-specific columns if not present.
    cur.execute("""
        ALTER TABLE path_profiles
          ADD COLUMN IF NOT EXISTS dbm_terrain     DOUBLE PRECISION,
          ADD COLUMN IF NOT EXISTS dbm_summer      DOUBLE PRECISION,
          ADD COLUMN IF NOT EXISTS dbm_leafoff     DOUBLE PRECISION,
          ADD COLUMN IF NOT EXISTS verdict_terrain TEXT,
          ADD COLUMN IF NOT EXISTS verdict_summer  TEXT,
          ADD COLUMN IF NOT EXISTS verdict_leafoff TEXT,
          ADD COLUMN IF NOT EXISTS prop_mode       TEXT,
          ADD COLUMN IF NOT EXISTS interpolated    BOOLEAN;
    """)
    for v in pp_vals:
        (txk, rxk, band, freq, dist, itwom, terr, dterr, dsum, dleaf,
         vterr, vsum, vleaf, mode, interp, geom) = v
        if geom:
            geom_sql = ("ST_SetSRID(ST_MakeLine(ST_MakePoint(%s,%s),ST_MakePoint(%s,%s)),%s)")
            cur.execute(f"""
                INSERT INTO path_profiles
                  (tx_site_key, rx_site_key, band_key, frequency_mhz, distance_km,
                   path_loss_db, obstruction_db, dbm_terrain, dbm_summer, dbm_leafoff,
                   verdict_terrain, verdict_summer, verdict_leafoff, prop_mode,
                   interpolated, los_status, total_loss_db, geom)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s,
                        {geom_sql})
            """, (txk, rxk, band, freq, dist, itwom, terr, dterr, dsum, dleaf,
                  vterr, vsum, vleaf, mode, interp, vsum, itwom,
                  geom[0], geom[1], geom[2], geom[3], srid))
        else:
            cur.execute("""
                INSERT INTO path_profiles
                  (tx_site_key, rx_site_key, band_key, frequency_mhz, distance_km,
                   path_loss_db, obstruction_db, dbm_terrain, dbm_summer, dbm_leafoff,
                   verdict_terrain, verdict_summer, verdict_leafoff, prop_mode,
                   interpolated, los_status, total_loss_db)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s)
            """, (txk, rxk, band, freq, dist, itwom, terr, dterr, dsum, dleaf,
                  vterr, vsum, vleaf, mode, interp, vsum, itwom))

    conn.commit()
    cur.execute("SELECT count(*) FROM sites WHERE key LIKE 'muddyrun_%';")
    ns = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM path_profiles WHERE tx_site_key=%s;", (WAGON["key"],))
    npp = cur.fetchone()[0]
    print(f"Loaded: {ns} sites, {npp} path_profiles into {schema} (SRID {srid}).")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

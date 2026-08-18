#!/usr/bin/env python3
"""Trace the Susquehanna river corridor N and S from the comm-wagon point by
following the local low ground (river channel) in the NASADEM DEM.

Approach: start at the wagon coord. Step in the general along-river bearing
(river here runs roughly NW<->SE). At each step, look at a fan of candidate
next-points and pick the one that stays lowest (the river/valley floor),
constrained to keep moving generally N or generally S. Record waypoints at
~1 km spacing out to the requested distance.

Reads the NASADEM .hgt directly (SRTMHGT via rasterio/GDAL).
Outputs waypoint lists we then feed to splat-hd as .qth RX sites.
"""
from __future__ import annotations
import math
import rasterio

HGT = "/data/splat/hgt/N39W077.hgt"  # covers lat 39..40, lon -77..-76
WAGON_LAT = 39.8059656
WAGON_LON = -76.2963533

# River trends ~NW-SE through Muddy Run / Wissler area. "North" travel = head
# up-river (toward NW-ish); "South" = down-river (toward SE-ish). We let the
# low-ground follower find the exact channel; we only bias the hemisphere.
STEP_M = 250.0          # follow-step length (fine, to hug the channel)
WAYPOINT_EVERY_M = 1000 # record a waypoint each ~1 km
MAX_DIST_M = 8000.0     # 8 km (~5 mi) each direction

def m_per_deg_lat():
    return 111_320.0

def m_per_deg_lon(lat):
    return 111_320.0 * math.cos(math.radians(lat))

def elev(ds, band, lat, lon):
    try:
        row, col = ds.index(lon, lat)
        v = band[row, col]
        return float(v)
    except Exception:
        return float("nan")

def step_latlon(lat, lon, bearing_deg, dist_m):
    br = math.radians(bearing_deg)
    dlat = (dist_m * math.cos(br)) / m_per_deg_lat()
    dlon = (dist_m * math.sin(br)) / m_per_deg_lon(lat)
    return lat + dlat, lon + dlon

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

def trace(ds, band, base_bearing, label):
    """Follow low ground. base_bearing ~ general travel direction (deg from N).
    At each step try candidate bearings within +/-70 deg of base_bearing and
    pick the lowest-elevation next cell (river channel following)."""
    lat, lon = WAGON_LAT, WAGON_LON
    traveled = 0.0
    next_wp_at = WAYPOINT_EVERY_M
    waypoints = []
    path = [(lat, lon, elev(ds, band, lat, lon))]
    while traveled < MAX_DIST_M:
        best = None
        for db in range(-70, 71, 5):
            b = (base_bearing + db) % 360
            nlat, nlon = step_latlon(lat, lon, b, STEP_M)
            e = elev(ds, band, nlat, nlon)
            if math.isnan(e):
                continue
            # prefer low ground, but keep near base bearing (small penalty)
            score = e + 0.02 * abs(db)
            if best is None or score < best[0]:
                best = (score, nlat, nlon, e, b)
        if best is None:
            break
        _, nlat, nlon, e, b = best
        traveled += STEP_M
        lat, lon = nlat, nlon
        path.append((lat, lon, e))
        if traveled >= next_wp_at:
            waypoints.append((round(traveled/1000, 2), lat, lon, e))
            next_wp_at += WAYPOINT_EVERY_M
    return waypoints, path

def main():
    with rasterio.open(HGT) as ds:
        band = ds.read(1)
        w_elev = elev(ds, band, WAGON_LAT, WAGON_LON)
        print(f"Wagon: {WAGON_LAT:.6f}, {WAGON_LON:.6f}  elev={w_elev:.0f} m AMSL")
        print(f"DEM: {HGT}  size={ds.width}x{ds.height}")
        print()
        # North/up-river ~ NW (bearing ~325). South/down-river ~ SE (~145).
        for base_bearing, label in [(325, "NORTH"), (145, "SOUTH")]:
            wps, path = trace(ds, band, base_bearing, label)
            print(f"=== {label} (base bearing {base_bearing}) ===")
            for km, lat, lon, e in wps:
                print(f"  {km:>4.1f} km  {lat:.6f}, {lon:.6f}  elev={e:.0f} m")
            print()

if __name__ == "__main__":
    main()

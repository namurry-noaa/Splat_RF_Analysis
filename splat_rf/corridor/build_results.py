#!/usr/bin/env python3
"""Parse the SPLAT! p2p reports for the Muddy Run corridor study into a tidy
CSV, then apply the two-season Weissberger foliage correction.

Reads:  ~/Radio/splat/mobile_woods/p2p/{band}_{dir}{k}.txt   (SPLAT reports)
Writes: studies/muddy_run_corridor/results.csv

Terrain-only figures come straight from ITWOM; foliage columns are added on
top per the study's summer / leaf-off depth estimates (see study.yml).
"""
from __future__ import annotations
import csv
import os
import re
import sys

# Allow importing the foliage model from the package.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from splat_rf.models.foliage import weissberger_loss_db  # noqa: E402

P2P = os.path.expanduser("~/Radio/splat/mobile_woods/p2p")
OUT = os.path.join(REPO, "studies", "muddy_run_corridor", "results.csv")

BANDS = {"gmrs": 462.6, "2m": 146.1, "aar": 161.0}
SUMMER_DEPTH_M = 30.0
LEAF_OFF_DEPTH_M = 10.0
THR = {"solid": -100.0, "usable": -110.0, "marginal": -118.0}

# N4 stalled in ITWOM (double-horizon edge case). Interpolate dBm from N3/N5.
INTERP = {"n4"}


def classify(dbm):
    if dbm is None:
        return "NO-DATA"
    if dbm >= THR["solid"]:
        return "SOLID"
    if dbm >= THR["usable"]:
        return "USABLE"
    if dbm >= THR["marginal"]:
        return "MARGINAL"
    return "DEAD"


def parse(path):
    d = {"dist_km": None, "itwom_db": None, "terr_db": None,
         "dbm": None, "mode": None, "rx_lat": None, "rx_lon": None}
    with open(path, encoding="latin-1") as f:
        txt = f.read()
    def g(pat, cast=float):
        m = re.search(pat, txt)
        return cast(m.group(1)) if m else None
    d["dist_km"] = g(r"Distance to .*?: ([\d.]+) kilometers")
    d["itwom_db"] = g(r"ITWOM Version 3\.0 path loss: ([\d.]+) dB")
    d["terr_db"] = g(r"terrain shielding: ([\d.]+) dB")
    d["dbm"] = g(r"Signal power level at .*?: (-?[\d.]+) dBm")
    m = re.search(r"Mode of propagation: (.+)", txt)
    d["mode"] = m.group(1).strip() if m else None
    # RX site location line (second "Site location")
    locs = re.findall(r"Site location: ([\d.]+) North / ([\d.]+) West", txt)
    if len(locs) >= 2:
        d["rx_lat"] = float(locs[1][0])
        d["rx_lon"] = -float(locs[1][1])  # back to negative-west
    return d


def main():
    rows = []
    for band, freq in BANDS.items():
        for dl in ("n", "s"):
            # first pass: collect dbm by k for interpolation
            dbm_by_k = {}
            recs = {}
            for k in range(1, 9):
                p = os.path.join(P2P, f"{band}_{dl}{k}.txt")
                if os.path.exists(p) and os.path.getsize(p) > 0:
                    recs[k] = parse(p)
                    dbm_by_k[k] = recs[k]["dbm"]
            for k in range(1, 9):
                key = f"{dl}{k}"
                if k in recs:
                    r = recs[k]
                    interp = False
                else:
                    # interpolate dbm/dist from neighbors (k-1, k+1)
                    lo = dbm_by_k.get(k - 1)
                    hi = dbm_by_k.get(k + 1)
                    dbm = (lo + hi) / 2 if (lo is not None and hi is not None) else None
                    r = {"dist_km": float(k), "itwom_db": None, "terr_db": None,
                         "dbm": dbm, "mode": "interpolated (ITWOM edge case)",
                         "rx_lat": None, "rx_lon": None}
                    interp = True
                # foliage (excess loss subtracted from received dBm)
                summer = weissberger_loss_db(freq, SUMMER_DEPTH_M)
                leafoff = weissberger_loss_db(freq, LEAF_OFF_DEPTH_M)
                dbm_terr = r["dbm"]
                dbm_summer = (dbm_terr - summer) if dbm_terr is not None else None
                dbm_leafoff = (dbm_terr - leafoff) if dbm_terr is not None else None
                rows.append({
                    "band": band,
                    "freq_mhz": freq,
                    "direction": "NORTH" if dl == "n" else "SOUTH",
                    "waypoint": k,
                    "corridor_km": k * 1.0,      # nominal ~1km spacing along corridor
                    "path_km": round(r["dist_km"], 3) if r["dist_km"] else k * 1.0,
                    "rx_lat": r["rx_lat"],
                    "rx_lon": r["rx_lon"],
                    "itwom_loss_db": r["itwom_db"],
                    "terrain_shield_db": r["terr_db"],
                    "dbm_terrain": round(dbm_terr, 1) if dbm_terr is not None else None,
                    "foliage_summer_db": round(summer, 1),
                    "foliage_leafoff_db": round(leafoff, 1),
                    "dbm_summer": round(dbm_summer, 1) if dbm_summer is not None else None,
                    "dbm_leafoff": round(dbm_leafoff, 1) if dbm_leafoff is not None else None,
                    "verdict_terrain": classify(dbm_terr),
                    "verdict_summer": classify(dbm_summer),
                    "verdict_leafoff": classify(dbm_leafoff),
                    "prop_mode": r["mode"],
                    "interpolated": interp,
                })
    cols = list(rows[0].keys())
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {OUT}")
    # quick summary print
    for band in BANDS:
        s = weissberger_loss_db(BANDS[band], SUMMER_DEPTH_M)
        l = weissberger_loss_db(BANDS[band], LEAF_OFF_DEPTH_M)
        print(f"  {band:>4} {BANDS[band]:>6} MHz  foliage summer={s:.1f}dB  leaf-off={l:.1f}dB  (Δ={s-l:.1f}dB)")


if __name__ == "__main__":
    main()

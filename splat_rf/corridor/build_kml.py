#!/usr/bin/env python3
"""Build a Google Earth / QGIS-loadable KML of the Muddy Run corridor study:
  * comm wagon placemark
  * HT waypoints N1-N8, S1-S8, one folder per band, colored by SUMMER verdict
  * a path line linking wagon->waypoints per direction

One KML per band (clean to toggle). Writes to reports/figures/kml/.
Coverage rasters are provided separately as SPLAT's own .kml ground overlays.
"""
from __future__ import annotations
import csv
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV = os.path.join(REPO, "studies", "muddy_run_corridor", "results.csv")
OUTDIR = os.path.join(REPO, "reports", "figures", "kml")
os.makedirs(OUTDIR, exist_ok=True)

WAGON = (39.8059656, -76.2963533)
BAND_LABEL = {"gmrs": "GMRS 462.6", "2m": "2m 146.1", "aar": "AAR 161.0"}

# KML colors are aabbggrr (alpha, blue, green, red).
VERDICT_COLOR = {
    "SOLID":    "ff00c800",  # green
    "USABLE":   "ff00d2ff",  # yellow/amber
    "MARGINAL": "ff0080ff",  # orange
    "DEAD":     "ff0000ff",  # red
    "NO-DATA":  "ff808080",  # grey
}


def fnum(v):
    return float(v) if v not in ("", None) else None


def placemark(name, lat, lon, desc, color):
    return f"""    <Placemark>
      <name>{name}</name>
      <description><![CDATA[{desc}]]></description>
      <Style><IconStyle><color>{color}</color><scale>1.0</scale>
        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/wht-blank.png</href></Icon>
      </IconStyle></Style>
      <Point><coordinates>{lon:.7f},{lat:.7f},0</coordinates></Point>
    </Placemark>
"""


def build_band(rows, band):
    brows = [r for r in rows if r["band"] == band]
    parts = [f'<?xml version="1.0" encoding="UTF-8"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
             f"<name>Muddy Run corridor - {BAND_LABEL[band]}</name>"]
    # wagon
    parts.append(placemark("Comm Wagon (TX)", WAGON[0], WAGON[1],
                           f"Mobile repeat TX, {BAND_LABEL[band]}", "ffff0000"))
    for direction in ("NORTH", "SOUTH"):
        parts.append(f"<Folder><name>{direction}</name>")
        drows = sorted([r for r in brows if r["direction"] == direction],
                       key=lambda r: int(r["waypoint"]))
        # path line
        coords = [f"{WAGON[1]:.7f},{WAGON[0]:.7f},0"]
        for r in drows:
            la, lo = fnum(r["rx_lat"]), fnum(r["rx_lon"])
            if la and lo:
                coords.append(f"{lo:.7f},{la:.7f},0")
        parts.append(f"""<Placemark><name>{direction} corridor</name>
          <Style><LineStyle><color>ffcccccc</color><width>2</width></LineStyle></Style>
          <LineString><coordinates>{' '.join(coords)}</coordinates></LineString></Placemark>""")
        # waypoints colored by summer verdict
        for r in drows:
            la, lo = fnum(r["rx_lat"]), fnum(r["rx_lon"])
            if not (la and lo):
                continue
            desc = (f"{BAND_LABEL[band]} | {direction} WP{r['waypoint']}<br/>"
                    f"path {r['path_km']} km<br/>"
                    f"dBm terrain: {r['dbm_terrain']}<br/>"
                    f"dBm summer:  {r['dbm_summer']} ({r['verdict_summer']})<br/>"
                    f"dBm leaf-off:{r['dbm_leafoff']} ({r['verdict_leafoff']})<br/>"
                    f"mode: {r['prop_mode']}")
            color = VERDICT_COLOR.get(r["verdict_summer"], VERDICT_COLOR["NO-DATA"])
            parts.append(placemark(f"{direction[0]}{r['waypoint']} {r['verdict_summer']}",
                                   la, lo, desc, color))
        parts.append("</Folder>")
    parts.append("</Document></kml>")
    out = os.path.join(OUTDIR, f"corridor_{band}.kml")
    with open(out, "w") as f:
        f.write("\n".join(parts))
    print(f"wrote {out}")


def main():
    with open(CSV) as f:
        rows = list(csv.DictReader(f))
    for band in ("gmrs", "2m", "aar"):
        build_band(rows, band)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build presentable coverage figures for the Muddy Run corridor study.

Two figure families, one set per band (gmrs / 2m / aar):

  (A) coverage_relief_<band>.png
      SPLAT color-terrain-relief coverage raster (dBm signal contours over
      shaded terrain), cropped to the coverage vicinity, with a proper dBm
      color legend, wagon + corridor waypoints overlaid, scale bar, N arrow.
      Emulates the qsl.net SPLAT annotated-map look.

  (B) coverage_contour_<band>.png
      Clean matplotlib DEM contour map (from NASADEM) of the same window with
      the corridor waypoints colored by SUMMER verdict + wagon marker.

Reads the SPLAT .ppm from the scratch working dir; DEM from /data; results CSV
from the repo. Writes PNGs into reports/figures/.
"""
from __future__ import annotations
import csv
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from PIL import Image
import rasterio

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRATCH = os.path.expanduser("~/Radio/splat/mobile_woods")
DEM = "/data/splat/hgt/N39W077.hgt"
CSV = os.path.join(REPO, "studies", "muddy_run_corridor", "results.csv")
FIGDIR = os.path.join(REPO, "reports", "figures")
os.makedirs(FIGDIR, exist_ok=True)

WAGON = (39.8059656, -76.2963533)
BAND_LABEL = {"gmrs": "GMRS 462.6 MHz", "2m": "2 m 146.1 MHz", "aar": "AAR 161.0 MHz"}

# The SPLAT tile 39:40:76:77 spans lat 39..40 (top=40N) and lon 76..77
# (left edge = 77W). 3600 px per degree.
TILE_TOP_LAT = 40.0
TILE_LEFT_LONW = 77.0   # west-positive
PPD = 3600

# Display window (deg) around the wagon -- ~ +-0.05 deg (~5.5 km) to frame 5km coverage.
WIN_DEG = 0.055

# SPLAT .dcf dBm color key (dBm : (r,g,b)) -- from the auto-generated .dcf.
DCF = [
    (0, (255, 0, 0)), (-10, (255, 128, 0)), (-20, (255, 165, 0)),
    (-30, (255, 206, 0)), (-40, (255, 255, 0)), (-50, (184, 255, 0)),
    (-60, (0, 255, 0)), (-70, (0, 208, 0)), (-80, (0, 196, 196)),
    (-90, (0, 148, 255)), (-100, (80, 80, 255)), (-110, (0, 38, 255)),
    (-120, (142, 63, 255)), (-130, (196, 54, 255)), (-140, (255, 0, 255)),
    (-150, (255, 194, 204)),
]

VERDICT_COLOR = {"SOLID": "#1a9c1a", "USABLE": "#e6b800",
                 "MARGINAL": "#e67300", "DEAD": "#cc0000", "NO-DATA": "#888888"}


def latlon_to_px(lat, lonw):
    """lat/lon(west-positive) -> (col,row) in the 3600x3600 tile."""
    row = int(round((TILE_TOP_LAT - lat) * PPD))
    col = int(round((TILE_LEFT_LONW - lonw) * PPD))
    return col, row


def load_results():
    with open(CSV) as f:
        return list(csv.DictReader(f))


def band_waypoints(rows, band):
    pts = []
    for r in rows:
        if r["band"] != band:
            continue
        if not r["rx_lat"] or not r["rx_lon"]:
            continue
        pts.append((float(r["rx_lat"]), float(r["rx_lon"]),
                    r["direction"], int(r["waypoint"]), r["verdict_summer"]))
    return pts


# --------------------------------------------------------------------------
# (A) SPLAT relief coverage + legend + overlays
# --------------------------------------------------------------------------
def make_relief(band, rows):
    ppm = os.path.join(SCRATCH, f"wagon_{band}_relief.ppm")
    im = Image.open(ppm).convert("RGB")
    wlon = WAGON[1] * -1  # to west-positive
    cx, cy = latlon_to_px(WAGON[0], -WAGON[1])
    halfpx = int(WIN_DEG * PPD)
    box = (cx - halfpx, cy - halfpx, cx + halfpx, cy + halfpx)
    crop = im.crop(box)

    # map extent in normal (neg-west) lon for plotting
    lat_top = WAGON[0] + WIN_DEG
    lat_bot = WAGON[0] - WIN_DEG
    lon_left = WAGON[1] - WIN_DEG
    lon_right = WAGON[1] + WIN_DEG
    extent = [lon_left, lon_right, lat_bot, lat_top]

    fig, ax = plt.subplots(figsize=(7.2, 6.6))
    ax.imshow(np.asarray(crop), extent=extent, aspect="auto", origin="upper")

    # overlay wagon + waypoints
    ax.plot(WAGON[1], WAGON[0], marker="*", ms=17, color="white",
            markeredgecolor="black", mew=1.2, zorder=5, label="Comm wagon (TX)")
    for lat, lon, direction, wp, verdict in band_waypoints(rows, band):
        ax.plot(lon, lat, marker="o", ms=6,
                color=VERDICT_COLOR.get(verdict, "#888"),
                markeredgecolor="black", mew=0.6, zorder=6)
        ax.annotate(f"{direction[0]}{wp}", (lon, lat),
                    textcoords="offset points", xytext=(4, 3),
                    fontsize=6.5, color="white",
                    path_effects=None, zorder=7)

    ax.set_xlabel("Longitude", fontsize=8)
    ax.set_ylabel("Latitude", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_title(f"{BAND_LABEL[band]} — predicted signal coverage\n"
                 f"(SPLAT! ITWOM, RX 1.5 m AGL; terrain-only)", fontsize=10)

    # north arrow
    ax.annotate("N", xy=(0.96, 0.93), xytext=(0.96, 0.82),
                xycoords="axes fraction", ha="center", fontsize=11, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1.5))

    # scale bar (~1 km). 1 km in lon-deg at this lat:
    km_deg_lon = 1.0 / (111.320 * np.cos(np.radians(WAGON[0])))
    x0 = lon_left + 0.12 * (lon_right - lon_left)
    y0 = lat_bot + 0.06 * (lat_top - lat_bot)
    ax.plot([x0, x0 + km_deg_lon], [y0, y0], color="black", lw=3)
    ax.text(x0 + km_deg_lon / 2, y0 + 0.004 * (lat_top - lat_bot), "1 km",
            ha="center", va="bottom", fontsize=7.5)

    # dBm legend (discrete swatches)
    handles = []
    for dbm, (r, g, b) in DCF[:13]:  # +0 down to -120 dBm is the useful span
        handles.append(Rectangle((0, 0), 1, 1, fc=(r/255, g/255, b/255),
                                  ec="none", label=f"{dbm} dBm"))
    leg1 = ax.legend(handles=handles, title="Signal level", loc="upper left",
                     bbox_to_anchor=(1.01, 1.0), fontsize=6.5, title_fontsize=7,
                     frameon=True)
    ax.add_artist(leg1)
    # verdict legend
    vhandles = [Line2D([], [], marker="o", ls="", color=VERDICT_COLOR[v],
                       markeredgecolor="black", label=v)
                for v in ("SOLID", "USABLE", "MARGINAL", "DEAD")]
    vhandles.insert(0, Line2D([], [], marker="*", ls="", color="white",
                              markeredgecolor="black", ms=12, label="Wagon (TX)"))
    ax.legend(handles=vhandles, title="HT verdict (summer)", loc="lower left",
              bbox_to_anchor=(1.01, 0.0), fontsize=6.5, title_fontsize=7, frameon=True)

    fig.tight_layout()
    out = os.path.join(FIGDIR, f"coverage_relief_{band}.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


# --------------------------------------------------------------------------
# (B) clean DEM contour map + verdict waypoints
# --------------------------------------------------------------------------
def make_contour(band, rows):
    lat_top = WAGON[0] + WIN_DEG
    lat_bot = WAGON[0] - WIN_DEG
    lon_left = WAGON[1] - WIN_DEG
    lon_right = WAGON[1] + WIN_DEG
    with rasterio.open(DEM) as ds:
        r0, c0 = ds.index(lon_left, lat_top)
        r1, c1 = ds.index(lon_right, lat_bot)
        r0, r1 = sorted((r0, r1))
        c0, c1 = sorted((c0, c1))
        window = ((r0, r1), (c0, c1))
        dem = ds.read(1, window=window).astype(float)
    dem[dem < -1000] = np.nan

    fig, ax = plt.subplots(figsize=(7.0, 6.6))
    extent = [lon_left, lon_right, lat_bot, lat_top]
    im = ax.imshow(dem, extent=extent, origin="upper", cmap="terrain", aspect="auto")
    cs = ax.contour(np.linspace(lon_left, lon_right, dem.shape[1]),
                    np.linspace(lat_top, lat_bot, dem.shape[0]),
                    dem, levels=12, colors="k", linewidths=0.4, alpha=0.5)
    ax.clabel(cs, inline=True, fontsize=5, fmt="%d")

    ax.plot(WAGON[1], WAGON[0], marker="*", ms=17, color="white",
            markeredgecolor="black", mew=1.2, zorder=5)
    for lat, lon, direction, wp, verdict in band_waypoints(rows, band):
        ax.plot(lon, lat, marker="o", ms=7,
                color=VERDICT_COLOR.get(verdict, "#888"),
                markeredgecolor="black", mew=0.7, zorder=6)
        ax.annotate(f"{direction[0]}{wp}", (lon, lat),
                    textcoords="offset points", xytext=(4, 3), fontsize=6.5, zorder=7)

    cb = fig.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
    cb.set_label("Elevation (m AMSL)", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    ax.set_xlabel("Longitude", fontsize=8)
    ax.set_ylabel("Latitude", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_title(f"{BAND_LABEL[band]} — corridor & terrain\n"
                 f"(NASADEM; waypoints colored by summer HT verdict)", fontsize=10)

    vhandles = [Line2D([], [], marker="o", ls="", color=VERDICT_COLOR[v],
                       markeredgecolor="black", label=v)
                for v in ("SOLID", "USABLE", "MARGINAL", "DEAD")]
    vhandles.insert(0, Line2D([], [], marker="*", ls="", color="white",
                              markeredgecolor="black", ms=12, label="Wagon (TX)"))
    ax.legend(handles=vhandles, loc="upper right", fontsize=6.5, frameon=True)

    fig.tight_layout()
    out = os.path.join(FIGDIR, f"coverage_contour_{band}.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


def main():
    rows = load_results()
    for band in ("gmrs", "2m", "aar"):
        make_relief(band, rows)
        make_contour(band, rows)


if __name__ == "__main__":
    main()

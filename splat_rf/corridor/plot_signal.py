#!/usr/bin/env python3
"""Signal-vs-distance line plots for the Muddy Run corridor study.

One figure per direction (NORTH, SOUTH); each figure overlays the three bands
(GMRS/2m/AAR) and the three foliage states are shown as a small-multiple set:
terrain-only, summer (full leaf), leaf-off (fall/winter). Usable-signal
thresholds drawn as horizontal reference bands.

Wide aspect + adequate DPI per the machine reporting standard.
Writes PNGs to reports/figures/.
"""
from __future__ import annotations
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV = os.path.join(REPO, "studies", "muddy_run_corridor", "results.csv")
FIGDIR = os.path.join(REPO, "reports", "figures")
os.makedirs(FIGDIR, exist_ok=True)

THR = {"SOLID": -100.0, "USABLE": -110.0, "MARGINAL": -118.0}
BAND_LABEL = {"gmrs": "GMRS 462.6", "2m": "2m 146.1", "aar": "AAR 161.0"}
BAND_COLOR = {"gmrs": "#d62728", "2m": "#1f77b4", "aar": "#2ca02c"}


def load():
    with open(CSV) as f:
        return list(csv.DictReader(f))


def fnum(v):
    return float(v) if v not in ("", None) else None


def draw_thresholds(ax):
    ax.axhspan(-100, -60, color="#c9f2c9", alpha=0.45, zorder=0)   # solid
    ax.axhspan(-110, -100, color="#fff2b3", alpha=0.5, zorder=0)   # usable
    ax.axhspan(-118, -110, color="#ffd9b3", alpha=0.5, zorder=0)   # marginal
    ax.axhspan(-140, -118, color="#f4c2c2", alpha=0.45, zorder=0)  # dead
    for name, y in THR.items():
        ax.axhline(y, color="#666", lw=0.7, ls="--", zorder=1)
    ax.text(0.15, -99.5, "SOLID", fontsize=7, color="#2a7", va="bottom")
    ax.text(0.15, -109.5, "USABLE", fontsize=7, color="#b80", va="bottom")
    ax.text(0.15, -117.5, "MARGINAL", fontsize=7, color="#c60", va="bottom")
    ax.text(0.15, -119.5, "DEAD", fontsize=7, color="#b22", va="top")


def plot_direction(rows, direction, outfile):
    states = [("dbm_terrain", "Terrain only", "-", "o"),
              ("dbm_summer", "Summer (full leaf)", "--", "s"),
              ("dbm_leafoff", "Leaf-off (fall/winter)", ":", "^")]
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 3.6), sharey=True)
    for ax, (col, title, ls, mk) in zip(axes, states):
        draw_thresholds(ax)
        for band in ("2m", "aar", "gmrs"):
            pts = [(fnum(r["path_km"]), fnum(r[col]))
                   for r in rows if r["band"] == band and r["direction"] == direction]
            pts = [(x, y) for x, y in pts if x is not None and y is not None]
            pts.sort()
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            ax.plot(xs, ys, ls, marker=mk, ms=3.5, lw=1.4,
                    color=BAND_COLOR[band], label=BAND_LABEL[band], zorder=3)
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("Path distance from wagon (km)", fontsize=8)
        ax.set_xlim(0, 8.2)
        ax.set_ylim(-140, -55)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.25, zorder=1)
    axes[0].set_ylabel("Received signal at HT (dBm)", fontsize=8)
    handles = [plt.Line2D([], [], color=BAND_COLOR[b], lw=2, label=BAND_LABEL[b])
               for b in ("2m", "aar", "gmrs")]
    fig.legend(handles=handles, loc="upper center", ncol=3, fontsize=8,
               frameon=False, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle(f"Mobile repeat -> HT signal vs. distance  |  {direction} along Susquehanna corridor",
                 fontsize=10, y=1.10)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {outfile}")


def main():
    rows = load()
    plot_direction(rows, "NORTH", os.path.join(FIGDIR, "signal_vs_distance_north.png"))
    plot_direction(rows, "SOUTH", os.path.join(FIGDIR, "signal_vs_distance_south.png"))


if __name__ == "__main__":
    main()

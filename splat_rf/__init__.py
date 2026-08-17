"""Splat_RF_Analysis -- terrain-aware RF propagation toolchain.

A Python orchestration layer around SPLAT! (Longley-Rice / ITM) with a
per-band foliage/clutter correction layer and PostGIS persistence.

Design principle: WRAP the propagation engine, do not reimplement it.
SPLAT! (system binary) does the ITM physics; this package manages presets,
drives runs, applies frequency-specific foliage correction, and reads/writes
the local PostGIS instance for spatial querying + QGIS visualization.
"""

__version__ = "0.1.0.dev0"

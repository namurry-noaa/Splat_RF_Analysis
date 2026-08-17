"""Frequency-specific foliage / clutter attenuation models.

IMPORTANT ARCHITECTURE NOTE
---------------------------
The Longley-Rice / ITM engine in SPLAT! models TERRAIN (diffraction over
ridges, ground reflection) but NOT vegetation. Foliage loss is real, large at
UHF, and genuinely frequency-dependent -- so it is applied here as a SEPARATE
correction layer ON TOP OF the ITM path loss.

This is why we do NOT need "a different propagation model per band": one ITM
engine (frequency as a parameter) + these per-band empirical foliage models.

Implemented models (stubs -- Phase 3):
  * Weissberger's modified exponential decay model
  * ITU-R P.833 vegetation attenuation
  * COST-235  (optional, high-freq)

References for implementation:
  * Weissberger (1982): L = 1.33 * f^0.284 * d^0.588   (14 < d <= 400 m)
                        L = 0.45 * f^0.284 * d          (0 < d <= 14 m)
    where f in GHz, d = foliage depth in meters, L in dB.
  * ITU-R P.833-9: terrestrial vegetation attenuation.
"""

from __future__ import annotations


def weissberger_loss_db(freq_mhz: float, foliage_depth_m: float) -> float:
    """Weissberger modified exponential decay foliage loss.

    Args:
        freq_mhz: frequency in MHz.
        foliage_depth_m: depth of vegetation along the path, meters.

    Returns:
        Excess loss in dB attributable to foliage.

    TODO(Phase 3): validate coefficients; guard input ranges.
    """
    f_ghz = freq_mhz / 1000.0
    d = foliage_depth_m
    if d <= 0:
        return 0.0
    if d <= 14.0:
        return 0.45 * (f_ghz ** 0.284) * d
    # 14 < d <= 400
    return 1.33 * (f_ghz ** 0.284) * (d ** 0.588)


def itu_p833_loss_db(freq_mhz: float, foliage_depth_m: float) -> float:
    """ITU-R P.833 vegetation attenuation (stub).

    TODO(Phase 3): implement the specific-attenuation + max-attenuation form
    from ITU-R P.833-9. Placeholder returns Weissberger for now so the
    pipeline is runnable end-to-end.
    """
    # Placeholder until P.833 is implemented.
    return weissberger_loss_db(freq_mhz, foliage_depth_m)


FOLIAGE_MODELS = {
    "weissberger": weissberger_loss_db,
    "itu_p833": itu_p833_loss_db,
    "none": lambda freq_mhz, foliage_depth_m: 0.0,
}


def apply_foliage(model: str, freq_mhz: float, foliage_depth_m: float) -> float:
    """Dispatch to the named foliage model. Returns excess loss in dB."""
    fn = FOLIAGE_MODELS.get(model, FOLIAGE_MODELS["none"])
    return fn(freq_mhz, foliage_depth_m)

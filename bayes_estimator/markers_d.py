"""Strategy D biomarkers: the 2040 in-suit test.

Matches our Strategy D slides:
  - 4 radiation-responsive genes measured in the suit (AEN, TRAF4, DDB2, TRIAP1; Li 2022)
  - DNA-damage foci imaging (γ-H2AX + 53BP1) in the spacecraft before/after each EVA
  - FDXR, a next-day gene checked between EVAs (O'Brien 2018)
Reuses FociMarker and the limits from markers.py, so Strategy C is unchanged.
Dose units: mGy (BFO absorbed). 1 Gy = 1000 mGy."""
from dataclasses import dataclass
import numpy as np
from .markers import FociMarker, RBE_BFO, NASA_30D_LIMIT_mGyEq   # noqa: F401 (re-exported)


@dataclass(frozen=True)
class GeneMarker:
    """Gene expression as fold change vs unexposed (1x = unchanged).

    Data are fold changes at 2 Gy at several times after exposure. We ASSUME the
    extra activity scales in proportion to dose: fold = 1 + (fold_at_2Gy - 1) * dose / 2 Gy."""
    name: str
    times_h: tuple           # hours after exposure where we have data
    fold_2Gy: tuple          # fold change at 2 Gy at those times
    window_h: tuple          # (earliest, latest) hours after exposure it's usable
    cv: float = 0.15         # PLACEHOLDER: measurement + person-to-person noise

    def expected(self, dose_mGy, hrs_after):
        f2 = np.interp(hrs_after, self.times_h, self.fold_2Gy)
        return 1 + (f2 - 1) * (dose_mGy / 2000)

    def sd(self, mu):
        return self.cv * mu


# --- Gene panel, Li et al. Life 2022 (2 Gy, read from our "Fold change over time" chart) ---
T = (2, 4, 8, 12, 24)
AEN    = GeneMarker("AEN",    T, (2.5, 7.0, 10.7, 6.5, 5.7), window_h=(2, 8))
TRAF4  = GeneMarker("TRAF4",  T, (2.1, 5.6, 2.8, 2.5, 1.2),  window_h=(4, 8))
DDB2   = GeneMarker("DDB2",   T, (1.2, 2.1, 8.2, 5.4, 7.1),  window_h=(4, 24))
TRIAP1 = GeneMarker("TRIAP1", T, (1.8, 3.7, 5.9, 5.1, 3.7),  window_h=(8, 24))

# --- FDXR, O'Brien et al. Sci Rep 2018: next-day marker, responds from ~0.1 Gy ---
FDXR = GeneMarker("FDXR", (24,), (5.0,), window_h=(18, 30))   # PLACEHOLDER: 5x at 2 Gy

# --- Foci imaging, same source as Strategy C (Ivashkevich 2011) ---
H2AX = FociMarker("gH2AX", per_Gy=11.0, half_life_h=5.0, window_h=(0.5, 8))
# 53BP1: ~11 foci/Gy at 30 min from our earlier foci chart; fades slower than γ-H2AX
BP1 = FociMarker("53BP1", per_Gy=11.2, half_life_h=27.0, window_h=(0.5, 8))

DEVICE_DELAY_H = 1.0     # ASSUMPTION: on-board imaging / in-suit cartridge (vs ~5 h lab in C)
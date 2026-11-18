"""Every biomarker number in one place, with where it came from.
Dose units: mGy (BFO absorbed). 1 Gy = 1000 mGy, 1 cGy = 10 mGy.

Case context: physical radiation dosimetry is unreliable or unavailable,
so these biomarkers are the ONLY way to know each astronaut's dose."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class FociMarker:
    """DNA-repair foci counted by fluorescence imaging (γ-H2AX)."""
    name: str
    per_Gy: float            # extra foci per cell per Gy at the peak
    half_life_h: float       # how fast foci fade after the peak
    window_h: tuple          # (earliest, latest) hours after exposure it's usable
    peak_h: float = 0.5
    baseline: float = 0.1    # PLACEHOLDER: foci in unexposed cells
    cv: float = 0.25         # PLACEHOLDER: measurement + person-to-person noise
    floor_sd: float = 0.05   # PLACEHOLDER: smallest possible noise

    def expected(self, dose_mGy, hrs_after):
        fade = 0.5 ** (max(hrs_after - self.peak_h, 0) / self.half_life_h)
        return self.baseline + self.per_Gy * (dose_mGy / 1000) * fade

    def sd(self, mu):
        return np.maximum(self.cv * mu, self.floor_sd)


@dataclass(frozen=True)
class LymphMarker:
    """Lymphocyte count (x10^9/L); falls as dose rises."""
    name: str = "lymphocytes"
    window_h: tuple = (12, 48)   # Li 2022 (slide C)
    L0: float = 2.0              # PLACEHOLDER: normal count
    k_per_Gy: float = 0.5        # PLACEHOLDER: depletion rate, needs a source
    cv: float = 0.30             # big person-to-person variation (slide C)

    def expected(self, dose_mGy, hrs_after):
        return self.L0 * np.exp(-self.k_per_Gy * dose_mGy / 1000)

    def sd(self, mu):
        return self.cv * mu


# Strategy C slide, ref 1: Ivashkevich 2011 Fig 8B (~11 foci/Gy, 0.02-1.5 Gy)
# and Fig 8C (foci fade ~8.5 -> 3 over 0.5-8 h after 0.6 Gy)
H2AX = FociMarker("gH2AX", per_Gy=11.0, half_life_h=5.0, window_h=(0.5, 8))
LYMPH = LymphMarker()           # Strategy C slide, ref 2: Li 2022

STRATEGY_C_MARKERS = [H2AX, LYMPH]
LAB_DELAY_H = 5.0               # Strategy C slide, ref 2: ~5 h lab processing

RBE_BFO = 1.5                  # repo README table: 623.3/415.1 ≈ 63.99/43.14 ≈ 1.5
                               # LIMITATION: biomarker curves are gamma-calibrated;
                               # SPE protons may respond differently per Gy
NASA_30D_LIMIT_mGyEq = 250.0   # NASA STD Vol 1 Rev C, Table 4.8-1 (BFO, 30 days)
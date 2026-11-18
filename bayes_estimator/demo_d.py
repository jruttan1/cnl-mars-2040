"""Strategy D on one astronaut after one EVA: what do we know, and when?"""
import numpy as np
from bayes_estimator import estimator as E, markers_d as MD, observation_models as O

RETURN_H = 3.5   # hours from exposure (EVA midpoint) to coming back inside


def readings(true, rng):
    """Device results at each stage. The estimator never sees `true`."""
    r = lambda m, h: (m, O.read(m, true, h, rng), h)
    back_inside = [r(MD.H2AX, RETURN_H), r(MD.BP1, RETURN_H), r(MD.AEN, RETURN_H)]
    gene_panel = [r(MD.AEN, 8), r(MD.TRAF4, 8), r(MD.DDB2, 8), r(MD.TRIAP1, 8)]
    next_day = [r(MD.DDB2, 24), r(MD.TRIAP1, 24), r(MD.FDXR, 24)]
    return back_inside, gene_panel, next_day


def show(label, e):
    print(f"  {label:<38} mean {e['mean']:5.0f} mGy, 95% [{e['lo95']:4.0f}-{e['upper95']:4.0f}]"
          f" -> {E.decision(e['upper95'])}")


if __name__ == "__main__":
    for true in (40, 600):
        rng = np.random.default_rng(42)
        a, b, c = readings(true, rng)
        print(f"Astronaut whose true dose was {true} mGy (hidden from the estimator):")
        show("No biodosimetry (dosimeters down)", E.estimate([]))
        show(f"+{RETURN_H + MD.DEVICE_DELAY_H:.1f} h: foci + AEN (back inside)", E.estimate(a))
        show("+8 h: 4-gene panel added", E.estimate(a + b))
        show("+24 h: FDXR + late genes added", E.estimate(a + b + c))
        print()
"""Strategy C on one astronaut after one EVA: what do we know, and when?"""
import numpy as np
from bayes_estimator import estimator as E, markers as M, observation_models as O

DRAW_H = 3.5    # hours between exposure and the blood draw (drawn right after coming in)


def show(label, e):
    print(f"  {label:<38} mean {e['mean']:5.0f} mGy, 95% [{e['lo95']:4.0f}-{e['upper95']:4.0f}]"
          f" -> {E.decision(e['upper95'])}")


for true in (40, 600):
    rng = np.random.default_rng(42)
    foci = (M.H2AX, O.read(M.H2AX, true, DRAW_H, rng), DRAW_H)
    lymph = (M.LYMPH, O.read(M.LYMPH, true, 24, rng), 24)
    print(f"Astronaut whose true dose was {true} mGy (hidden from the estimator):")
    show("No biodosimetry (dosimeters down)", E.estimate([]))
    show(f"+{DRAW_H + M.LAB_DELAY_H:.1f} h: γ-H2AX result back", E.estimate([foci]))
    show("+24 h: lymphocyte count added", E.estimate([foci, lymph]))
    print()
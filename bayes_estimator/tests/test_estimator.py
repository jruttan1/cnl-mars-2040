import unittest
import numpy as np
from bayes_estimator import estimator as E, markers as M, observation_models as O


class TestEstimator(unittest.TestCase):
    def test_recovers_dose(self):
        rng = np.random.default_rng(0)
        r = [(M.H2AX, O.read(M.H2AX, 400, 1, rng), 1) for _ in range(5)]
        self.assertLess(abs(E.estimate(r)["mean"] - 400), 150)

    def test_biodosimetry_narrows_range(self):
        rng = np.random.default_rng(1)
        none = E.estimate([])
        foci = E.estimate([(M.H2AX, O.read(M.H2AX, 150, 3.5, rng), 3.5)])
        self.assertLess(foci["upper95"] - foci["lo95"], none["upper95"] - none["lo95"])

    def test_upper_bound_is_safe(self):
        rng = np.random.default_rng(2); n = 300; hits = 0
        for _ in range(n):
            true = rng.uniform(20, 500)
            r = [(M.H2AX, O.read(M.H2AX, true, 3.5, rng), 3.5)]
            hits += true <= E.estimate(r)["upper95"]
        self.assertGreater(hits / n, 0.88)

    def test_outside_window_ignored(self):
        p0 = E.estimate([])["posterior"]
        p1 = E.estimate([(M.LYMPH, 1.0, 3.5)])["posterior"]
        self.assertTrue(np.allclose(p0, p1))


if __name__ == "__main__":
    unittest.main()
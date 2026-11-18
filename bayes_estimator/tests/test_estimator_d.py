import unittest
import numpy as np
from bayes_estimator import estimator as E, markers as MC, markers_d as MD, observation_models as O
from bayes_estimator.demo_d import readings


def width(e):
    return e["upper95"] - e["lo95"]


class TestStrategyD(unittest.TestCase):
    def test_recovers_dose(self):
        rng = np.random.default_rng(0)
        a, b, c = readings(400, rng)
        self.assertLess(abs(E.estimate(a + b + c)["mean"] - 400), 150)

    def test_d_narrower_than_c(self):
        wc, wd = [], []
        rng = np.random.default_rng(3)
        for _ in range(100):
            c = [(MC.H2AX, O.read(MC.H2AX, 150, 3.5, rng), 3.5)]
            a, _, _ = readings(150, rng)
            wc.append(width(E.estimate(c))); wd.append(width(E.estimate(a)))
        self.assertLess(np.mean(wd), np.mean(wc))

    def test_more_genes_narrower(self):
        w1, w2 = [], []
        rng = np.random.default_rng(1)
        for _ in range(100):
            a, b, c = readings(300, rng)
            w1.append(width(E.estimate(a))); w2.append(width(E.estimate(a + b + c)))
        self.assertLess(np.mean(w2), np.mean(w1))

    def test_upper_bound_is_safe(self):
        rng = np.random.default_rng(2); n = 300; hits = 0
        for _ in range(n):
            true = rng.uniform(20, 500)
            a, _, _ = readings(true, rng)
            hits += true <= E.estimate(a)["upper95"]
        self.assertGreater(hits / n, 0.88)

    def test_gene_outside_window_ignored(self):
        p0 = E.estimate([])["posterior"]
        p1 = E.estimate([(MD.TRIAP1, 3.0, 3.5)])["posterior"]   # TRIAP1 only usable from 8 h
        self.assertTrue(np.allclose(p0, p1))


if __name__ == "__main__":
    unittest.main()
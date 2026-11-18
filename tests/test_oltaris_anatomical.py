"""Isolated data-integrity checks; no transport or mission simulation."""
import unittest

import numpy as np
import pandas as pd

from organize_oltaris_anatomical import (
    RAW, PROCESSED, SUMMARY_NAME, ORGANS_NAME, PARAMETER_COLUMNS,
    band_integral, source_spectrum, validate_doses,
)


class AnatomicalDataTests(unittest.TestCase):
    def test_summary_and_organs_agree(self):
        summary = pd.read_csv(RAW / SUMMARY_NAME)
        organs = pd.read_csv(RAW / ORGANS_NAME)
        self.assertEqual(len(validate_doses(summary, organs)), 36)
        organs.loc[0, 'grid_engine_id'] = -1
        with self.assertRaises(ValueError):
            validate_doses(summary, organs)

    def test_processed_values_and_missingness_preserved(self):
        for name in (SUMMARY_NAME, ORGANS_NAME):
            original = pd.read_csv(RAW / name)
            processed = pd.read_csv(PROCESSED / name)
            pd.testing.assert_frame_equal(original, processed[original.columns], check_dtype=False)

    def test_superseded_units_remain_separate(self):
        old = pd.read_csv(PROCESSED / 'superseded_weibull_anatomical_doses.csv')
        exported = old[old.provenance.eq('original_effective_dose_export')]
        self.assertEqual(set(exported.unit), {'mSv'})
        self.assertAlmostEqual(exported.loc[exported.target.eq('Bfo'), 'value'].item(), 588.90587)
        absorbed = old[old.quantity.eq('absorbed_dose')].iloc[0]
        self.assertEqual((absorbed.value, absorbed.unit), (474.4, 'mGy'))

    def test_band_accuracy_and_continuity(self):
        summary = pd.read_csv(RAW / SUMMARY_NAME)
        for years in (100, 1000):
            parameters = summary.loc[summary.sapphire_return_period_years.eq(years), PARAMETER_COLUMNS].iloc[0].to_numpy()
            source, _ = source_spectrum(years)
            predicted = band_integral(source[:, 0], parameters)
            self.assertLess(np.max(np.abs(predicted / source[:, 1] - 1)), .032)
            self.assertTrue(np.all(np.diff(predicted) < 0))
            _, r0, gamma1, gamma2 = parameters
            boundary_energy = np.sqrt(((gamma2 - gamma1) * r0) ** 2 + 938.2720813 ** 2) - 938.2720813
            sides = band_integral(boundary_energy * np.array([1 - 1e-10, 1 + 1e-10]), parameters)
            self.assertAlmostEqual(sides[0] / sides[1], 1, places=8)
        with self.assertRaises(ValueError):
            band_integral(0, parameters)


if __name__ == '__main__':
    unittest.main()

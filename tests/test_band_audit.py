"""Tests of spectrum mathematics and provenance; no mission model changes."""
import unittest
import numpy as np
from scipy.integrate import quad
from audit_band_spectra import band,corrected_parameters,PARAMETERS,PROTON_REST_MEV,sapphire_spectrum


class BandAuditTests(unittest.TestCase):
    def test_unit_conversion_on_both_branches(self):
        energy=np.geomspace(.01,2500,200)
        for p in PARAMETERS.values():
            original=band(energy,p,rigidity_reference_MV=1)
            corrected=band(energy,corrected_parameters(p))
            for x,y in zip(original,corrected):
                np.testing.assert_allclose(x,y,rtol=1e-13)
            uncorrected=band(energy,p)
            for x,y in zip(original,uncorrected):
                np.testing.assert_allclose(y/x,1000**p['gamma1'],rtol=1e-13)

    def test_differential_integrates_and_break_is_continuous(self):
        for p in PARAMETERS.values():
            rb=(p['gamma2']-p['gamma1'])*p['R0_MV']
            eb=np.sqrt(rb**2+PROTON_REST_MEV**2)-PROTON_REST_MEV
            for quantity in (0,1):
                low=band(eb*(1-1e-9),p)[quantity]
                high=band(eb*(1+1e-9),p)[quantity]
                self.assertAlmostEqual(float(low/high),1,places=7)
            for lo,hi in [(.1,10),(10,100),(100,1000)]:
                actual=quad(lambda e:float(band(e,p)[1]),lo,hi,
                            points=[eb] if lo<eb<hi else None,epsabs=.01,epsrel=1e-10)[0]
                expected=band(lo,p)[0]-band(hi,p)[0]
                self.assertAlmostEqual(actual/expected,1,places=8)

    def test_original_reports_and_correction_accuracy(self):
        corrected=[]
        for n,p in PARAMETERS.items():
            spectrum,_=sapphire_spectrum(n)
            estimate,_=band(spectrum[:,0],corrected_parameters(p))
            self.assertLess(np.max(abs(estimate/spectrum[:,1]-1)),.032)
            corrected.append(estimate)
        self.assertTrue(np.all(corrected[1]>corrected[0]))

    def test_invalid_energy_rejected(self):
        for energy in (0,-1):
            with self.assertRaises(ValueError):band(energy,PARAMETERS[100])


if __name__=='__main__':unittest.main()

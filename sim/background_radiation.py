"""Constant solar-minimum GCR reference, independent of the synthetic SPE.

NASA/TP-2011-216155 Table 2.7, male organ doses, annual values / (365*24).
20 g/cm² matches the cabin surrogate. The EVA channel uses the published 5 g/cm²
light-shield result as an explicit proxy, NOT transport through a 0.4 g/cm² suit.
No mSv conversion or SPE organ-ratio scaling is applied to GCR.
"""
from math import isfinite

SOURCE_URL = 'https://ntrs.nasa.gov/api/citations/20130001648/downloads/20130001648.pdf'
SOURCE_PATH = 'data/reference/gcr/nasa_tp_2011_216155.pdf'
# BFO absorbed mGy, BFO Gray Equivalent, skin Gray Equivalent, lens Gray Equivalent.
ANNUAL = {0.4: (185.7, 337.2, 375.8, 372.4),
          20.0: (182.0, 314.9, 342.3, 338.4)}
REFERENCE_SHIELDING = {0.4: 5.0, 20.0: 20.0}


def interval(start, end, shielding, scale=1.0):
    if not all(isfinite(x) for x in (start, end, scale)) or end < start or scale < 0:
        raise ValueError('GCR interval and scale must be finite, ordered and nonnegative')
    if shielding not in ANNUAL:
        raise ValueError('GCR reference supports only cabin 20 and EVA 0.4 proxy channels')
    return tuple(value * scale * (end - start) / (365 * 24) for value in ANNUAL[shielding])


def metadata(scale=1.0):
    return dict(source_url=SOURCE_URL, source_table='2.7(a,b), printed pp. 30–31',
                model='Constant solar-minimum male reference; emergency interval only', scale=scale,
                eva_limitation='5 g/cm² GCR proxy assigned to the 0.4 g/cm² EVA channel; not validated suit transport or an upper bound',
                quantity_order=['bfo_absorbed_mGy', 'bfo_gray_equivalent_mGy_eq',
                                'skin_gray_equivalent_mGy_eq', 'lens_gray_equivalent_mGy_eq'],
                daily_rates={str(depth): interval(0, 24, depth, scale) for depth in ANNUAL},
                source_shielding_g_cm2=REFERENCE_SHIELDING,
                prior_cruise_dose_included=False, reactor_dose_included=False)

"""Exploratory 20 g/cm² BFO proxy, defaulting to the 336-hour GOES-10 template.

Reference numbers come from the user's proposed calculation, NOT verified local
organ exports. This is not a matched SAPPHIRE anatomical transport calculation.
It must not drive Strategy A aborts or establish medical-limit compliance.
"""
import argparse
import numpy as np
from radiation_model import (ROOT, load_baseline, baseline_interval_dose,
                             write_preserving, sha256, BASELINE_PATH)

# User-supplied King-event reference; both organ values remain unverified here.
SHIELDING_G_CM2 = 20.0
KING_POINT_MGY = 185.2
KING_BFO_MGY = 28.89
KING_BFO_MGY_EQ = 41.92
DEFAULT_TEMPLATE = 'october_2003_goes10'
REFERENCE_STATUS = 'user_supplied_not_verified_in_repository'


def build_bfo_proxy(historical_template=DEFAULT_TEMPLATE):
    """Scale the existing timing histories at exactly 20 g/cm²; no EVA extrapolation."""
    baseline = load_baseline(historical_template=historical_template)
    frame = baseline[baseline.shielding_g_cm2.eq(SHIELDING_G_CM2)].copy()
    if frame.empty:
        raise ValueError('The proxy requires the exact 20 g/cm² baseline.')
    columns = ['historical_template', 'scenario', 'scenario_role', 'hour', 'hour_end',
               'bin_duration_h', 'shielding_g_cm2', 'timing_variant', 'estimate_type',
               'data_quality', 'normalized_bin_weight', 'dose_rate_mGy_h',
               'cumulative_dose_mGy', 'cumulative_end_dose_mGy', 'event_absorbed_dose_mGy',
               'template_source_path', 'template_source_sha256', 'source_path', 'source_sha256']
    frame = frame[columns]
    ratios = {'mGy': KING_BFO_MGY / KING_POINT_MGY,
              'mGy_Eq': KING_BFO_MGY_EQ / KING_POINT_MGY}
    for unit, ratio in ratios.items():
        frame[f'bfo_proxy_event_total_{unit}'] = frame.event_absorbed_dose_mGy * ratio
        frame[f'bfo_proxy_rate_{unit}_h'] = frame.dose_rate_mGy_h * ratio
        frame[f'bfo_proxy_cumulative_start_{unit}'] = frame.cumulative_dose_mGy * ratio
        frame[f'bfo_proxy_cumulative_end_{unit}'] = frame.cumulative_end_dose_mGy * ratio
        for _, group in frame.groupby(['scenario', 'timing_variant']):
            np.testing.assert_allclose(
                (group[f'bfo_proxy_rate_{unit}_h'] * group.bin_duration_h).sum(),
                group[f'bfo_proxy_event_total_{unit}'].iloc[0], rtol=1e-12)
    frame['reference_point_absorbed_dose_mGy'] = KING_POINT_MGY
    frame['reference_bfo_absorbed_dose_mGy'] = KING_BFO_MGY
    frame['reference_bfo_gray_equivalent_mGy_Eq'] = KING_BFO_MGY_EQ
    frame['reference_status'] = REFERENCE_STATUS
    frame['model_status'] = 'exploratory_cross_spectrum_cross_transport_proxy'
    frame['for_operational_decisions'] = False
    frame['baseline_sha256'] = sha256(BASELINE_PATH)
    return frame.reset_index(drop=True)


def bfo_interval_dose(frame, scenario, start_hour, end_hour, timing_variant=None):
    """Return separate exploratory mGy and mGy-Eq totals over storm hours [a,b)."""
    if frame.historical_template.nunique() != 1 or not frame.shielding_g_cm2.eq(20).all():
        raise ValueError('Select one historical template at exactly 20 g/cm².')
    if (not frame.reference_point_absorbed_dose_mGy.eq(KING_POINT_MGY).all() or
            not frame.reference_bfo_absorbed_dose_mGy.eq(KING_BFO_MGY).all() or
            not frame.reference_bfo_gray_equivalent_mGy_Eq.eq(KING_BFO_MGY_EQ).all()):
        raise ValueError('Proxy reference differs from the configured user-supplied values.')
    tissue_dose = baseline_interval_dose(scenario, SHIELDING_G_CM2, start_hour, end_hour,
        timing_variant, baseline=frame, historical_template=frame.historical_template.iloc[0])
    return {'bfo_proxy_mGy': tissue_dose * KING_BFO_MGY / KING_POINT_MGY,
            'bfo_proxy_mGy_Eq': tissue_dose * KING_BFO_MGY_EQ / KING_POINT_MGY}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', choices=['august_1972', DEFAULT_TEMPLATE], default=DEFAULT_TEMPLATE)
    parser.add_argument('--start-hour', type=float, default=16,
                        help='Storm-relative interval start, not emergency-relative time')
    parser.add_argument('--duration', type=float, default=7)
    args = parser.parse_args()
    if not np.isfinite(args.duration) or args.duration <= 0:
        parser.error('--duration must be finite and positive')
    frame = build_bfo_proxy(args.template)
    results = {scenario: bfo_interval_dose(frame, scenario, args.start_hour, args.start_hour+args.duration)
               for scenario in frame.scenario.unique()}
    output = ROOT / 'outputs/model' / f'exploratory_bfo_{args.template}.csv'
    write_preserving(output, frame.to_csv(index=False))
    print('EXPLORATORY ONLY — user-supplied organ reference values are unverified.')
    print('20 g/cm² only; no EVA mapping, medical-limit comparison or abort-policy use.')
    print(f'Template: {args.template}; {int(frame.hour_end.max())} full-event hours.')
    for scenario, interval in results.items():
        row = frame[frame.scenario.eq(scenario)].iloc[0]
        print(f'{scenario}: event-total BFO proxy {row.bfo_proxy_event_total_mGy:.6g} mGy; '
              f'{row.bfo_proxy_event_total_mGy_Eq:.6g} mGy-Eq')
        print(f'  Storm hours {args.start_hour:g}–{args.start_hour+args.duration:g}: '
              f'{interval["bfo_proxy_mGy"]:.6g} mGy; {interval["bfo_proxy_mGy_Eq"]:.6g} mGy-Eq (central timing)')
    print(f'Saved {output.relative_to(ROOT)} ({len(frame):,} rows).')


if __name__ == '__main__':
    main()

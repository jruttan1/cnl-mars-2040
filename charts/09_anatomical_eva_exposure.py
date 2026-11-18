"""Plot corrected BFO event totals with historical timing; baseline remains read-only."""
from pathlib import Path
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from radiation_model import ROOT, BASELINE_PATH, sha256
from anatomical_environment import load_environment, MANIFEST

OUT = ROOT / 'outputs/analysis/anatomical_eva'
DOSES = ROOT / 'data/processed/oltaris/oltaris_sapphire_anatomical_summary.csv'
CENTRAL = 'gt10MeV__log_linear'
TEMPLATES = {'august_1972': 'August 1972', 'october_2003_goes10': 'October–November 2003'}
COLORS = {100: '#176a9b', 1000: '#b54525'}


def interval_dose(frame, start, end):
    """Exact overlap integral of piecewise-constant hourly BFO rates."""
    if not (frame.hour.min() <= start <= end <= frame.hour_end.max()):
        raise ValueError('Interval must lie within the complete timing record')
    overlap = np.maximum(0, np.minimum(frame.hour_end, end) - np.maximum(frame.hour, start))
    return float(np.sum(frame.bfo_absorbed_dose_rate_mGy_h * overlap))


def build_profiles():
    records = []
    manifest = json.loads(MANIFEST.read_text())
    for template in TEMPLATES:
        data = load_environment(template)
        data = data[data.shielding_g_cm2.eq(.4)].copy()
        for (_, _), member in data.groupby(['scenario', 'timing_variant']):
            result = member.sort_values('hour').copy()
            result['return_period_years'] = int(result.scenario.iloc[0].split('-')[-1])
            result['bfo_absorbed_dose_rate_mGy_h'] = result.bfo_absorbed_dose_mGy_per_h
            increment = result.bfo_absorbed_dose_mGy_per_h * result.bin_duration_h
            result['continuous_eva_cumulative_end_mGy'] = increment.cumsum()
            result['continuous_eva_cumulative_start_mGy'] = increment.cumsum() - increment
            result['aluminum_areal_density_g_cm2'] = .4
            source = ('data/processed/spe_hourly.csv' if template == 'august_1972'
                      else 'data/processed/october_2003_goes10_hourly_proton_flux.csv')
            result['template_source_path'] = source
            result['template_source_sha256'] = manifest['source_sha256'][source]
            records.append(result)
    return pd.concat(records, ignore_index=True)


def build_eva_windows(profiles, duration):
    records = []
    if duration <= 0 or not np.isfinite(duration):
        raise ValueError('Positive finite EVA duration required')
    for (template, years, variant), member in profiles.groupby(
            ['historical_template', 'return_period_years', 'timing_variant']):
        member = member.sort_values('hour')
        starts = member.loc[member.hour + duration <= member.hour_end.max(), 'hour']
        for start in starts:
            records.append(dict(historical_template=template, return_period_years=years,
                                timing_variant=variant, eva_start_hour=start, eva_duration_h=duration,
                                bfo_eva_absorbed_dose_mGy=interval_dose(member, start, start + duration)))
    return pd.DataFrame(records)


def main():
    config_path = ROOT / 'radiation_config.json'
    duration = float(json.loads(config_path.read_text())['eva_duration_hours'])
    profiles = build_profiles()
    windows = build_eva_windows(profiles, duration)
    OUT.mkdir(parents=True, exist_ok=True)
    profiles.to_csv(OUT / 'hourly_bfo_profiles.csv', index=False)
    windows.to_csv(OUT / 'eva_start_time_comparison.csv', index=False)
    fig, axes = plt.subplots(3, 2, figsize=(13, 12), sharey='row')
    examples, cumulative_rows, provenance, sensitivity = [], [], [], []
    for column, (template, label) in enumerate(TEMPLATES.items()):
        sample = profiles[(profiles.historical_template.eq(template)) &
                          profiles.return_period_years.eq(100) & profiles.timing_variant.eq(CENTRAL)].sort_values('hour')
        central_windows = windows[(windows.historical_template.eq(template)) &
                                  windows.return_period_years.eq(100) & windows.timing_variant.eq(CENTRAL)]
        peak = central_windows.loc[central_windows.bfo_eva_absorbed_dose_mGy.idxmax()]
        start = float(peak.eva_start_hour)
        end = start + duration
        timestamp = pd.to_datetime(sample.template_timestamp_utc.iloc[0], utc=True)
        start_utc = timestamp + pd.Timedelta(hours=start)
        end_utc = timestamp + pd.Timedelta(hours=end)
        filled = sample[sample.is_gap_filled]
        for gap in filled.itertuples():
            axes[0, column].axvspan(gap.hour, gap.hour_end, facecolor='none', edgecolor='gray', hatch='////', linewidth=0)
            left, right = max(gap.hour, start), min(gap.hour_end, end)
            if right > left:
                axes[2, column].axvspan(left-start, right-start, facecolor='none', edgecolor='gray', hatch='////', linewidth=0)
        gap_dose = interval_dose(sample.assign(bfo_absorbed_dose_rate_mGy_h=sample.bfo_absorbed_dose_rate_mGy_h * sample.is_gap_filled), start, end)
        gap_fraction = gap_dose / interval_dose(sample, start, end)
        elapsed = np.unique(np.r_[np.arange(0, duration, 1), duration])
        for years, color in COLORS.items():
            members = profiles[profiles.historical_template.eq(template) & profiles.return_period_years.eq(years)]
            center = members[members.timing_variant.eq(CENTRAL)].sort_values('hour')
            edges = np.r_[center.hour, center.hour_end.iloc[-1]]
            style = '-' if years == 100 else '--'
            legend = f'SAPPHIRE 1-in-{years:,}'
            axes[0, column].stairs(center.bfo_absorbed_dose_rate_mGy_h, edges, baseline=None,
                                  color=color, ls=style, lw=1.8, label=legend)
            bounds = members.groupby('hour').bfo_absorbed_dose_rate_mGy_h.agg(['min', 'max'])
            axes[0, column].fill_between(edges, np.r_[bounds['min'], bounds['min'].iloc[-1]],
                                        np.r_[bounds['max'], bounds['max'].iloc[-1]], step='post', color=color, alpha=.10)
            subset = windows[windows.historical_template.eq(template) & windows.return_period_years.eq(years)]
            bounds = subset.groupby('eva_start_hour').bfo_eva_absorbed_dose_mGy.agg(['min', 'max'])
            chosen = subset[subset.timing_variant.eq(CENTRAL)]
            axes[1, column].plot(chosen.eva_start_hour, chosen.bfo_eva_absorbed_dose_mGy,
                                 color=color, ls=style, lw=1.8)
            axes[1, column].fill_between(bounds.index, bounds['min'], bounds['max'], color=color, alpha=.10)
            histories = np.array([[interval_dose(member, start, start + offset) for offset in elapsed]
                                  for _, member in members.groupby('timing_variant')])
            cumulative = [interval_dose(center, start, start + offset) for offset in elapsed]
            axes[2, column].plot(elapsed, cumulative, color=color, ls=style, lw=2,
                                 label=f'{years:,}-year: {cumulative[-1]:.2f} mGy')
            axes[2, column].fill_between(elapsed, histories.min(axis=0), histories.max(axis=0), color=color, alpha=.10)
            for variant, member in members.groupby('timing_variant'):
                value = interval_dose(member, start, end)
                sensitivity.append(dict(historical_template=template, return_period_years=years,
                    timing_variant=variant, eva_start_hour=start, eva_end_hour=end,
                    bfo_absorbed_dose_mGy=value, percent_change_from_central=100*(value/cumulative[-1]-1)))
            examples.append(dict(interpolated_dose_fraction=gap_fraction, historical_template=template, return_period_years=years,
                                 eva_start_hour=start, eva_end_hour=end, eva_duration_h=duration,
                                 template_eva_start_utc=str(start_utc), template_eva_end_utc=str(end_utc),
                                 central_bfo_eva_absorbed_dose_mGy=cumulative[-1],
                                 timing_min_mGy=histories[:, -1].min(), timing_max_mGy=histories[:, -1].max(),
                                 selection='maximum central seven-hour exposure among native hourly starts; illustrative, not operational'))
            cumulative_rows.extend(dict(historical_template=template, return_period_years=years,
                                        elapsed_eva_h=offset, cumulative_bfo_absorbed_dose_mGy=value)
                                   for offset, value in zip(elapsed, cumulative))
        for row in (0, 1):
            axes[row, column].set_xlim(0, sample.hour_end.max() if row == 0 else sample.hour_end.max() - duration)
            axes[row, column].set_xlabel(f'Hours since {timestamp:%d %b %Y %H:%M} UTC')
        axes[0, column].set_title(f'{label} timing · {len(sample)} hours', fontsize=13)
        axes[0, column].set_yscale('log')
        axes[0, column].set_ylabel('Modeled BFO absorbed dose rate (mGy/h)')
        axes[0, column].axvspan(start, end, color='#a88a21', alpha=.18)
        axes[0, column].legend(fontsize=9)
        axes[1, column].set_ylabel(f'BFO dose during a {duration:g}-hour EVA (mGy)')
        axes[1, column].axvline(start, color='#8a721b', ls=':', lw=1.4)
        axes[1, column].set_ylim(bottom=0)
        axes[2, column].set_title(f'Peak window {start:g}–{end:g} h · {gap_fraction:.1%} dose in filled bins', fontsize=11)
        axes[2, column].set_xlabel('Elapsed time within example EVA (hours)')
        axes[2, column].set_ylabel('Accumulated BFO absorbed dose (mGy)')
        axes[2, column].set_xlim(0, duration)
        axes[2, column].set_ylim(bottom=0)
        axes[2, column].legend(fontsize=9)
        for axis in axes[:, column]:
            axis.grid(axis='y', alpha=.18)
        provenance.append(dict(historical_template=template, template_start_utc=str(timestamp),
                               record_hours=len(sample), gap_filled_hours=int(sample.is_gap_filled.sum()),
                               source_path=sample.template_source_path.iloc[0],
                               source_sha256=sample.template_source_sha256.iloc[0]))
    fig.suptitle('Synthetic EVA exposure: anatomical BFO dose × historical storm timing', fontsize=16, y=.985)
    fig.text(.5, .952, 'MAX adult male · 0.4 g/cm² aluminium sphere · corrected Band / SAPPHIRE event totals', ha='center', fontsize=11)
    fig.text(.5, .012, 'Central: >10 MeV/log-linear. Hatching: interpolated bins. Shading: 9 timing alternatives, not confidence intervals.\n'
             'Historical timing only; fixed spectral shape. No distance rescaling, health-effect prediction or baseline replacement.',
             ha='center', fontsize=10)
    fig.tight_layout(rect=(0, .055, 1, .94), h_pad=2)
    fig.savefig(OUT / 'eva_bfo_comparison.png', dpi=180)
    plt.close(fig)
    pd.DataFrame(sensitivity).to_csv(OUT / 'interpolation_sensitivity.csv', index=False)
    pd.DataFrame(examples).to_csv(OUT / 'peak_window_examples.csv', index=False)
    pd.DataFrame(cumulative_rows).to_csv(OUT / 'example_eva_accumulation.csv', index=False)
    metadata = dict(quantity='BFO absorbed dose', unit='mGy', rate_unit='mGy/h', eva_duration_h=duration,
                    shielding_g_cm2=.4, central_timing_variant=CENTRAL, timing_sources=provenance,
                    dose_source_path=str(DOSES.relative_to(ROOT)), dose_source_sha256=sha256(DOSES),
                    baseline_read_only_sha256=sha256(BASELINE_PATH), config_read_only_sha256=sha256(config_path),
                    equation='dose_increment_mGy = event_BFO_absorbed_dose_mGy * normalized_bin_weight',
                    event_totals_mGy={str(years): float(member.event_bfo_absorbed_dose_mGy.iloc[0])
                                      for years, member in profiles.groupby('return_period_years')},
                    for_operational_decisions=False)
    (OUT / 'provenance.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (OUT / 'README.md').write_text('''# Anatomical EVA absorbed-dose comparison

This chart uses the common simulator environment: a synthetic time allocation of the corrected OLTARIS MAX **BFO absorbed dose**,
not the historical point/tissue absorbed dose and not the old King-ratio BFO proxy.
The 0.4 g/cm² aluminium sphere is an EVA shielding surrogate, not a validated spacesuit.
The 100-year and 1,000-year event totals are 415.1 and 723.7 mGy respectively.
No mSv or Gray Equivalent values are used in these calculations.

## Method and chart

For each complete historical record, the nonnegative timing weights sum to one.
Multiply those weights by the anatomical event-total dose; divide by bin duration for mGy/h.
The 1972 record has 264 hours and the 2003 GOES-10 record has 336 hours. They are normalized
separately, not renormalized to the EVA or a 72-hour display window. Physical event closure is unverified.
Historical proton measurements supply the relative peaks and dips, not measured astronaut dose.
The x axes use historical elapsed hours; timestamps are template dates, not a future forecast.

- Top: instantaneous modeled BFO rate under continuous EVA-reference shielding; log axis exposes dips.
- Middle: integrated dose for a seven-hour EVA starting at each valid hourly start. These overlapping
  windows are alternatives, not separate doses to add together.
- Bottom: cumulative additional BFO dose from zero during an example seven-hour EVA. The start is
  selected retrospectively at the largest central seven-hour dose, separately for each template.
  It is not a proposed EVA schedule or strategy optimization. Both return periods use the same start.
  Accumulation cannot dip; only its slope changes. No pre-EVA dose or post-EVA cabin dose is included.

The center uses >10 MeV/log-linear gap filling. Bands span >10, >30, >60 MeV and three existing
gap-fill choices, using each complete member history before taking bounds. They represent timing
sensitivity only, not confidence intervals or full dose uncertainty. Filled historical gaps retain flags
in hourly_bfo_profiles.csv and are hatched on the rate and example accumulation panels.
interpolation_sensitivity.csv compares all nine alternatives at the SAME central peak-window start.
The 35.2% 1972 filled-bin contribution is an allocation fraction, not an error estimate.
Counts/source hashes are in provenance.json.

## Interpretation limits

A fixed spectral shape through time is assumed: an event-integrated anatomical response is distributed
according to a proton-channel timing proxy. This is not time-resolved transport and does not account for
spectral hardening/softening, individual anatomy, attitude, realistic shielding, or dosimeter readings.
The inputs are user-supplied corrected summaries, not independently verified corrected solver exports.
Reference spectra are applied to a hypothetical mission near 1.25 AU without distance adjustment.
Source spectra report 1.2 AU; runs are labeled 1 AU.
The two synthetic severities differ only by their anatomical total within a given timing template.
These are not independent simulated time histories or predictions of event occurrence.

The result is an accumulated **modeled organ exposure**, not a health-effect model, medical threshold
assessment, or validated operational astronaut dose tracker. Further validated dosimetry and an explicit
health-response framework would be needed to translate exposure into effects.

## Reproduce

`.venv/bin/python charts/09_anatomical_eva_exposure.py`

Only outputs/analysis/anatomical_eva is written. Frozen baseline files, radiation_config.json, existing
SHIELDOSE reference charts and strategy logic remain unchanged. No transport simulation is rerun.
''')
    print(pd.DataFrame(examples).to_string(index=False))


if __name__ == '__main__':
    main()

"""Illustrate forecast-based scheduling; no strategy simulation or forecast validation."""
from pathlib import Path
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from radiation.anatomical_environment import load_environment, DATA, MANIFEST
from radiation.radiation_model import ROOT, sha256

OUT = ROOT / 'results/presentation/strategy_b'
TEMPLATES = {
    'august_1972': ('August 1972 timing', '#6A51A3'),
    'october_2003_goes10': ('2003 Halloween storm timing', '#238B45'),
}
WARNING_TEMPLATE_HOUR = 48
HORIZON_H = 120
EVA_H = 7
TIMING_OFFSETS_H = (-6, 0, 6)
AMPLITUDE_FACTORS = (.7, 1., 1.3)


def build_examples():
    examples, hourly_records, window_records = {}, [], []
    for template in TEMPLATES:
        frame = load_environment(template)
        member = frame[frame.timing_variant.eq('gt10MeV__log_linear') &
                       frame.shielding_g_cm2.eq(.4) &
                       frame.scenario.eq('SAPPHIRE-1-in-100')].sort_values('hour')
        assert np.allclose(member.bin_duration_h, 1)
        source_rates = member.bfo_gray_equivalent_mGy_eq_per_h.to_numpy()
        assert np.isclose(source_rates.sum(), 623.3)
        members, integrated, central_index = [], [], None
        for offset in TIMING_OFFSETS_H:
            for factor in AMPLITUDE_FACTORS:
                indices = WARNING_TEMPLATE_HOUR + np.arange(HORIZON_H) - offset
                assert indices.min() >= 0 and indices.max() < len(source_rates)
                rates = source_rates[indices] * factor
                doses = np.convolve(rates, np.ones(EVA_H), mode='valid')
                if offset == 0 and factor == 1:
                    central_index = len(members)
                members.append(rates)
                integrated.append(doses)
                for hour, rate in enumerate(rates):
                    hourly_records.append(dict(template=template, delay_h=offset, amplitude_factor=factor,
                                               hour=hour, bfo_rate_mGy_eq_per_h=rate))
                for start, dose in enumerate(doses):
                    assert np.isclose(dose, rates[start:start + EVA_H].sum(), rtol=1e-12)
                    window_records.append(dict(template=template, delay_h=offset, amplitude_factor=factor,
                                               eva_start_h=start, eva_end_h=start + EVA_H,
                                               bfo_eva_dose_mGy_eq=dose))
        members, integrated = np.array(members), np.array(integrated)
        starts = np.arange(HORIZON_H - EVA_H + 1)
        assert np.all(members > 0) and np.all(integrated > 0)
        examples[template] = dict(rates=members, doses=integrated, central_index=central_index,
                                  starts=starts)
    return examples, hourly_records, window_records


def setup_axes():
    figure, axes = plt.subplots(2, 1, figsize=(8.2, 7), sharex=True, sharey=True)
    figure.subplots_adjust(left=.14, right=.97, bottom=.17, top=.81, hspace=.30)
    for axis in axes:
        axis.spines[['top', 'right']].set_visible(False)
        axis.tick_params(direction='out', labelsize=11)
        axis.grid(axis='y', color='#E4E4E4', linewidth=.5)
        axis.set_axisbelow(True)
        axis.set_yscale('log')
        axis.minorticks_off()
        axis.set_xticks([0, 24, 48, 72, 96, 120])
    return figure, axes


def save(figure, name):
    for extension in ('png', 'svg'):
        figure.savefig(OUT / f'{name}.{extension}', dpi=220, facecolor='white')
    plt.close(figure)


def forecast_chart(examples):
    figure, axes = setup_axes()
    for axis, (template, (title, color)) in zip(axes, TEMPLATES.items()):
        example = examples[template]
        values = example['rates']
        central = values[example['central_index']]
        edges = np.arange(HORIZON_H + 1)
        axis.fill_between(edges, np.r_[values.min(axis=0), values.min(axis=0)[-1]],
                          np.r_[values.max(axis=0), values.max(axis=0)[-1]],
                          step='post', color=color, alpha=.18, linewidth=0)
        axis.stairs(central, edges, baseline=None, color=color, linewidth=1.4)
        axis.set_title(title, loc='left', fontsize=12, pad=7)
        axis.set_xlim(0, HORIZON_H)
        axis.set_ylim(.0001, 250)
        axis.set_yticks([.001, .01, .1, 1, 10, 100],
                       labels=['0.001', '0.01', '0.1', '1', '10', '100'])
    figure.suptitle('Strategy B: uncertain radiation forecast', fontsize=15, y=.98)
    figure.legend([Line2D([], [], color='#444444'), Patch(facecolor='#999999', alpha=.3)],
                  ['Central estimate', 'Illustrative scenario range'],
                  loc='upper center', bbox_to_anchor=(.55, .935), ncol=2, frameon=False, fontsize=11)
    figure.text(.025, .49, 'Predicted BFO dose rate (mGy-Eq/h; log scale)', va='center', rotation=90, fontsize=12)
    axes[-1].set_xlabel('Hours after illustrative warning', fontsize=12)
    figure.text(.55, .065, '100-year scenario · 0.4 g/cm² aluminum shielding', ha='center', fontsize=10)
    figure.text(.55, .025, 'Illustration only: ±6 h timing, ±30% magnitude; range is not a confidence interval.',
                ha='center', fontsize=9)
    save(figure, '01_uncertain_forecast')


def scheduling_chart(examples):
    figure, axes = setup_axes()
    figure.subplots_adjust(bottom=.22)
    severities = [('SAPPHIRE-1-in-100', '1-in-100-year', '#2878B5', 623.3),
                  ('SAPPHIRE-1-in-1000', '1-in-1,000-year', '#D55E00', 1087.)]
    records = []
    for axis, (template, (title, _)) in zip(axes, TEMPLATES.items()):
        frame = load_environment(template)
        starts = examples[template]['starts']
        for scenario, label, color, event_total in severities:
            member = frame[frame.timing_variant.eq('gt10MeV__log_linear') &
                           frame.shielding_g_cm2.eq(.4) &
                           frame.scenario.eq(scenario)].sort_values('hour')
            assert np.allclose(member.bin_duration_h, 1)
            source_rates = member.bfo_gray_equivalent_mGy_eq_per_h.to_numpy()
            assert np.isclose(source_rates.sum(), event_total)
            rates = source_rates[WARNING_TEMPLATE_HOUR:WARNING_TEMPLATE_HOUR + HORIZON_H]
            doses = np.convolve(rates, np.ones(EVA_H), mode='valid')
            assert len(doses) == len(starts)
            axis.scatter(starts, doses, color=color, s=12, linewidths=0, zorder=3)
            for departure, dose in zip(starts, doses):
                assert np.isclose(dose, rates[departure:departure + EVA_H].sum(), rtol=1e-12)
                records.append(dict(template=template, scenario=scenario,
                                    eva_start_h=int(departure), eva_end_h=int(departure + EVA_H),
                                    bfo_eva_dose_mGy_eq=float(dose)))
        axis.set_title(title, loc='left', fontsize=12, pad=7)
        axis.set_xlim(0, HORIZON_H)
        axis.set_ylim(.001, 2000)
        axis.set_yticks([.01, .1, 1, 10, 100, 1000],
                       labels=['0.01', '0.1', '1', '10', '100', '1,000'])
    figure.suptitle('EVA timing changes radiation exposure.', fontsize=15, y=.98)
    figure.legend([Line2D([], [], color=color, marker='o', linestyle='none', markersize=5)
                   for _, _, color, _ in severities],
                  [label for _, label, _, _ in severities],
                  loc='upper center', bbox_to_anchor=(.55, .935), ncol=2, frameon=False, fontsize=11)
    figure.text(.025, .49, 'Total seven-hour EVA BFO dose (mGy-Eq; log scale)', va='center', rotation=90, fontsize=12)
    axes[-1].set_xlabel('EVA departure time (hours after warning)', fontsize=12)
    figure.text(.55, .105, 'Each dot totals the next seven hours · 0.4 g/cm² aluminum shielding', ha='center', fontsize=10)
    figure.text(.55, .065, 'Assumed warning: hour 48 of each historical profile = hour 0 here.',
                ha='center', fontsize=10)
    figure.text(.55, .025, 'Modeled exposure shown; the crew’s forecast would be uncertain.',
                ha='center', fontsize=10)
    save(figure, '02_eva_start_selection')
    pd.DataFrame(records).to_csv(OUT / 'severity_eva_windows.csv', index=False)
    return len(records)


def main():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'axes.linewidth': .8, 'svg.fonttype': 'none'})
    examples, hourly, windows = build_examples()
    OUT.mkdir(parents=True, exist_ok=True)
    forecast_chart(examples)
    severity_windows_checked = scheduling_chart(examples)
    pd.DataFrame(hourly).to_csv(OUT / 'illustrative_forecast_members.csv', index=False)
    pd.DataFrame(windows).to_csv(OUT / 'illustrative_eva_windows.csv', index=False)
    report = dict(status='Illustration, not a strategy simulation or a calibrated forecast',
                  template_warning_hour=WARNING_TEMPLATE_HOUR, horizon_h=HORIZON_H,
                  eva_duration_h=EVA_H,
                  central_scenario='SAPPHIRE-1-in-100', shielding_g_cm2=.4,
                  timing_offsets_h=TIMING_OFFSETS_H, amplitude_factors=AMPLITUDE_FACTORS,
                  band='Min/max of nine coherent forecast members, not a confidence interval',
                  repair_constraints='No repair deadline or operational feasibility rule imposed',
                  source_environment_sha256=sha256(DATA), source_manifest_sha256=sha256(MANIFEST),
                  generator_sha256=sha256(Path(__file__)),
                  windows_checked=len(windows),
                  scheduling_chart_scenarios=['SAPPHIRE-1-in-100', 'SAPPHIRE-1-in-1000'],
                  scheduling_chart_display='Central hourly departure doses; no uncertainty whiskers or selected-start markers',
                  scheduling_time_origin='Hour 0 is an assumed warning at historical profile hour 48, not an observed warning',
                  severity_windows_checked=severity_windows_checked)
    (OUT / 'provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Validated {len(windows)} windows across 18 forecast members. Created figures in {OUT}')


if __name__ == '__main__':
    main()

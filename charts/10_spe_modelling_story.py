"""Build presentation figures from the existing, checksum-verified BFO environment."""
from pathlib import Path
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anatomical_environment import load_environment, SUMMARY, MANIFEST, DATA
from radiation_model import ROOT, sha256

OUT = ROOT / 'outputs/presentation/spe_modelling'
CENTRAL = 'gt10MeV__log_linear'
COLORS = {100: '#167DAD', 1000: '#C25432'}
TEMPLATES = {
    'august_1972': ('August 1972 timing', 'IMP-5 / NASA OMNIWeb', 264),
    'october_2003_goes10': ('October–November 2003 timing', 'GOES-10 supplied historical record', 336),
}


def style_axis(axis):
    axis.spines[['top', 'right']].set_visible(False)
    axis.tick_params(direction='out', width=.8, length=4, labelsize=11, colors='black')
    axis.set_axisbelow(True)
    axis.grid(axis='y', color='#E4E4E4', linewidth=.5)


def save(figure, name):
    for extension in ('png', 'svg'):
        figure.savefig(OUT / f'{name}.{extension}', dpi=220, facecolor='white')
    plt.close(figure)


def load_checked_data():
    summary = pd.read_csv(SUMMARY)
    records, checks = [], []
    for template, (_, _, expected_bins) in TEMPLATES.items():
        frame = load_environment(template)
        frame = frame[frame.timing_variant.eq(CENTRAL)].copy()
        for (scenario, shielding), member in frame.groupby(['scenario', 'shielding_g_cm2']):
            member = member.sort_values('hour')
            years = int(scenario.split('-')[-1])
            expected = summary[(summary.sapphire_return_period_years.eq(years)) &
                               (summary.aluminum_areal_density_g_cm2.eq(shielding))]
            assert len(expected) == 1
            total = float(expected.bfo_gray_equivalent_mGy_eq.iloc[0])
            weights = member.normalized_bin_weight.to_numpy()
            duration = member.bin_duration_h.to_numpy()
            rates = member.bfo_gray_equivalent_mGy_eq_per_h.to_numpy()
            assert len(member) == expected_bins
            assert np.all(np.isfinite(rates)) and np.all(rates >= 0)
            assert np.all(duration > 0) and np.all(weights >= 0)
            assert np.isclose(weights.sum(), 1, rtol=0, atol=1e-12)
            assert np.allclose(rates * duration, total * weights, rtol=1e-12)
            assert np.isclose(np.sum(rates * duration), total, rtol=1e-12)
            assert member.hour.iloc[0] == 0
            assert np.allclose(member.hour_end.iloc[:-1], member.hour.iloc[1:])
            checks.append(dict(template=template, scenario=scenario, shielding_g_cm2=float(shielding),
                               bins=len(member), gap_filled_bins=int(member.is_gap_filled.sum()),
                               weights_sum=float(weights.sum()), expected_total_mGy_eq=total,
                               integrated_total_mGy_eq=float(np.sum(rates * duration))))
        records.append(frame)
    return summary, pd.concat(records, ignore_index=True), checks


def magnitude_chart(summary):
    figure, axes = plt.subplots(1, 2, figsize=(12, 6.5), sharey=True)
    figure.subplots_adjust(left=.12, right=.98, bottom=.20, top=.80, wspace=.14)
    organs = [('BFO', 'bfo'), ('Skin', 'skin'), ('Eye lens', 'lens')]
    records = []
    for axis, shielding, title in zip(axes, (.4, 20), ('EVA — 0.4 g/cm² aluminum shielding', 'Cabin — 20 g/cm² aluminum shielding')):
        for years, offset in ((100, -.18), (1000, .18)):
            run = summary[summary.sapphire_return_period_years.eq(years) &
                          summary.aluminum_areal_density_g_cm2.eq(shielding)].iloc[0]
            values = [float(run[f'{organ}_gray_equivalent_mGy_eq']) for _, organ in organs]
            assert np.isfinite(values).all() and np.all(np.array(values) > 0)
            positions = np.arange(3) + offset
            axis.bar(positions, np.array(values) - 10, bottom=10, width=.32,
                     color=COLORS[years], edgecolor='black', linewidth=.5,
                     label=f'{years:,}-year scenario', zorder=3)
            for position, value, (label, _) in zip(positions, values, organs):
                axis.annotate(f'{value:,.2f}'.rstrip('0').rstrip('.'), (position, value), xytext=(0, 9),
                              textcoords='offset points', ha='center', fontsize=9)
                records.append(dict(organ=label, shielding_g_cm2=shielding,
                                    return_period_years=years, full_event_mGy_eq=value))
        axis.set_xticks(np.arange(3), ['Blood-forming\norgans (BFO)', 'Skin', 'Eye lens'])
        axis.set_xlabel('Body part', labelpad=10)
        axis.set_xlim(-.5, 2.5)
        axis.set_yscale('log')
        axis.set_ylim(10, 220000)
        axis.set_yticks([10, 100, 1000, 10000, 100000],
                       labels=['10', '100', '1,000', '10,000', '100,000'])
        axis.minorticks_off()
        axis.set_title(title, loc='left', fontsize=12, pad=12)
        style_axis(axis)
    axes[0].set_ylabel('Full-event radiation dose absorbed by body part\n(biologically weighted, mGy-Eq)')
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, title='SAPPHIRE return period', loc='upper center',
                  bbox_to_anchor=(.54, .985), ncol=2, frameon=False, fontsize=11, title_fontsize=11)
    figure.text(.54, .035, 'Entire event at fixed shielding · logarithmic scale (each step = ×10)',
                ha='center', fontsize=10)
    save(figure, '01_sources_to_dose')
    pd.DataFrame(records).to_csv(OUT / 'backup_organ_totals.csv', index=False)


def normalized_timing_chart(profiles):
    figure, axis = plt.subplots(figsize=(7.2, 5.8))
    figure.subplots_adjust(left=.17, right=.97, bottom=.18, top=.90)
    records = []
    styles = [('august_1972', '1972 · IMP-5', '#6A51A3', '-'),
              ('october_2003_goes10', '2003 · GOES-10', '#238B45', '--')]
    for template, label, color, linestyle in styles:
        member = profiles[profiles.historical_template.eq(template) &
                          profiles.shielding_g_cm2.eq(.4) &
                          profiles.scenario.eq('SAPPHIRE-1-in-100')].sort_values('hour')
        percent_rates = 100 * member.normalized_bin_weight / member.bin_duration_h
        assert np.isclose(np.sum(percent_rates * member.bin_duration_h), 100)
        edges = np.r_[member.hour.to_numpy(), member.hour_end.iloc[-1]]
        axis.stairs(percent_rates, edges, baseline=None, color=color, linestyle=linestyle,
                    linewidth=1.3, label=label)
        for gap in member[member.is_gap_filled].itertuples():
            axis.axvspan(gap.hour, gap.hour_end, facecolor='none', edgecolor='#C8C8C8',
                         hatch='////', linewidth=0, zorder=0)
        for row, rate in zip(member.itertuples(), percent_rates):
            records.append(dict(historical_template=template, hour=row.hour, hour_end=row.hour_end,
                                bin_duration_h=row.bin_duration_h, percent_per_h=rate,
                                is_gap_filled=row.is_gap_filled))
    axis.set_yscale('log')
    axis.set_ylim(.00001, 30)
    axis.set_yticks([.00001, .0001, .001, .01, .1, 1, 10])
    axis.minorticks_off()
    axis.set_xlim(0, 336)
    axis.set_xticks([0, 72, 144, 216, 288, 336])
    axis.set_xlabel('Time from template start (h)')
    axis.set_ylabel('Share of total event exposure\nper hour (%/h)')
    axis.set_title('When does exposure occur?', fontsize=14, pad=12)
    handles, labels = axis.get_legend_handles_labels()
    handles.append(Patch(facecolor='none', edgecolor='#C8C8C8', hatch='////'))
    axis.legend(handles, labels + ['1972 interpolation'], frameon=False, loc='lower right', fontsize=10)
    style_axis(axis)
    figure.text(.55, .035, '>10 MeV timing proxy · each record normalized to 100% · log scale',
                ha='center', fontsize=10)
    save(figure, '04_normalized_storm_timing')
    pd.DataFrame(records).to_csv(OUT / 'normalized_timing.csv', index=False)


def eva_timing_chart(profiles):
    figure, axis = plt.subplots(figsize=(7.2, 5.8))
    figure.subplots_adjust(left=.15, right=.97, bottom=.18, top=.90)
    records, checks = [], []
    for years in (100, 1000):
        member = profiles[profiles.historical_template.eq('august_1972') &
                          profiles.shielding_g_cm2.eq(.4) &
                          profiles.scenario.eq(f'SAPPHIRE-1-in-{years}')].sort_values('hour')
        starts = member.loc[member.hour + 7 <= member.hour_end.max(), 'hour'].to_numpy()
        rates = member.bfo_gray_equivalent_mGy_eq_per_h.to_numpy()
        assert np.allclose(member.bin_duration_h, 1)
        doses = np.convolve(rates, np.ones(7), mode='valid')
        assert len(starts) == len(doses) == 258
        for start, dose in zip(starts, doses):
            overlaps = np.maximum(0, np.minimum(member.hour_end, start + 7) - np.maximum(member.hour, start))
            assert np.isclose(dose, np.sum(rates * overlaps), rtol=1e-12, atol=1e-12)
            records.append(dict(historical_template='august_1972', return_period_years=years,
                                shielding_g_cm2=.4, eva_start_h=start, eva_end_h=start + 7,
                                eva_bfo_mGy_eq=dose,
                                overlaps_interpolated_bins=bool(np.any((overlaps > 0) & member.is_gap_filled))))
        axis.plot(starts, doses, color=COLORS[years], linewidth=1.5,
                  linestyle='--' if years == 1000 else '-', label=f'{years:,} yr')
        peak = int(np.argmax(doses))
        axis.scatter([starts[peak]], [doses[peak]], color=COLORS[years], s=20, zorder=3)
        axis.annotate(f'{doses[peak]:.0f}', (starts[peak], doses[peak]), xytext=(9, 6),
                      textcoords='offset points', color=COLORS[years], fontsize=11)
        checks.append(dict(return_period_years=years, windows=len(starts),
                           peak_start_h=float(starts[peak]), peak_end_h=float(starts[peak] + 7),
                           peak_seven_hour_bfo_mGy_eq=float(doses[peak])))
    axis.set_xlim(0, 264)
    axis.set_xticks([0, 48, 96, 144, 192, 240, 264])
    axis.set_ylim(0, 650)
    axis.set_yticks([0, 100, 200, 300, 400, 500, 600])
    axis.set_xlabel('EVA start time within template (h)')
    axis.set_ylabel('Seven-hour EVA BFO dose (mGy-Eq)')
    axis.set_title('What does EVA timing change?', fontsize=14, pad=12)
    axis.legend(title='SAPPHIRE return period', frameon=False, loc='upper right', fontsize=11,
                title_fontsize=11)
    style_axis(axis)
    figure.text(.55, .035, '1972 timing · 0.4 g/cm² aluminum shielding · EVA dose only', ha='center', fontsize=10)
    save(figure, '05_seven_hour_eva_timing')
    pd.DataFrame(records).to_csv(OUT / 'seven_hour_eva_windows.csv', index=False)
    return checks


def timing_chart(profiles):
    figure = plt.figure(figsize=(7.2, 5.8))
    axes = [figure.add_axes([.14, .55, .82, .32]), figure.add_axes([.14, .14, .82, .32])]
    panel_titles = ['(a) August 1972', '(b) October–November 2003']
    for axis, (template, _), title in zip(axes, TEMPLATES.items(), panel_titles):
        subset = profiles[profiles.historical_template.eq(template) & profiles.shielding_g_cm2.eq(.4)]
        for years in (1000, 100):
            member = subset[subset.scenario.eq(f'SAPPHIRE-1-in-{years}')].sort_values('hour')
            edges = np.r_[member.hour.to_numpy(), member.hour_end.iloc[-1]]
            rates = member.bfo_gray_equivalent_mGy_eq_per_h.to_numpy()
            axis.stairs(rates, edges, color=COLORS[years], linewidth=1.15,
                        linestyle='--' if years == 1000 else '-',
                        label=f'{years:,} yr', baseline=None)
            if years == 100:
                for gap in member[member.is_gap_filled].itertuples():
                    axis.axvspan(gap.hour, gap.hour_end, facecolor='none', edgecolor='#B6B6B6',
                                 hatch='////', linewidth=0, zorder=0)
        axis.set_title(title, loc='left', fontsize=12, pad=7)
        axis.set_xlim(0, 336)
        axis.set_yscale('log')
        axis.set_ylim(.0001, 200)
        axis.set_yticks([.0001, .001, .01, .1, 1, 10, 100])
        axis.minorticks_off()
        axis.set_xticks([0, 72, 144, 216, 288, 336])
        style_axis(axis)
    handles, labels = axes[0].get_legend_handles_labels()
    handles = handles[::-1] + [Patch(facecolor='none', edgecolor='#B6B6B6', hatch='////', label='Interpolated')]
    figure.legend(handles, labels[::-1] + ['Interpolated'], loc='upper center',
                  bbox_to_anchor=(.55, .995), ncol=3, frameon=False, fontsize=11,
                  title='SAPPHIRE return period', title_fontsize=11)
    figure.text(.025, .51, 'BFO Gray Equivalent rate (mGy-Eq/h)', rotation=90,
                va='center', fontsize=12)
    axes[1].set_xlabel('Time from template start (h)', labelpad=7)
    figure.text(.55, .017, 'Synthetic SPE · 0.4 g/cm$^{2}$ aluminum shielding · >10 MeV proxy',
                ha='center', fontsize=10)
    save(figure, '02_histories_to_synthetic_spe')


def main():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12,
                         'axes.linewidth': .8, 'svg.fonttype': 'none'})
    summary, profiles, checks = load_checked_data()
    OUT.mkdir(parents=True, exist_ok=True)
    magnitude_chart(summary)
    timing_chart(profiles)
    normalized_timing_chart(profiles)
    eva_checks = eva_timing_chart(profiles)
    profiles.to_csv(OUT / 'plotted_hourly_environment.csv', index=False)
    manifest = json.loads(MANIFEST.read_text())
    provenance = {
        'quantity': 'Organ Gray Equivalent: mGy-Eq; BFO rate: mGy-Eq/h; normalized timing: %/h',
        'background_slide': ['04_normalized_storm_timing', '05_seven_hour_eva_timing'],
        'backup_organ_chart': '01_sources_to_dose',
        'eva_window_validation': eva_checks,
        'method': 'Read existing simulator radiation environment; no new OLTARIS or mission run',
        'timing_variant': CENTRAL,
        'source_sha256': manifest['source_sha256'],
        'environment_sha256': sha256(DATA),
        'generator_sha256': sha256(Path(__file__)),
        'validation': checks,
        'limitations': ['Fixed spectral shape through time', 'No heliocentric distance rescaling',
                        'Idealized aluminium spheres and MAX male anatomy',
                        'Corrected OLTARIS summaries supplied by user; native exports pending verification',
                        'Exact GOES-10 archive match pending verification',
                        'Historical record endpoints do not establish physical event closure',
                        'Two severity levels crossed with two timing templates; not independent observed events'],
    }
    (OUT / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(f'Created four PNG/SVG figures in {OUT}')
    print(f'Passed {len(checks)} dose-conservation checks across both templates, severities and shielding states.')


if __name__ == '__main__':
    main()

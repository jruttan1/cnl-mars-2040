"""Accumulated grid-target dose, with a preselected seven-hour example interval."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from environment_common import load_historical as load, central, draw_envelopes, sensitivity_legend, accumulated_dose, finish, COLORS


def main():
    cfg, mission, _, _, _ = load()
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    a = cfg['eva_start_hour']; b = a + cfg['eva_duration_hours']
    for ax, (location, spec) in zip(axes, cfg['environments'].items()):
        frame = mission[mission.location.eq(location)]
        curve = central(frame)
        draw_envelopes(ax, frame, cfg, cumulative=True)
        edges = np.r_[0, curve.hour_end_since_emergency]
        cumulative = np.r_[0, curve.cumulative_end_absorbed_dose_mGy]
        ax.plot(edges, cumulative, color=COLORS[location], linewidth=2.2)
        ax.axvspan(a, b, color='#b78b20', alpha=0.17, linewidth=0)
        exposure = accumulated_dose(curve, a, b)
        ax.text(0.025, 0.92, f'Interval {a:g}–{b:g} h: {exposure:,.2f} mGy\n'
                f'{cfg["emergency_duration_hours"]:g}-hour total: {cumulative[-1]:,.2f} mGy',
                transform=ax.transAxes, va='top', fontsize=10,
                bbox=dict(facecolor='white', edgecolor='none', alpha=0.85))
        ax.set(title=f'{spec["label"]} — {spec["shielding_g_cm2"]:g} g/cm² Al',
               ylabel='Cumulative absorbed dose [mGy]', xlim=(0, cfg['emergency_duration_hours']), ylim=(0, None))
        ax.ticklabel_format(axis='y', style='plain', useOffset=False)
        ax.grid(alpha=0.16)
    axes[-1].set_xlabel('Hours since emergency begins')
    fig.suptitle('Historical King reference: cumulative dose', fontsize=17, y=0.99)
    fig.text(0.5, 0.947, f'Start: {cfg["emergency_start_utc"]} • Separate linear dose scales for readability',
             ha='center', fontsize=10)
    fig.legend(handles=sensitivity_legend()+[Patch(facecolor='#b78b20', alpha=0.17, label=f'Example {cfg["eva_duration_hours"]:g}-hour interval')],
               loc='lower center', bbox_to_anchor=(0.5, 0.065), ncol=2, frameon=False)
    fig.text(0.5, 0.015, 'Both curves start at zero and integrate the same SPE timeline with different shielding responses.\n'
             'Sensitivity ranges are not confidence intervals. The highlighted interval is configured, not optimized.',
             ha='center', fontsize=9)
    caption = (f'Figure 5. Cumulative modeled absorbed dose over the {cfg["emergency_duration_hours"]:g}-hour '
               f'emergency window starting {cfg["emergency_start_utc"]}. Panels represent continuous residence '
               'in the external EVA reference and cabin reference, respectively, with separate linear dose '
               'axes explicitly labeled in mGy. These are reference environments, not strategy schedules. '
               'Hourly estimated rates are integrated as piecewise-constant bin averages, with cumulative '
               'dose set to zero at the window start. Connecting cumulative endpoints is exact within this '
               'bin model. Colored bands span all configured gap-filling methods and energy-threshold timing proxies; '
               'cumulative bounds are computed from whole trajectories, not by integrating pointwise rate '
               f'bounds. The highlighted {cfg["eva_duration_hours"]:g}-hour interval begins at emergency hour '
               f'{a:g}, set in configuration without peak searches or future-knowledge optimization. '
               'Annotated interval doses are increments within each reference environment, not an EVA/cabin '
               'switching strategy. Exact bin-overlap integration supports fractional-hour windows. '
               'All grid-target, event-closure and spectral-response limitations of Figure 4 apply. '
               'Bands are scenario sensitivity ranges, not confidence intervals.\n\n'
               'Data: outputs/model/historical/mission_radiation_environment.csv. Configuration: radiation_config.json.')
    finish(fig, 'historical/05_cumulative_exposure', caption, rect=(0, 0.13, 1, 0.93))


if __name__ == '__main__':
    main()

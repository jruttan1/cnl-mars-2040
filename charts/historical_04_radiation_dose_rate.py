"""Estimated hourly absorbed dose under a shared historical SPE timeline."""
import numpy as np
import matplotlib.pyplot as plt
from environment_common import load_historical as load, central, draw_envelopes, shade_gaps, finish, COLORS

# Change event timing, shielding and gap methods in radiation_config.json.
LOG_DOSE_AXIS = True  # Two references differ substantially; show both on one axis.


def main():
    cfg, mission, _, _, _ = load()
    fig, ax = plt.subplots(figsize=(11, 6))
    for location, spec in cfg['environments'].items():
        frame = mission[mission.location.eq(location)]
        curve = central(frame)
        draw_envelopes(ax, frame, cfg)
        edges = np.r_[curve.hour_since_emergency, curve.hour_end_since_emergency.iloc[-1]]
        ax.stairs(curve.absorbed_dose_rate_mGy_h, edges, baseline=None, color=COLORS[location], linewidth=2,
                  label=f'{spec["label"]} — {spec["shielding_g_cm2"]:g} g/cm² Al')
    shade_gaps(ax, curve)
    if LOG_DOSE_AXIS:
        ax.set_yscale('log')
    ax.set(xlim=(0, cfg['emergency_duration_hours']), xlabel='Hours since emergency begins',
           ylabel='Estimated absorbed dose rate [mGy/h]')
    ax.grid(axis='y', alpha=0.18)
    ax.legend(loc='upper right', frameon=True, framealpha=0.95)
    fig.suptitle('Historical King reference: absorbed-dose rate', fontsize=17, y=0.98)
    fig.text(0.5, 0.925, f'{cfg["emergency_start_utc"]} • {cfg["emergency_duration_hours"]:g} h window • '
             f'OLTARIS tissue depth {cfg["tissue_depth_g_cm2"]:g} g/cm²', ha='center', fontsize=10)
    fig.text(0.5, 0.025,
             'Colored bands: range from different gap-filling methods and proton-energy channels.\n'
             'Grey stripes: missing measurements filled by the model. Bands are not confidence intervals.\n'
             'Grid-based EVA/cabin references; full event dose allocated over the entire available OMNI record.',
             ha='center', fontsize=9)
    caption = (f'Figure 4. Estimated hourly absorbed-dose rates during the {cfg["emergency_duration_hours"]:g}-hour '
               f'illustrative emergency window beginning {cfg["emergency_start_utc"]}. Exact absorbed-dose values '
               'from the 0.4 and 20 g/cm² OLTARIS exports are selected at the common configured tissue depth '
               f'of {cfg["tissue_depth_g_cm2"]:g} g/cm². These event totals are distributed over the full available '
               f'OMNIWeb record using normalized hourly profiles. Central curves use the >{cfg["central_proxy_MeV"]} MeV '
               f'channel with {cfg["central_gap_method"]} filling of interior missing observations. Step heights '
               'are constant modeled rates within each hour; grey vertical strips identify gap-filled bins. '
               'Colored bands span all configured gap-filling methods and energy-threshold timing proxies. '
               'Each member is independently normalized '
               'over the full record, not the displayed window. The vertical axis is '
               + ('logarithmic. ' if LOG_DOSE_AXIS else 'linear. ') +
               'Ranges are pointwise sensitivity envelopes, not statistical confidence intervals or bounds '
               'on unobserved peaks. Temporal allocation assumes a fixed response through time and that '
               'the available record receives the full King event dose; spectral equivalence and physical '
               'event closure are unverified. References are grid-target estimates, not verified spacesuit, '
               'cabin geometry, or whole-body absorbed doses. No reactor radiation is included.\n\n'
               'Data: outputs/model/historical/mission_radiation_environment.csv. Configuration: radiation_config.json.')
    finish(fig, 'historical/04_radiation_dose_rate', caption)


if __name__ == '__main__':
    main()

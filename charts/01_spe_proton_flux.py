"""Measured August 1972 proton flux. Run from any directory."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import matplotlib.pyplot as plt
from common import save
from radiation.radiation_model import load_config, load_hourly

# Settings: thresholds are overlapping measurements; do not add them together.
THRESHOLDS_MEV = [10, 30, 60]
LOG_Y = True
SHOW = False


def main():
    cfg = load_config()
    data = load_hourly(cfg['historical_template'])
    fig, ax = plt.subplots(figsize=(10, 4))
    for energy in THRESHOLDS_MEV:
        ax.plot(data.hours_since_start, data[f'proton_flux_gt{energy}_MeV'], label=f'>{energy} MeV')
    ax.set(xlabel=f"Hours since first observation ({data.timestamp_utc.iloc[0]:%Y-%m-%d %H:%M UTC})",
           ylabel='Proton flux [protons/(cm²·s·sr)]' if cfg['historical_template']=='august_1972' else 'Reported integral proton flux\n(unit not recorded in CSV)',
           title=f"Measured {cfg['template_label']} — missing hours remain gaps")
    if LOG_Y:
        ax.set_yscale('log')
    ax.legend()
    save(fig, '01_spe_proton_flux.png', SHOW)


if __name__ == '__main__':
    main()

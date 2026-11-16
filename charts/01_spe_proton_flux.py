"""Measured August 1972 proton flux. Run from any directory."""
import matplotlib.pyplot as plt
from common import load, save

# Settings: thresholds are overlapping measurements; do not add them together.
THRESHOLDS_MEV = [10, 30, 60]
LOG_Y = True
SHOW = False


def main():
    data = load('spe_hourly.csv')
    fig, ax = plt.subplots(figsize=(10, 4))
    for energy in THRESHOLDS_MEV:
        ax.plot(data.hours_since_start, data[f'proton_flux_gt{energy}_MeV'], label=f'>{energy} MeV')
    ax.set(xlabel='Hours since first observation (1972-08-02 00:00 UTC)',
           ylabel='Proton flux [protons/(cm²·s·sr)]',
           title='Measured August 1972 SPE — missing hours remain gaps')
    if LOG_Y:
        ax.set_yscale('log')
    ax.legend()
    save(fig, '01_spe_proton_flux.png', SHOW)


if __name__ == '__main__':
    main()

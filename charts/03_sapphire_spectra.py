"""Clear comparison of event-total protons above selected energy thresholds."""
import numpy as np
import matplotlib.pyplot as plt
from common import ROOT, load, save

# Use exact tabulated energies; the source does not contain 30 or 60 MeV rows.
THRESHOLDS_MEV = [10, 32, 63]
SCENARIOS = {
    'SAPPHIRE-1-in-100': '100-year return-period event',
    'SAPPHIRE-1-in-1000': '1,000-year return-period event',
}
LOCATION = 'spacecraft'  # Alternative: 'model_1p2AU'
SHOW = False


def main():
    if LOCATION not in {'spacecraft', 'model_1p2AU'}:
        raise ValueError('LOCATION must be spacecraft or model_1p2AU')
    data = load('spe_scenarios.csv')
    column = f'{LOCATION}_integral_protons_cm2'
    # Select exact source rows. No interpolation, averaging, or dose conversion.
    values = []
    for scenario in SCENARIOS:
        selected = data[data.scenario_id == scenario].set_index('energy_MeV')
        if selected.index.has_duplicates or not set(THRESHOLDS_MEV).issubset(selected.index):
            raise ValueError(f'Missing or duplicate threshold values for {scenario}')
        totals = selected.loc[THRESHOLDS_MEV, column].to_numpy(dtype=float)
        if not np.isfinite(totals).all() or (totals < 0).any():
            raise ValueError(f'Invalid fluence for {scenario}')
        values.append(totals / 1e9)

    fig, ax = plt.subplots(figsize=(10, 5.8))
    x = np.arange(len(THRESHOLDS_MEV))
    width = 0.72 / len(SCENARIOS)
    for index, (label, totals) in enumerate(zip(SCENARIOS.values(), values)):
        positions = x + (index - (len(SCENARIOS) - 1) / 2) * width
        bars = ax.bar(positions, totals, width, label=label, edgecolor='white', linewidth=0.8, zorder=3)
        ax.bar_label(bars, labels=[f'{value:.4g}' for value in totals], padding=5, fontsize=11)
    ax.set_xticks(x, [f'{energy:g}' for energy in THRESHOLDS_MEV], fontsize=12)
    ax.set_ylabel(r'Integral event fluence, $\Phi(>E)$ [$10^9$ protons/cm²]', fontsize=11)
    ax.set_xlabel(r'Proton energy threshold, $E$ [MeV]', labelpad=12, fontsize=11)
    ax.set_ylim(0, np.max(values) * 1.25)
    ax.set_title('Integral solar-proton fluence by event return period', fontsize=16, loc='left', pad=40)
    ax.text(0, 1.025, f'SPENVIS / SAPPHIRE • {LOCATION} fluence • model at 1.2 AU • no magnetic shielding',
            transform=ax.transAxes, fontsize=10, color='0.35')
    ax.legend(frameon=False, loc='upper right', fontsize=11)
    ax.yaxis.grid(alpha=0.2, zorder=0)
    ax.spines[['top', 'right']].set_visible(False)
    fig.text(0.5, 0.015, 'Cumulative thresholds: each bar includes all protons above E; groups are not independent.\nExact tabulated values • Event-integrated quantities • No dose conversion',
             ha='center', fontsize=10)
    save(fig, '03_sapphire_spectra.png', SHOW, bottom_margin=0.09)
    thresholds = ', '.join(f'{e:g}' for e in THRESHOLDS_MEV)
    caption = (
        'Figure 3. Integral solar-proton event fluence for the SAPPHIRE '
        + ' and '.join(SCENARIOS.values()) + '. '
        f'Grouped bars show integral proton fluence above {thresholds} MeV, expressed in billions of protons '
        'per cm² (10^9 protons/cm²) over the entire event on a linear vertical axis starting at zero. Labels above the bars '
        'give values in these scaled units to four significant figures, consistent with the source report precision. '
        'Energy thresholds are displayed as equally spaced categorical groups, not a continuous energy axis. Each threshold uses an exact '
        f'tabulated energy from the SPENVIS/SAPPHIRE {LOCATION} columns; no interpolation is applied. '
        'The source table has no exact 30 or 60 MeV rows. The reports specify model fluence at 1.2 AU '
        'and no magnetic shielding. Threshold groups overlap: protons above a higher threshold are also '
        'included above lower thresholds, so the bars must not be added. Return periods label modeled '
        'event scenarios, not proportional increases in storm intensity. These totals do not represent '
        'hourly intensity, astronaut dose, or statistical uncertainty intervals.\n\n'
        'Data: data/processed/spe_scenarios.csv.\nScript: charts/03_sapphire_spectra.py.\n'
    )
    (ROOT / 'results/charts/03_sapphire_spectra.txt').write_text(caption, encoding='utf-8')


if __name__ == '__main__':
    main()

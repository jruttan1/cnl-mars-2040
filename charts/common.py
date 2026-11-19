"""Small shared loader; all charts read only the three consolidated CSVs."""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    allowed = {'spe_hourly.csv', 'shielding_dose.csv', 'spe_scenarios.csv'}
    if name not in allowed:
        raise ValueError(f'Choose one of {sorted(allowed)}')
    return pd.read_csv(ROOT / 'data/processed' / name)


def save(fig, filename, show=False, *, bottom_margin=0):
    destination = ROOT / 'results/charts' / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, bottom_margin, 1, 1))
    fig.savefig(destination, dpi=160)
    print(destination)
    if show:
        plt.show()
    plt.close(fig)

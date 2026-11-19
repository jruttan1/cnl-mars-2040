"""Shared display helpers for the new baseline figures; physics lives at project root."""
from pathlib import Path
import sys
import io
import hashlib
import shutil
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from radiation.radiation_model import ROOT, export_historical_environment, sensitivity_bounds, accumulated_dose, write_preserving

COLORS = {'external_eva_reference': '#b54525', 'spacecraft_cabin_reference': '#176a9b'}
SHOW = False


def load_historical():
    plt.rcParams.update({'font.size': 11, 'axes.titlesize': 12, 'axes.labelsize': 11,
                         'legend.fontsize': 9, 'axes.spines.top': False, 'axes.spines.right': False,
                         'savefig.dpi': 180})
    return export_historical_environment()


def central(frame):
    return frame[frame.estimate_type.eq('central')].sort_values('hour_since_emergency')


def draw_envelopes(ax, frame, cfg, cumulative=False):
    metric = 'cumulative_end_absorbed_dose_mGy' if cumulative else 'absorbed_dose_rate_mGy_h'
    color = COLORS[frame.location.iloc[0]]
    limits = sensitivity_bounds(frame, metric)
    if cumulative:
        x = np.r_[0, limits.index.to_numpy()+1]
        low, high = np.r_[0, limits.lower], np.r_[0, limits.upper]
        ax.fill_between(x, low, high, color=color, alpha=0.18, linewidth=0)
    else:
        x = np.r_[limits.index, limits.index[-1]+1]
        ax.fill_between(x, np.r_[limits.lower, limits.lower.iloc[-1]],
                        np.r_[limits.upper, limits.upper.iloc[-1]], step='post',
                        color=color, alpha=0.18, linewidth=0)


def shade_gaps(ax, frame):
    for hour in frame.loc[frame.is_gap_filled, 'hour_since_emergency']:
        ax.axvspan(hour, hour+1, color='0.4', alpha=0.10, linewidth=0, zorder=0)


def sensitivity_legend():
    return [Patch(facecolor='0.4', alpha=0.18, label='Range across timing assumptions')]


def finish(fig, stem, caption, rect=(0, 0.12, 1, 0.91)):
    fig.tight_layout(rect=rect)
    destination = ROOT / 'results/charts' / (stem + '.png')
    buffer = io.BytesIO()
    fig.savefig(buffer, format='png', dpi=180)
    content = buffer.getvalue()
    if destination.exists() and destination.read_bytes() != content:
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()[:16]
        backup = ROOT / 'data/raw/archive/model_output_versions' / (destination.name+'.'+digest)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(destination, backup)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    write_preserving(destination.with_suffix('.txt'), caption+'\n')
    print(destination)
    if SHOW:
        plt.show()
    plt.close(fig)

"""Exact SAPPHIRE SHIELDOSE-2 event doses at the six exported shielding depths."""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
from sapphire_common import SCENARIO_COLORS
from environment_common import finish
from radiation_model import load_config
from spenvis_audit import verified_shieldose_rows

LOG_DOSE_AXIS = True
LOG_SHIELDING_AXIS = True  # Spreads the six exported simulation coordinates clearly.


def main():
    cfg=load_config();dose=verified_shieldose_rows()
    fig,ax=plt.subplots(figsize=(12,6))
    for spec in cfg['synthetic_scenarios']:
        rows=dose[dose.scenario_id.eq(spec['scenario_id'])].sort_values('aluminum_areal_density_g_cm2')
        if rows.empty:raise ValueError(f'Missing verified dose: {spec["scenario_id"]}')
        label=f'{spec["return_period_years"]:,}-year — '+('main scenario' if spec['role']=='main' else 'extreme stress test')
        ax.plot(rows.aluminum_areal_density_g_cm2,rows.dose_value,marker='o',color=SCENARIO_COLORS[spec['role']],
                linestyle='-' if spec['role']=='main' else '--',lw=2,label=label)
    if LOG_DOSE_AXIS:ax.set_yscale('log')
    if LOG_SHIELDING_AXIS:ax.set_xscale('log')
    ax.set_xticks(np.sort(dose.aluminum_areal_density_g_cm2.unique()))
    ax.xaxis.set_major_formatter(ScalarFormatter());ax.minorticks_off()
    ax.set(xlabel='Aluminium shielding areal density [g/cm²]',ylabel='Event-integrated tissue-target absorbed dose (mGy)')
    ax.legend();ax.grid(alpha=0.18)
    fig.suptitle('SHIELDOSE-2 — Tissue-Target Absorbed Dose vs. Aluminium Shielding',fontsize=15,y=0.98)
    fig.text(0.5,0.925,'SAPPHIRE 100-year main scenario and 1,000-year extreme stress test • 4π irradiation',ha='center',fontsize=11)
    fig.text(0.5,0.025,'SHIELDOSE-2; tissue at centre of aluminium spheres; proton results without nuclear attenuation.\n'
             'Points: exported tissue-target results, not astronaut whole-body dose. Connecting lines are visual guides.',ha='center',fontsize=9)
    caption=('Figure 6. Event-integrated tissue-target absorbed dose versus aluminium areal density for the verified SAPPHIRE '
             '100-year main scenario and 1,000-year extreme stress test. All six markers per scenario are actual '
             'SHIELDOSE-2 numerical outputs (rad × 10 = mGy); lines are visual guides without numerical interpolation. '
             'SHIELDOSE-2; tissue at centre of aluminium spheres; proton results without nuclear attenuation. 4π irradiation. '
             f'Logarithmic dose axis: {LOG_DOSE_AXIS}; logarithmic shielding axis: {LOG_SHIELDING_AXIS}. '
             'These full-event totals do not depend on the selected temporal window and contain no OMNI or King dose normalization. '
             'They are not astronaut whole-body doses.\n\n'
             'Data: data/processed/shielding_dose.csv, verified rows only; originals and run-grouping evidence in '
             'data/raw/spenvis/verified_sapphire_manifest.json.')
    finish(fig,'06_shielding_sensitivity',caption)


if __name__=='__main__':main()

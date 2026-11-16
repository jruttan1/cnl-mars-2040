"""Supported synthetic event fluence over time, without claiming absorbed dose."""
import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from radiation_model import export_environment
from environment_common import finish

ENERGY_THRESHOLD_MEV = 10  # Must be an exact SAPPHIRE table coordinate (e.g. 10, 32, 63).
LOG_Y_AXIS = True  # Reveals the weaker tail; each major tick is a tenfold change.
COLORS = {'main':'#176a9b','worst_case':'#b54525'}


def main():
    result=export_environment()
    cfg=result['config'];profiles=result['profiles']
    window=profiles[profiles.in_emergency_window]
    center=window[window.estimate_type.eq('central')].sort_values('hour_since_emergency')
    bounds=window.groupby('hour_since_emergency').normalized_bin_weight.agg(['min','max'])
    edges=np.r_[center.hour_since_emergency,center.hour_since_emergency.iloc[-1]+1]
    fig,ax=plt.subplots(figsize=(11,6))
    for spec in cfg['synthetic_scenarios']:
        row=result['spectra'].loc[result['spectra'].scenario_id.eq(spec['scenario_id']) & result['spectra'].energy_MeV.eq(ENERGY_THRESHOLD_MEV)]
        if len(row)!=1: raise ValueError('Choose an exact exported SAPPHIRE energy threshold.')
        event_fluence=row.spacecraft_integral_protons_cm2.iloc[0]
        color=COLORS[spec['role']]
        label=f'{spec["return_period_years"]:,}-year event — {spec["role"].replace("_"," ")}'
        if LOG_Y_AXIS and (bounds['min'] <= 0).any():
            raise ValueError('Log scale requires positive fluence; choose a linear axis to display zero values.')
        ax.stairs(center.normalized_bin_weight*event_fluence,edges,baseline=None,color=color,lw=2,label=label,
                  linestyle='--' if spec['role']=='worst_case' else '-')
        low=bounds['min']*event_fluence;high=bounds['max']*event_fluence
        ax.fill_between(edges,np.r_[low,low.iloc[-1]],np.r_[high,high.iloc[-1]],step='post',color=color,alpha=0.13)
    ax.set(xlim=(0,cfg['emergency_duration_hours']),xlabel='Hours since emergency begins',
           ylabel=f'Hourly integral proton fluence (>{ENERGY_THRESHOLD_MEV:g} MeV) [protons/cm²]')
    if LOG_Y_AXIS:
        ax.set_yscale('log')
    else:
        ax.set_ylim(bottom=0)
        ax.ticklabel_format(axis='y',style='sci',scilimits=(0,0),useMathText=True)
    ax.legend();ax.grid(axis='y',alpha=0.15)
    fig.suptitle('Synthetic SAPPHIRE SPE scenarios',fontsize=18,y=0.98)
    fig.text(0.5,0.925,'August 1972 historical temporal template • 100-year main / 1,000-year worst-case',ha='center',fontsize=11)
    scale_note = 'Logarithmic y-axis: each major tick is a ×10 change; lower fluence remains visible.' if LOG_Y_AXIS else 'Linear y-axis: equal vertical distances represent equal fluence differences.'
    fig.text(0.5,0.025,scale_note+'\n'
             'Bands show timing sensitivity. Synthetic hourly fluence, not measured flux or absorbed dose.\n'
             'SAPPHIRE event totals are distributed over the full 264-hour historical template.',ha='center',fontsize=9)
    caption=(f'Figure 8. Synthetic SAPPHIRE SPE scenarios using an August 1972 historical temporal template, '
             f'for integral proton fluence above {ENERGY_THRESHOLD_MEV:g} MeV. The 100-year event is the main case '
             'and the 1,000-year event is the worst-case stress test. Each event fluence is allocated across '
             'the complete assumed 264-hour event using unit-sum OMNI timing weights. Only the configured '
             'emergency window is displayed. Central curves use the configured channel and gap method; bands '
             'span all nine timing alternatives and are not confidence intervals. A fixed spectrum over time '
             'is assumed. No conversion to absorbed dose, sr conversion or additional radial attenuation is made. '
             'The user reports 1.25 AU; exported reports display 1.2 AU and spacecraft/model spectra are equal. '
             'The 1972 timestamps identify the template, not a forecast for 2040.\n\n'
             'Data: data/processed/spe_scenarios.csv; outputs/model/synthetic_sapphire_temporal_weights.csv. '
             'Hourly spectral values: outputs/model/synthetic_sapphire_hourly_fluence.csv.')
    caption += '\n\n'+scale_note+' Axis scaling changes only the display, not the calculated fluence.'
    finish(fig,'08_synthetic_sapphire_proton_profile',caption)


if __name__=='__main__':
    main()

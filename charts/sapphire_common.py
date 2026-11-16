"""Presentation plots using the shared, verified synthetic SAPPHIRE model."""
import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from radiation_model import export_environment, MissingTransportError, accumulated_dose
from environment_common import finish

SCENARIO_COLORS={'main':'#176a9b','worst_case':'#b54525'}


def plot_dose(cumulative=False, roles=('main','worst_case')):
    try:
        result=export_environment(require_dose=True)
    except MissingTransportError as error:
        raise SystemExit(str(error)) from error
    cfg=result['config'];mission=result['mission']
    if cumulative:
        fig,axes=plt.subplots(2,1,figsize=(11,8),sharex=True)
    else:
        fig,ax=plt.subplots(figsize=(11,7))
        axes=[ax,ax]  # Both environments use one shared physical dose scale.
    metric='cumulative_end_absorbed_dose_mGy' if cumulative else 'absorbed_dose_rate_mGy_h'
    a=cfg['eva_start_hour'];b=a+cfg['eva_duration_hours']
    for ax,(location,env) in zip(axes,cfg['environments'].items()):
        interval_labels=[]
        reference_label='EVA shielding reference' if location=='external_eva_reference' else 'Cabin shielding reference'
        for spec in cfg['synthetic_scenarios']:
            if spec['role'] not in roles:continue
            frame=mission[mission.location.eq(location)&mission.scenario_id.eq(spec['scenario_id'])]
            if frame.empty:continue
            center=frame[frame.estimate_type.eq('central')].sort_values('hour_since_emergency')
            bounds=frame.groupby('hour_since_emergency')[metric].agg(['min','max'])
            edges=np.r_[center.hour_since_emergency,center.hour_end_since_emergency.iloc[-1]]
            color=SCENARIO_COLORS[spec['role']]
            style='-' if spec['role']=='main' else '--'
            label=f'{spec["return_period_years"]:,}-year — '+('main scenario' if spec['role']=='main' else 'extreme stress test')
            if not cumulative:
                environment_label='EVA' if location=='external_eva_reference' else 'Cabin'
                label=f'{spec["return_period_years"]:,}-year — {environment_label} ({env["shielding_g_cm2"]:g} g/cm² Al)'
            if cumulative:
                ax.plot(edges,np.r_[0,center[metric]],color=color,ls=style,lw=2,label=label)
                ax.fill_between(edges,np.r_[0,bounds['min']],np.r_[0,bounds['max']],color=color,alpha=0.13)
                interval_dose = accumulated_dose(center,a,b)
                display_dose = f"{interval_dose:.3g}" if interval_dose < 0.1 else f"{interval_dose:,.2f}"
                interval_labels.append(f'{spec["return_period_years"]:,}-year: {display_dose} mGy')
            else:
                ax.stairs(center[metric],edges,baseline=None,color=color,linestyle=style,lw=2,label=label)
                ax.fill_between(edges,np.r_[bounds['min'],bounds['min'].iloc[-1]],np.r_[bounds['max'],bounds['max'].iloc[-1]],step='post',color=color,alpha=0.13)
        if not cumulative:
            i=int(len(bounds)*0.60)
            ax.text(bounds.index[i],bounds['max'].iloc[i]*2.5,
                    f'{reference_label} · {env["shielding_g_cm2"]:g} g/cm² Al',
                    fontsize=10,weight='bold',color='#374151',
                    bbox=dict(facecolor='white',edgecolor='none',alpha=0.85))
        ax.set(title=f'{reference_label} — {env["shielding_g_cm2"]:g} g/cm² aluminium' if cumulative else '',
               xlim=(0,cfg['emergency_duration_hours']),
               ylabel='Cumulative modeled\ntissue-target dose (mGy)' if cumulative else 'Modeled tissue-target absorbed dose rate (mGy/h)')
        ax.yaxis.label.set_size(10)
        if cumulative:
            ax.set_ylim(bottom=0)
            ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
            ax.axvspan(a,b,color='#b78b20',alpha=0.15,zorder=0)
            ax.text(0.02,0.92,f'EVA interval {a:g}–{b:g} h: tissue-target dose\n'+'\n'.join(interval_labels),transform=ax.transAxes,
                    va='top',fontsize=9,bbox=dict(facecolor='white',alpha=0.9,edgecolor='none'))
        else:
            ax.set_yscale('log')
        ax.grid(axis='y',alpha=0.15)
    axes[-1].set_xlabel('Hours since emergency begins')
    handles,labels=axes[0].get_legend_handles_labels()
    if not cumulative:
        handles=handles[:len(roles)]
        labels=[f'{spec["return_period_years"]:,}-year — '+('main scenario' if spec['role']=='main' else 'extreme stress test')
                for spec in cfg['synthetic_scenarios'] if spec['role'] in roles]
    fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(0.5,0.075),ncol=2,frameon=False)
    title='Synthetic SPE — Cumulative Tissue-Target Absorbed Dose' if cumulative else 'Synthetic SPE — Tissue-Target Absorbed Dose Rate'
    fig.suptitle(title,fontsize=16,y=0.985)
    note='Separate linear dose scales' if cumulative else 'One shared logarithmic dose axis; each major tick = ×10'
    fig.text(0.5,0.94,f"SAPPHIRE • {cfg['template_label']} timing • "+note,ha='center',fontsize=10)
    fig.text(0.5,0.025,'SHIELDOSE-2; tissue at centre of aluminium spheres; proton results without nuclear attenuation.\n'
             'Shading: timing sensitivity, not confidence intervals. EVA/cabin are idealized shielding references, not verified hardware.',ha='center',fontsize=9)
    stem='05_cumulative_exposure' if cumulative else '04_radiation_dose_rate'
    caption=(f'{title} for synthetic SAPPHIRE SPE scenarios using the {cfg["template_label"]} historical temporal template. '
             'The 100-year event is the main scenario and the 1,000-year event is the extreme stress test. '
             'The references use exact 0.4 and 20 g/cm² SHIELDOSE-2 results for tissue at the centre of aluminium spheres, '
             '4π irradiation, without proton nuclear attenuation. Numerical rad values are converted using 1 rad = 10 mGy. '
             f"Event dose is allocated over all {cfg['template_duration_hours']} hourly bins; the configured window is only the displayed subset. "
             'Nine timing members compare three proton thresholds and three gap methods; bands are sensitivity envelopes, '
             'not confidence intervals or transport uncertainty. Gap methods coincide for complete GOES-10 data; only channel timing differs. A fixed spectrum through time is assumed. '
             f'Central timing: >{cfg["central_proxy_MeV"]} MeV, {cfg["central_gap_method"]}. '
             + (f'Cumulative dose starts at zero in the emergency window. Panels have separate linear y-scales. '
                f'The preselected {b-a:g}-hour interval starts at hour {a:g}; labels show the modeled tissue-target dose accumulated during that interval, not validated astronaut whole-body exposure. '
                'Hourly rates are integrated exactly over bin overlaps; cumulative envelopes use complete histories. ' if cumulative
                else 'Rates are piecewise constant within hourly bins. All four curves share one logarithmic y-axis. Identical time shapes are imposed by the common temporal template; shielding changes the dose magnitude. ') +
             'These are target-tissue calculations, not measured or verified whole-body astronaut doses. '
             'Run association and event-integrated interpretation were confirmed by the user and checked against source/report contents.\n\n'
             'Data: data/processed/mission_radiation_environment.csv; outputs/model/synthetic_sapphire_interval_exposure.csv. '
             'Settings: radiation_config.json. Source records: data/raw/spenvis/verified_sapphire_manifest.json.')
    finish(fig,stem,caption,rect=(0,0.14 if cumulative else 0.19,1,0.91))

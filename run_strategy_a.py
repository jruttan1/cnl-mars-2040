"""Run from the project root: python run_strategy_a.py --help."""
import argparse
from dataclasses import asdict, replace
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from sim.assumptions import DEFAULT_ASSUMPTIONS
from radiation_model import load_config, HISTORICAL_TEMPLATES
from sim.mission_simulator import simulate_mission
from sim.strategies import strategy_a

ROOT = Path(__file__).resolve().parent


def plot_timeline(result, path):
    fig, ax = plt.subplots(figsize=(12, 5))
    for i, a in enumerate(result.astronauts):
        ax.broken_barh([(0, result.current_mission_time)], (i-.3, .6), facecolors='#e2e8f0')
        for eva in result.progress:
            if eva.astronaut.name != a.name:continue
            duration = eva.reported_end_time-eva.start_time
            ax.broken_barh([(eva.start_time, duration)], (i-.3,.6),
                facecolors='#237a67' if eva.completed else '#bd573b',
                hatch=None if eva.completed else '//')
            ax.text(eva.start_time+duration/2, i, eva.repair_type,
                    ha='center',va='center',fontsize=9,color='white',rotation=0)
    ax.set(yticks=range(len(result.astronauts)),yticklabels=[a.name for a in result.astronauts],
           xlabel='Hours since emergency begins',xlim=(0,max(1,result.current_mission_time)),
           title='Strategy A — repair attempts and time inside the spacecraft')
    ax.grid(axis='x',alpha=.2)
    ax.legend(handles=[Patch(facecolor='#237a67',label='Completed EVA'),
        Patch(facecolor='#bd573b',hatch='//',label='Aborted EVA'),
        Patch(facecolor='#e2e8f0',label='Inside spacecraft')],loc='upper center',bbox_to_anchor=(.5,-.18),ncol=3)
    fig.text(.5,.015,'Operational assumptions only; repair completion is not proof of spacecraft survival or medical safety.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.09,1,1));path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(path,dpi=180);plt.close(fig)


def main():
    defaults = DEFAULT_ASSUMPTIONS
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario',choices=[defaults.default_spe_severity,defaults.worst_case_spe_severity],default=defaults.default_spe_severity)
    parser.add_argument('--template', choices=[name for name, info in HISTORICAL_TEMPLATES.items() if info['enabled']],
                        default=load_config()['historical_template'])
    parser.add_argument('--timing-variant',default=defaults.timing_variant)
    parser.add_argument('--engine',choices=['NTP','NEP'],default=defaults.engine_type)
    parser.add_argument('--storm-start',type=float,default=defaults.storm_start_hour)
    parser.add_argument('--max-hours',type=float,default=defaults.max_hours)
    parser.add_argument('--time-step',type=float,default=defaults.time_step_hours)
    parser.add_argument('--turnaround',type=float,default=defaults.turnaround_hours)
    parser.add_argument('--eva-time-cap',type=float,default=defaults.max_continuous_eva_hours)
    parser.add_argument('--estimated-external-rate',type=float,default=defaults.estimated_external_rate_mGy_h,
                        help='Optional fixed imperfect estimate, mGy/h; independent of the CSV')
    parser.add_argument('--estimated-cabin-rate',type=float,default=defaults.estimated_cabin_rate_mGy_h)
    parser.add_argument('--abort-threshold',type=float,default=defaults.radiation_abort_threshold_mGy,
                        help='Experimental estimated-dose policy parameter; NOT a medical limit')
    parser.add_argument('--restriction',type=float,nargs=2,action='append',default=None,metavar=('START','END'))
    args=parser.parse_args()
    cfg=replace(defaults, default_spe_severity=args.scenario, historical_template=args.template,
        timing_variant=args.timing_variant, storm_start_hour=args.storm_start,
        engine_type=args.engine, max_hours=args.max_hours,time_step_hours=args.time_step,
        turnaround_hours=args.turnaround,max_continuous_eva_hours=args.eva_time_cap,
        radiation_abort_threshold_mGy=args.abort_threshold,
        estimated_external_rate_mGy_h=args.estimated_external_rate,
        estimated_cabin_rate_mGy_h=args.estimated_cabin_rate,
        operational_restrictions=(defaults.operational_restrictions if args.restriction is None
                                  else tuple(tuple(x) for x in args.restriction)))
    result=simulate_mission(strategy_a,config=cfg)
    scenario=result.scenario
    out=ROOT/'outputs/strategy_a';out.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(result.event_log).to_csv(out/'event_log.csv',index=False)
    summary=dict(scenario=asdict(scenario),assumptions=asdict(cfg),
        quantity='idealized tissue-target absorbed dose (mGy)',status=result.status,
        mission_duration_hours=result.current_mission_time,required_repairs=result.required_repairs,
        completed_repairs=result.completed_repairs,
        outstanding_repairs=[r for r in result.required_repairs if r not in result.completed_repairs],
        crew=[asdict(a) for a in result.astronauts],
        evas=[{**{k:v for k,v in asdict(e).items() if k!='astronaut'},'astronaut':e.astronaut.name} for e in result.progress])
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    plot_timeline(result,ROOT/'outputs/charts/09_strategy_a_mission_timeline.png')
    print(f'Strategy A | {scenario.severity} | {scenario.historical_template} | {scenario.timing_variant} | {scenario.engine_type}')
    print(f'Mission hour 0 = storm hour {scenario.storm_start_hour:g}; outside {scenario.shielding:g}, inside {scenario.cabin_shielding:g} g/cm²')
    print('Required repairs:',', '.join(result.required_repairs))
    print('Abort policy:', 'time cap and preset restrictions; no reliable dose estimate' if args.estimated_external_rate is None else 'time cap, preset restrictions and assumed imperfect dose estimate')
    for e in result.progress:
        print(f'  {e.start_time:g}–{e.reported_end_time:g} h (planned end {e.scheduled_end_time:g}): {e.astronaut.name}, {e.repair_type}, '
              f'{"completed" if e.completed else "aborted"} — {e.end_reason}')
    for event in result.event_log:
        if event['action']=='wait':print(f'  Delay at {event["hour"]:g} h: {event["reason"]}')
    print(f'Status: {result.status}; {len(result.completed_repairs)}/{len(result.required_repairs)} repairs; duration {result.current_mission_time:g} h')
    for a in result.astronauts:
        print(f'  {a.name}: {a.accumulated_radiation:.6f} mGy modeled tissue-target dose; inside {a.inside_hours:g} h, outside {a.outside_hours:g} h')
    print('These are modeled target doses and assumed repair outcomes, not clinical or spacecraft survival predictions.')
    print('Saved: outputs/strategy_a/{summary.json,event_log.csv}; outputs/charts/09_strategy_a_mission_timeline.png')


if __name__=='__main__':main()

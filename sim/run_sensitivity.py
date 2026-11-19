"""Paired engineering sensitivity cases, not a probability-weighted Monte Carlo."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
from .run_comparison import positive_hours


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deadlines', nargs='+', type=positive_hours, default=[24., 48., 72.])
    parser.add_argument('--warning-holds', nargs='+', type=float, default=[0., 24.])
    parser.add_argument('--engines', nargs='+', choices=['NTP', 'NEP'], default=['NTP', 'NEP'])
    parser.add_argument('--severity', choices=['100', '1000'], default='100')
    parser.add_argument('--forecast-severity', choices=['100', '1000'], default='100')
    parser.add_argument('--output-dir', type=Path, default=Path('results/engineering_sensitivity'))
    parser.add_argument('--observation-hours', type=positive_hours)
    parser.add_argument('--continued-shelter-feasible', action='store_true')
    args = parser.parse_args()
    import math
    if any(not math.isfinite(h) or h < 0 for h in args.warning_holds):
        parser.error('Warning holds must be finite and nonnegative')
    if args.output_dir.exists():
        parser.error('Use a fresh output directory to preserve earlier experiments')
    args.output_dir.mkdir(parents=True)
    rows = []
    for engine in args.engines:
        for hold in sorted(set(args.warning_holds)):
            for deadline in sorted(set(args.deadlines)):
                folder = args.output_dir / f'{engine}_hold{hold:g}_deadline{deadline:g}'
                command = [sys.executable, '-B', '-m', 'sim.run_comparison', '--engine', engine,
                           '--repair-deadline', str(deadline), '--severity', args.severity,
                           '--forecast-severity', args.forecast_severity, '--output-dir', str(folder)]
                if hold:
                    command += ['--warning-hold', str(hold)]
                if args.observation_hours is not None:
                    command += ['--observation-hours', str(args.observation_hours)]
                if args.continued_shelter_feasible:
                    command += ['--continued-shelter-feasible']
                if engine == 'NEP':
                    command += ['--nep-access', 'protected']
                subprocess.run(command, check=True)
                summary = json.loads((folder / 'summary.json').read_text())
                if summary['recovery'][f'{engine.lower()}_repair_deadline_hours'] != deadline:
                    raise RuntimeError('Runner discarded the requested repair deadline')
                if engine == 'NEP' and summary['recovery']['nep_route_and_worksite_protected'] is not True:
                    raise RuntimeError('Runner discarded the explicit NEP access assumption')
                for strategy, entry in summary['strategies'].items():
                    rows.append(dict(engine=engine, warning_hold_h=hold, deadline_h=deadline,
                        strategy=strategy, status=entry['status'], elapsed_h=entry['elapsed_h'],
                        exposure_end_h=entry['exposure_observation_end_h'],
                        exposure_basis=entry['exposure_comparison_basis'],
                        repairs_completed=len(entry['repairs_completed']),
                        critical_repair_completed=entry['critical_repair_completed'],
                        repairs_completed_below_references=entry['repairs_completed_below_references'],
                        **{f'max_{k}_mGy_eq': v for k,v in entry['max_organ_mGy_eq'].items()}))
    with (args.output_dir / 'comparison.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    text = '''# Engineering sensitivity comparison

These are equally displayed hypothetical cases, not probabilities or mission-success rates.
Deadlines 24/48/72 h and procedural holds 0/24 h are illustrative defaults, not CNL facts or
validated engineering/procedural recommendations. NEP cases explicitly assume protected
routes AND worksites; unknown access remains prohibited in the main runner.
No reactor thermal transient, leak rate, reactor dose or guaranteed safe return is simulated.
A 0 h hold is an immediate-repair comparator, not a validated conservative SPE procedure.
All policies receive the same hold, deadline, damage, crew and true storm in each case.
Reference comparisons use the same BFO/skin/lens criteria for every policy.
Exposure observation endpoints and comparison bases are exported separately from recovery times.
Without a shared stated observation period, the below-reference comparison is unavailable;
low exposure at an early termination is not a benefit. Continued shelter after termination
requires an explicit feasibility assumption. A temporary hold advances time, not crew death.
All measurements and policy decisions are retained in individual case folders.

| Engine | Hold h | Deadline h | Strategy | Repairs | End h | BFO mGy-Eq | Repairs below all references |
|---|---:|---:|---|---:|---:|---:|---|
'''
    for r in rows:
        text += f"| {r['engine']} | {r['warning_hold_h']:g} | {r['deadline_h']:g} | {r['strategy']} | {r['repairs_completed']} | {r['elapsed_h']:g} | {r['max_BFO_mGy_eq']:.1f} | {r['repairs_completed_below_references']} |\n"
    (args.output_dir / 'README.md').write_text(text)


if __name__ == '__main__':
    main()

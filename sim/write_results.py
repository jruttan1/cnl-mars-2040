"""Compose RESULTS.md for a finished Monte Carlo folder, decision-level results first.

Reads only files the runner wrote (summary.json, trial_results.csv, manifest.json). Outcome rates
come after the decision comparison and are always shown with their spread across emergencies.
"""
import argparse
import csv
import json
from pathlib import Path
import statistics

from .decision_metrics import decision_report


def quantiles(values):
    values = sorted(values)
    if not values:
        return None
    pick = lambda q: values[min(len(values) - 1, int(round(q * (len(values) - 1))))]
    return pick(.1), pick(.5), pick(.9)


def load_rows(folder):
    with (folder / 'trial_results.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for key in ('repairs_completed', 'aborted_evas', 'max_BFO_mGy_eq', 'max_Skin_mGy_eq', 'max_Lens_mGy_eq',
                    'crew_mean_bfo_absorbed_mGy'):
            row[key] = float(row[key])
        for key in ('urgent_repair_on_time', 'all_repairs_completed'):
            row[key] = row[key] == 'True'
    return rows


def spread_table(rows):
    lines = ['| strategy | urgent repair on time | all four repairs | repairs completed p10 / median / p90 | '
             'aborted EVAs p10 / median / p90 | max BFO mGy-Eq p10 / median / p90 | max BFO ≥ 250 mGy-Eq |',
             '|---|---|---|---|---|---|---|']
    for label in 'BCD':
        group = [r for r in rows if r['strategy'] == label]
        n = len(group)
        fmt = lambda q: ' / '.join(f'{v:g}' if float(v).is_integer() else f'{v:.1f}' for v in q)
        lines.append(f"| {label} | {sum(r['urgent_repair_on_time'] for r in group) / n:.0%} | "
                     f"{sum(r['all_repairs_completed'] for r in group) / n:.0%} | "
                     f"{fmt(quantiles([r['repairs_completed'] for r in group]))} | "
                     f"{fmt(quantiles([r['aborted_evas'] for r in group]))} | "
                     f"{fmt(quantiles([r['max_BFO_mGy_eq'] for r in group]))} | "
                     f"{sum(r['max_BFO_mGy_eq'] >= 250 for r in group) / n:.1%} |")
    return lines


def paired_table(rows):
    index = {}
    for r in rows:
        index[(r['trial'], r['engine'], r['anatomy'], r['strategy'])] = r
    lines = ['| comparison (second minus first) | repairs completed: better / same / worse | median change | '
             'urgent on time: gained / lost | max BFO mGy-Eq median change |', '|---|---|---|---|---|']
    for first, second in (('B', 'C'), ('C', 'D'), ('B', 'D')):
        d_rep, d_bfo, gain, lose = [], [], 0, 0
        for (trial, engine, anatomy, label), a in index.items():
            if label != first:
                continue
            b = index[(trial, engine, anatomy, second)]
            d_rep.append(b['repairs_completed'] - a['repairs_completed'])
            d_bfo.append(b['max_BFO_mGy_eq'] - a['max_BFO_mGy_eq'])
            gain += b['urgent_repair_on_time'] and not a['urgent_repair_on_time']
            lose += a['urgent_repair_on_time'] and not b['urgent_repair_on_time']
        n = len(d_rep)
        lines.append(f"| {first} → {second} | {sum(v > 0 for v in d_rep)} / {sum(v == 0 for v in d_rep)} / "
                     f"{sum(v < 0 for v in d_rep)} of {n} | {statistics.median(d_rep):+g} | "
                     f"+{gain} / −{lose} | {statistics.median(d_bfo):+.2f} |")
    return lines


def write(folder):
    folder = Path(folder)
    summary = json.loads((folder / 'summary.json').read_text())
    manifest = json.loads((folder / 'manifest.json').read_text())
    rows = load_rows(folder)
    config = manifest['config']
    lines = [f'# Results: {folder.name}', '',
             'Conditional frequencies under the configured hypothetical emergency distribution, not mission probabilities. '
             f"{config['trials']} emergencies × {len(config['engines'])} engines × {len(config['anatomies'])} reference "
             'anatomies; every strategy faces the identical emergency and measurement seed.', '',
             decision_report(summary['decision_metrics']),
             '## Outcomes, with spread across emergencies', '', *spread_table(rows), '',
             '## Paired change per emergency', '', *paired_table(rows), '',
             '## Settings that shape these results (team assumptions, not CNL facts)', '',
             f"- Forecast stress allowance weight: {config.get('forecast_stress_weight')}",
             f"- Abort progress credit: {config.get('abort_progress_credit')} (share of hours worked kept toward the repair)",
             f"- Retry after abort for every strategy: {config.get('retry_after_abort')}, restart review {config.get('restart_quiet_hours')} h",
             f"- B forecast projection: {config.get('b_projection')}; matched current-rate mode: {config.get('matched_current_rate')}",
             f"- Urgent repair deadline (h): {config['urgent_deadline_h']}; EVA work (h): {config['eva_work_hours']}",
             '', 'Exposure levels are BFO Gray Equivalent against the 250 mGy-Eq reference; that reference is not a symptom threshold.']
    (folder / 'RESULTS.md').write_text('\n'.join(lines) + '\n')
    return folder / 'RESULTS.md'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    print(write(parser.parse_args().folder))


if __name__ == '__main__':
    main()

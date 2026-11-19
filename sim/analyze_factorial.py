"""Attribute outcome differences to the forecast stress tail and the restart rule.

Reads four Monte Carlo output folders that share every emergency draw and differ
only in ``forecast_stress_weight`` and ``restart_quiet_hours``. Reports paired
effects with trial-clustered intervals (engine/anatomy cohorts reuse each draw, so
the 100 emergencies, not the 400 cases, are the independent units) and classifies
where B, C and D first choose differently. Diagnostic, not a new experiment.
"""
import argparse
import json
import math
from pathlib import Path
import statistics

from radiation.radiation_model import ROOT

CELLS = {('stress', 'noretry'): 'stress_noretry', ('nostress', 'noretry'): 'nostress_noretry',
         ('stress', 'retry'): 'stress_retry', ('nostress', 'retry'): 'nostress_retry'}
METRICS = {
    'urgent_on_time': lambda e: float(e['critical_repair_completed_before_deadline'] is True),
    'all_repairs': lambda e: float(e['all_repairs_completed']),
    'repairs_completed': lambda e: float(len(e['repairs_completed'])),
    'aborted_evas': lambda e: float(e['aborted_evas']),
    'evas_started': lambda e: float(len(e['evas'])),
    'any_reference_exceeded': lambda e: float(e['any_organ_reference_exceeded']),
    'max_BFO_mGy_eq': lambda e: e['max_organ_mGy_eq']['BFO'],
    'crew_mean_BFO_absorbed_mGy': lambda e: e['crew_mean_bfo_absorbed_mGy'],
}


def load(folder):
    records = {}
    for path in sorted(Path(folder).glob('trial_*.json')):
        record = json.loads(path.read_text())
        records[record['draw']['trial'], record['engine'], record['anatomy']] = record
    return records


def clustered(values_by_trial):
    """Mean and normal 95% interval over independent emergencies."""
    means = [statistics.mean(v) for v in values_by_trial.values()]
    mean = statistics.mean(means)
    if len(means) < 2:
        return mean, None
    radius = 1.96 * statistics.stdev(means) / math.sqrt(len(means))
    return mean, (mean - radius, mean + radius)


def paired(data, label, metric, left, right, engine=None):
    """Mean of metric(left) - metric(right) per emergency, plus flip counts."""
    by_trial, up, down = {}, 0, 0
    for key, a in data[left].items():
        if engine and key[1] != engine:
            continue
        b = data[right][key]
        x, y = METRICS[metric](a['strategies'][label]), METRICS[metric](b['strategies'][label])
        by_trial.setdefault(key[0], []).append(x - y)
        up += x > y
        down += x < y
    mean, interval = clustered(by_trial)
    return mean, interval, up, down


def level(data, label, metric, cell, engine=None):
    by_trial = {}
    for key, record in data[cell].items():
        if not engine or key[1] == engine:
            by_trial.setdefault(key[0], []).append(METRICS[metric](record['strategies'][label]))
    return clustered(by_trial)


def fmt(mean, interval, digits=3):
    return (f'{mean:+.{digits}f}' if interval is None else
            f'{mean:+.{digits}f} [{interval[0]:+.{digits}f}, {interval[1]:+.{digits}f}]')


def signature(entry):
    return [(round(d['hour'], 2), d['action'], d.get('astronaut'), d.get('repair'))
            for d in entry['reassessment_audit']['decisions']]


def first_difference(a, b):
    """Classify the first point at which two decision sequences separate."""
    for index, (x, y) in enumerate(zip(a, b)):
        if x != y:
            if x[1] != y[1]:
                return 'different action (%s vs %s)' % (x[1], y[1])
            if x[3] != y[3]:
                return 'different repair'
            if x[2] != y[2]:
                return 'different crew member'
            return 'same start, different time'
    if len(a) != len(b):
        return 'one strategy takes extra decisions'
    return 'identical'


def divergence(data, cell):
    rows = {}
    for left, right in (('B', 'C'), ('C', 'D'), ('B', 'D')):
        counts, outcome_same, outcome_diff = {}, 0, 0
        for record in data[cell].values():
            a, b = record['strategies'][left], record['strategies'][right]
            kind = first_difference(signature(a), signature(b))
            counts[kind] = counts.get(kind, 0) + 1
            if kind != 'identical':
                same = all(METRICS[m](a) == METRICS[m](b) for m in
                           ('urgent_on_time', 'all_repairs', 'aborted_evas', 'max_BFO_mGy_eq'))
                outcome_same += same
                outcome_diff += not same
        rows[f'{left} vs {right}'] = dict(first_difference=counts, divergent_with_same_outcome=outcome_same,
                                          divergent_with_different_outcome=outcome_diff)
    return rows


def report(data):
    lines = ['# Forecast stress tail × restart rule: factorial attribution', '',
             'Same 100 emergencies × NTP/NEP × MAX/FAX in every cell; intervals cluster on emergency.',
             'Frequencies are conditional on the configured hypothetical distribution, not mission probabilities.', '']
    cells = {key: name for key, name in CELLS.items()}
    lines += ['## Level in each cell', '',
              '| strategy | metric | ' + ' | '.join(f'{s}/{r}' for s, r in cells) + ' |',
              '|---|---|' + '---|' * len(cells)]
    for label in 'BCD':
        for metric in METRICS:
            row = [f'{level(data, label, metric, name)[0]:.3f}' for name in cells.values()]
            lines.append(f'| {label} | {metric} | ' + ' | '.join(row) + ' |')
    lines += ['', '## Paired effects (first minus second; flips = emergencies where it went up / down)', '']
    contrasts = [('stress tail removed, no retry rule', 'nostress_noretry', 'stress_noretry'),
                 ('stress tail removed, retry rule on', 'nostress_retry', 'stress_retry'),
                 ('retry rule added, stress tail on', 'stress_retry', 'stress_noretry'),
                 ('retry rule added, stress tail off', 'nostress_retry', 'nostress_noretry'),
                 ('both changed together', 'nostress_retry', 'stress_noretry')]
    lines += ['| strategy | contrast | metric | effect [95% CI] | up | down |', '|---|---|---|---|---|---|']
    for label in 'BCD':
        for title, left, right in contrasts:
            for metric in ('urgent_on_time', 'all_repairs', 'aborted_evas', 'max_BFO_mGy_eq', 'any_reference_exceeded'):
                mean, interval, up, down = paired(data, label, metric, left, right)
                lines.append(f'| {label} | {title} | {metric} | {fmt(mean, interval)} | {up} | {down} |')
    lines += ['', '## Interaction (does the retry effect depend on the stress tail?)', '',
              '| strategy | metric | (retry effect, tail off) − (retry effect, tail on) |', '|---|---|---|']
    for label in 'BCD':
        for metric in ('urgent_on_time', 'all_repairs', 'aborted_evas', 'max_BFO_mGy_eq'):
            by_trial = {}
            for key in data['stress_noretry']:
                v = [METRICS[metric](data[c][key]['strategies'][label])
                     for c in ('nostress_retry', 'nostress_noretry', 'stress_retry', 'stress_noretry')]
                by_trial.setdefault(key[0], []).append((v[0] - v[1]) - (v[2] - v[3]))
            lines.append(f'| {label} | {metric} | {fmt(*clustered(by_trial))} |')
    lines += ['', '## Where B, C and D first choose differently', '']
    for name in cells.values():
        lines += [f'### {name}', '']
        for pair, row in divergence(data, name).items():
            lines.append(f'- **{pair}**: {row["first_difference"]}; divergent decisions with the same '
                         f'outcome: {row["divergent_with_same_outcome"]}, with a different outcome: '
                         f'{row["divergent_with_different_outcome"]}')
        lines.append('')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=ROOT / 'results/monte-carlo')
    parser.add_argument('--prefix', default='factorial_')
    parser.add_argument('--output', type=Path, default=ROOT / 'results/monte-carlo/factorial_RESULTS.md')
    args = parser.parse_args()
    data = {name: load(args.base / f'{args.prefix}{name}') for name in CELLS.values()}
    keys = {name: set(records) for name, records in data.items()}
    if len({frozenset(k) for k in keys.values()}) != 1:
        raise SystemExit('Cells do not contain identical emergencies; refusing to pair them')
    args.output.write_text(report(data) + '\n')
    print(args.output)


if __name__ == '__main__':
    main()

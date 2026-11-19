"""Decision-level comparison of B, C and D on the same emergencies.

The experiment's question is whether different information changes decisions, so these
metrics come first and outcome rates second. Everything here is computed from the compact
decision log stored in each checkpoint; nothing is re-simulated and no truth is consulted.
"""
import re
import statistics

ACTING = ('start', 'abort')
KEEP = ('start', 'abort', 'wait', 'safe_hold', 'completed', 'returned', 'stabilize')
RISK_TOLERANCE = 0.05
PCT = re.compile(r'(\d+\.?\d*)%')


def reason_category(action, reason):
    """Coarse, mutually exclusive label for the rule that produced a decision."""
    r = reason
    if 'In-EVA biomarker' in r:
        return 'in-EVA biomarker assessment'
    if 'Lower projected exposure' in r:
        return 'dose-saving wait'
    if 'Repeat EVA suspended' in r or 'Urgent repair chain blocked' in r:
        return 'repair held after radiation abort'
    if 'Crew reassessment' in r:
        return 'post-abort crew reassessment'
    if 'H2AX review' in r or 'post-EVA crew exposure review' in r:
        return 'post-EVA review hold'
    if 'Restart after sustained improvement' in r or 'Restart requires' in r:
        return 'restart review'
    if 'turnaround' in r or 'Insufficient' in r:
        return 'operational timing'
    if 'Reassess before candidate departure' in r:
        return 'waiting for a forecast-chosen departure window'
    if 'Forecast coverage' in r:
        return 'forecast coverage'
    if 'robability of any organ reference exceedance' in r or 'Biomarkers conflict' in r:
        return 'risk gate'
    if 'selected crew by projected exposure' in r:
        return 'risk gate'
    return 'other'


def compact_log(event_log):
    """Decisions only, consecutive repeats merged, with the quoted risk probability."""
    rows = []
    for event in event_log:
        if event['action'] not in KEEP:
            continue
        match = PCT.search(event['reason'])
        row = dict(hour=round(event['hour'], 3), action=event['action'], astronaut=event.get('astronaut'),
                   repair=event.get('repair'), cat=reason_category(event['action'], event['reason']),
                   p=float(match.group(1)) / 100 if match else None)
        if rows and event['action'] in ('wait', 'safe_hold') and all(
                rows[-1][k] == row[k] for k in ('action', 'astronaut', 'repair', 'cat', 'p')):
            continue
        rows.append(row)
    return rows


def signature(entry):
    return [(row['hour'], row['action'], row['astronaut'], row['repair'])
            for row in entry['decision_log'] if row['action'] in ACTING]


def first_divergence(a, b):
    """Return (kind, hour) of the first point two decision sequences separate, or None."""
    sa, sb = signature(a), signature(b)
    for x, y in zip(sa, sb):
        if x != y:
            hour = min(x[0], y[0])
            if x[1] != y[1]:
                return 'different action', hour
            if x[3] != y[3]:
                return 'different repair', hour
            if x[2] != y[2]:
                return 'different crew member', hour
            return 'same decision, different time', hour
    if len(sa) != len(sb):
        longer = sa if len(sa) > len(sb) else sb
        return 'one strategy makes an extra decision', longer[min(len(sa), len(sb))][0]
    return None


def _exact(entry, hour):
    rows = [r for r in entry['decision_log'] if abs(r['hour'] - hour) < 1e-6 and r['action'] in ACTING]
    return rows[-1] if rows else None


def _latest(entry, hour):
    """The strategy's most recent decision at or before `hour`."""
    rows = [r for r in entry['decision_log'] if r['hour'] <= hour + 1e-6
            and r['action'] in ('start', 'abort', 'wait', 'safe_hold')]
    return rows[-1] if rows else None


def cause(a, b, kind, hour):
    """Why the two strategies separated at `hour`, using only what each one logged then."""
    ea, eb = _exact(a, hour), _exact(b, hour)
    if kind == 'different crew member':
        return 'different crew chosen'
    if ea is None and eb is None:
        return 'unattributed (no acting decision at that hour)'
    # The acting strategy launched/aborted; the other was doing something else at that hour.
    actor_entry, other_entry = (a, b) if ea is not None and (eb is None or ea['action'] != eb['action']) else (b, a)
    actor = _exact(actor_entry, hour)
    other = _latest(other_entry, hour)
    if other is None:
        return 'unattributed (other strategy had logged nothing)'
    if other['action'] in ACTING:
        # The other strategy was mid-EVA or had launched earlier: an in-EVA or timing difference.
        return 'in-EVA assessment differed' if actor['action'] == 'abort' else 'launch timing differed'
    if actor['action'] == 'abort':
        return 'in-EVA assessment differed'
    if other['cat'] == 'risk gate':
        if actor['p'] is not None and other['p'] is not None and (
                (actor['p'] <= RISK_TOLERANCE) != (other['p'] <= RISK_TOLERANCE)):
            return 'estimated risk fell on opposite sides of the gate'
        return 'risk gate, same side (timing/crew rule)'
    return other['cat']


EVIDENCE_CAUSES = ('estimated risk fell on opposite sides of the gate', 'in-EVA assessment differed',
                   'in-EVA biomarker assessment', 'dose-saving wait')


def outcome_vector(entry):
    # Exposure differs whenever timing differs, so compare the mission-relevant outcomes only.
    return (entry['critical_repair_completed_before_deadline'] is True, len(entry['repairs_completed']),
            entry['aborted_evas'])


def pair_metrics(records, left, right):
    divergent, kinds, causes, hours, same_outcome = 0, {}, {}, [], 0
    for record in records:
        a, b = record['strategies'][left], record['strategies'][right]
        found = first_divergence(a, b)
        if found is None:
            continue
        kind, hour = found
        divergent += 1
        kinds[kind] = kinds.get(kind, 0) + 1
        why = cause(a, b, kind, hour)
        causes[why] = causes.get(why, 0) + 1
        hours.append(hour)
        same_outcome += outcome_vector(a) == outcome_vector(b)
    n = len(records)
    return dict(pair=f'{left} vs {right}', emergencies=n, different_decisions=divergent,
                different_decisions_fraction=divergent / n if n else None,
                median_first_divergence_h=statistics.median(hours) if hours else None,
                first_divergence_kind=dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
                first_divergence_cause=dict(sorted(causes.items(), key=lambda kv: -kv[1])),
                evidence_or_in_eva_cause_fraction=(sum(v for k, v in causes.items() if k in EVIDENCE_CAUSES) / divergent
                                                   if divergent else None),
                divergent_with_identical_outcome=same_outcome)


def strategy_profile(records, label):
    starts = aborts = retries = waits = 0
    credited = []
    for record in records:
        entry = record['strategies'][label]
        starts += sum(r['action'] == 'start' for r in entry['decision_log'])
        aborts += entry['aborted_evas']
        seen = {}
        for eva in sorted(entry['evas'], key=lambda e: e['start_h']):
            if seen.get(eva['repair']):
                retries += 1
            seen[eva['repair']] = eva['aborted']
            credited.append(eva.get('work_credited_h', 0.0))
        waits += sum(r['action'] in ('wait', 'safe_hold') and r['cat'] not in ('operational timing',)
                     for r in entry['decision_log'])
    n = len(records)
    cats = {}
    for record in records:
        for row in record['strategies'][label]['decision_log']:
            if row['action'] in ('wait', 'safe_hold'):
                cats[row['cat']] = cats.get(row['cat'], 0) + 1
    return dict(strategy=label, emergencies=n, mean_launch_decisions=starts / n, mean_aborts=aborts / n,
                mean_retries_after_abort=retries / n, mean_credited_work_h=sum(credited) / n,
                hold_or_wait_decisions_by_rule=dict(sorted(cats.items(), key=lambda kv: -kv[1])))


def decision_metrics(records):
    out = dict(pairs=[pair_metrics(records, a, b) for a, b in (('B', 'C'), ('C', 'D'), ('B', 'D'))],
               profiles=[strategy_profile(records, label) for label in 'BCD'])
    by_engine = {}
    for engine in sorted({r['engine'] for r in records}):
        group = [r for r in records if r['engine'] == engine]
        by_engine[engine] = [pair_metrics(group, a, b) for a, b in (('B', 'C'), ('C', 'D'), ('B', 'D'))]
    out['by_engine'] = by_engine
    return out


def decision_report(metrics):
    lines = ['## Decision differences between strategies (same emergencies)', '',
             'A "different decision" means the sequence of EVA launches/aborts (time, crew, repair) differs. '
             'At hour 0 all strategies hold identical information, so identical early decisions are expected.', '',
             '| pair | emergencies with different decisions | median first-divergence hour | caused by evidence / in-EVA readings | same final outcome anyway |',
             '|---|---|---|---|---|']
    for row in metrics['pairs']:
        median = row['median_first_divergence_h']
        share = row['evidence_or_in_eva_cause_fraction']
        lines.append(f"| {row['pair']} | {row['different_decisions']}/{row['emergencies']} "
                     f"({row['different_decisions_fraction']:.0%}) | {'-' if median is None else f'{median:.1f}'} | "
                     f"{'-' if share is None else f'{share:.0%}'} | {row['divergent_with_identical_outcome']} |")
    lines += ['', '### What separated them first', '']
    for row in metrics['pairs']:
        lines.append(f"- **{row['pair']}** kind: {row['first_divergence_kind'] or 'none'}; cause: {row['first_divergence_cause'] or 'none'}")
    lines += ['', '### Decision profile per strategy (per emergency)', '',
              '| strategy | launches | aborts | retries after abort | work hours credited | hold/wait decisions by rule |',
              '|---|---|---|---|---|---|']
    for p in metrics['profiles']:
        lines.append(f"| {p['strategy']} | {p['mean_launch_decisions']:.2f} | {p['mean_aborts']:.2f} | "
                     f"{p['mean_retries_after_abort']:.2f} | {p['mean_credited_work_h']:.2f} | {p['hold_or_wait_decisions_by_rule']} |")
    return '\n'.join(lines) + '\n'

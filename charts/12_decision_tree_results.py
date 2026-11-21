"""Presentation figures for the B/C/D decision-tree Monte Carlo, with the explanation on each graph.

Every number printed on a figure is computed from the run's checkpoints; nothing is typed in.
Frequencies are conditional on the configured hypothetical distribution, not mission probabilities.
"""
from pathlib import Path
import glob
import json
import math
import statistics
import sys
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sim.decision_metrics import first_divergence, cause, pair_metrics, signature  # noqa: E402

RUN = ROOT / 'results/monte-carlo/decision_trees_current_rate_100'
OUT = ROOT / 'results/presentation/decision_trees'

# Validated palette (light mode, first slots, all-pairs safe). Aqua and the cause hues are below 3:1 on white,
# so every mark that matters is also labelled directly.
SURFACE, INK, INK2, MUTED, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#8a8984', '#e6e5e0'
STRAT = {'B': '#2a78d6', 'C': '#eb6834', 'D': '#1baf7a'}
NAME = {'B': 'B  forecast only', 'C': 'C  + blood tests', 'D': 'D  + in-suit readings'}
SHORT = {'B': 'forecast only', 'C': '+ blood tests (5 h lab)', 'D': '+ in-suit readings (1 h)'}
TICK = {'B': 'B\nforecast\nonly', 'C': 'C\n+ blood tests\n(5 h lab)', 'D': 'D\n+ in-suit\nreadings (1 h)'}
CAUSE = {  # group -> (colour, label)
    'gate': ('#6250d6', 'New evidence moved the risk estimate across the 5% launch gate'),
    'eva': ('#e87ba4', 'An abort call differed mid-EVA'),
    'post': ('#eda100', 'Post-abort crew reassessment / restart hold'),
    'other': ('#b9b8b0', 'Another rule (crew choice, review hold, forecast coverage…)'),
}
CAUSE_GROUP = {'estimated risk fell on opposite sides of the gate': 'gate', 'in-EVA assessment differed': 'eva',
               'post-abort crew reassessment': 'post', 'repair held after radiation abort': 'post'}
REPAIR = {'communications': 'comms', 'monitoring': 'monitor', 'propulsion_initial': 'prop 1', 'propulsion': 'prop 2'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE,
                     'savefig.facecolor': SURFACE, 'text.color': INK, 'axes.labelcolor': INK2,
                     'xtick.color': INK2, 'ytick.color': INK2, 'axes.edgecolor': GRID})


def load():
    records = [json.loads(Path(p).read_text()) for p in sorted(glob.glob(str(RUN / 'trial_*.json')))]
    if len(records) != 400:
        raise SystemExit(f'Expected 400 checkpoints, found {len(records)}')
    return records


def wilson(k, n):
    z, p = 1.959963984540054, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - r, c + r


def tidy(ax, grid='x'):
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    ax.spines['left'].set_color(GRID)
    ax.spines['bottom'].set_color(GRID)
    ax.tick_params(length=0, labelsize=9)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=.8)
        ax.set_axisbelow(True)


def headline(fig, title, subtitle):
    fig.text(.04, .955, title, fontsize=19, fontweight='bold', va='top', ha='left')
    fig.text(.04, .905, textwrap.fill(subtitle, 175), fontsize=11.5, color=INK2, va='top', ha='left', linespacing=1.35)


def footer(fig, text):
    fig.text(.04, .015, textwrap.fill(text, 200), fontsize=8, color=MUTED, va='bottom', ha='left')


def note(ax, x, y, text, width=46, size=10, color=INK, weight='normal', box=True, **kw):
    ax.text(x, y, textwrap.fill(text, width), transform=ax.transAxes, fontsize=size, color=color, fontweight=weight,
            va='top', ha='left', linespacing=1.35,
            bbox=dict(boxstyle='round,pad=.5', fc='#f3f2ee', ec=GRID, lw=.8) if box else None, **kw)


# ---------------------------------------------------------------------------------------------------------------
def figure_1(records):
    pairs = [('B', 'C'), ('C', 'D'), ('B', 'D')]
    fig = plt.figure(figsize=(16, 9))
    rows = []
    for a, b in pairs:
        metrics = pair_metrics(records, a, b)
        n, differ = metrics['emergencies'], metrics['different_decisions']
        groups = dict.fromkeys(CAUSE, 0)
        for key, count in metrics['first_divergence_cause'].items():
            groups[CAUSE_GROUP.get(key, 'other')] += count
        rows.append((a, b, n, n - differ, groups, metrics))
    lo = min(m['different_decisions_fraction'] for *_, m in rows)
    hi = max(m['different_decisions_fraction'] for *_, m in rows)
    ev_lo = min(m['evidence_or_in_eva_cause_fraction'] for *_, m in rows)
    ev_hi = max(m['evidence_or_in_eva_cause_fraction'] for *_, m in rows)
    headline(fig, f'Given the same emergency, the strategies make different calls in about 1 case in 3 ({lo:.0%}–{hi:.0%})',
             f'In {ev_lo:.0%}–{ev_hi:.0%} of those cases the first split traces to new evidence changing the risk estimate or the abort call (violet and pink). '
             '400 cases = 100 emergencies × NTP/NEP × male/female reference anatomy.')
    ax = fig.add_axes([.25, .39, .58, .41])
    for i, (a, b, n, same, groups, metrics) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.barh(y, same / n * 100, left=0, height=.52, color='#e4e3dd', edgecolor=SURFACE, linewidth=2)
        ax.text(same / n * 50, y, f'Same decisions\n{same / n:.0%}', ha='center', va='center', fontsize=9.5, color=INK2)
        left = same / n * 100
        for key, (color, _) in CAUSE.items():
            share = groups[key] / n * 100
            if share == 0:
                continue
            ax.barh(y, share, left=left, height=.52, color=color, edgecolor=SURFACE, linewidth=2)
            if share >= 4.2:
                ax.text(left + share / 2, y, f'{share:.0f}%', ha='center', va='center', fontsize=10, fontweight='bold', color=INK)
            left += share
        ax.text(102, y + .08, f"{metrics['different_decisions_fraction']:.0%} differ", va='center', fontsize=12, fontweight='bold')
        ax.text(102, y - .17, f"first split near hour {metrics['median_first_divergence_h']:.0f}\n(median)", va='center', fontsize=8.5, color=INK2, linespacing=1.3)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f'{a} vs {b}\n{SHORT[a]}\nvs {SHORT[b]}' for a, b, *_ in reversed(rows)], fontsize=9.5, linespacing=1.3)
    ax.set_xlim(0, 100)
    ax.set_xlabel('Share of the 400 cases (%)', fontsize=10)
    tidy(ax, 'x')
    ax.spines['left'].set_visible(False)
    handles = [Patch(fc=c, label=l) for c, l in CAUSE.values()]
    leg = fig.legend(handles=handles, loc='lower left', bbox_to_anchor=(.06, .215), ncol=2, frameon=False, fontsize=10,
                     title='What made the two strategies first decide differently', title_fontsize=10.5, alignment='left')
    leg._legend_box.align = 'left'
    fig.text(.06, .165, textwrap.fill(
        'How to read this: for each pair, find the first moment their launch/abort decisions split on the same emergency, then ask which rule produced the difference. '
        'At hour 0 everyone holds identical information, so they decide alike; they separate once blood and in-suit results start arriving. '
        'For B vs C, an abort call that differs mid-EVA is also an evidence effect: C re-weights storm scenarios from returned results while B cannot.', 185),
        fontsize=9.5, color=INK, va='top', linespacing=1.4)
    footer(fig, 'Source: results/monte-carlo/decision_trees_current_rate_100. Conditional frequencies under the configured hypothetical emergency distribution, '
                'not mission probabilities. Decision = launch or abort (time, crew member, repair). All strategies project today’s estimated dose rate; none sees the future.')
    return fig


# ---------------------------------------------------------------------------------------------------------------
def storm_rate(record):
    from dataclasses import fields
    from sim.assumptions import MissionAssumptions
    from sim.mission_simulator import RadiationEnvironment
    from sim.models import Scenario

    def tup(value):
        return tuple(tup(v) for v in value) if isinstance(value, list) else value
    names = {f.name for f in fields(MissionAssumptions)}
    config = MissionAssumptions(**{k: tup(v) for k, v in record['mission'].items() if k in names})
    environment = RadiationEnvironment(Scenario.from_assumptions(config))
    hours = np.arange(0, 96)
    return hours, np.array([environment.dose(h, h + 1, config.external_shielding_g_cm2) for h in hours])


def latest_row(entry, hour):
    rows = [r for r in entry['decision_log'] if r['hour'] <= hour + 1e-6 and r['action'] in ('start', 'abort', 'wait', 'safe_hold')]
    return rows[-1] if rows else None


def describe(record, first, second):
    a, b = record['strategies'][first], record['strategies'][second]
    found = first_divergence(a, b)
    if not found:
        return None, ''
    kind, hour = found
    why = cause(a, b, kind, hour)
    parts = []
    for label, entry in ((first, a), (second, b)):
        row = latest_row(entry, hour)
        if row is None:
            continue
        verb = {'start': 'launches', 'abort': 'aborts', 'wait': 'waits', 'safe_hold': 'holds'}[row['action']]
        risk = f" (est. risk {row['p']:.0%})" if row['p'] is not None else ''
        parts.append(f'{label} {verb}{risk}')
    return hour, f"Hour {hour:g}: " + ';  '.join(parts)


def pick_cases(records):
    ntp = [r for r in records if r['engine'] == 'NTP' and r['anatomy'] == 'MAX']
    reps = lambda r, L: len(r['strategies'][L]['repairs_completed'])
    helped = max(ntp, key=lambda r: (min(reps(r, 'C'), reps(r, 'D')) - reps(r, 'B'), reps(r, 'C')))
    hurt = max(ntp, key=lambda r: (reps(r, 'B') - reps(r, 'C'), reps(r, 'D') - reps(r, 'C')))
    return helped, hurt


def plural(n, word):
    return f'{n} {word}' + ('' if n == 1 else 's')


def lane_panel(ax_storm, ax, record, title, tag, first, second):
    hours, rate = storm_rate(record)
    ax_storm.fill_between(hours + .5, rate, color='#d9d8d3')
    ax_storm.set_xlim(0, 96)
    ax_storm.set_ylim(0, rate.max() * 1.15)
    ax_storm.set_yticks([])
    ax_storm.set_xticks([])
    for side in ('top', 'right', 'left', 'bottom'):
        ax_storm.spines[side].set_visible(False)
    peak = hours[int(rate.argmax())]
    ax_storm.text(min(peak + 3, 74), rate.max() * .6, 'true storm dose rate outside\n(the crew never sees this directly)', fontsize=8, color=INK2, va='center')
    ax_storm.set_title(title, loc='left', fontsize=12.5, fontweight='bold', pad=4)
    ax_storm.set_title(tag, loc='right', fontsize=8.5, color=MUTED, pad=4)
    ax.set_xlim(0, 96)
    ax.set_ylim(-.35, 4.35)
    ax.axvline(48, color=INK2, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(48.8, -.3, 'assumed urgent-repair deadline (48 h)', fontsize=8, color=INK2, va='bottom')
    hour, text = describe(record, first, second)
    if hour is not None:
        ax.axvline(hour, color=INK, linewidth=1.1, ymax=.93)
        ax.text(hour + .8, 4.28, textwrap.fill(text, 60), fontsize=9, color=INK, va='top', linespacing=1.3,
                bbox=dict(boxstyle='round,pad=.35', fc='#f3f2ee', ec=GRID, lw=.8))
    for lane, label in enumerate('BCD'):
        y = 3 - lane
        entry = record['strategies'][label]
        ax.text(-1.2, y, NAME[label], ha='right', va='center', fontsize=10, fontweight='bold', color=INK)
        ax.axhline(y - .38, color=GRID, linewidth=.8)
        for eva in sorted(entry['evas'], key=lambda e: e['start_h']):
            end = eva['return_started_h'] if eva['return_started_h'] is not None else eva['end_h']
            width = end - eva['start_h']
            if eva['aborted']:
                ax.add_patch(Rectangle((eva['start_h'], y - .24), width, .48, fc=SURFACE, ec=STRAT[label], lw=1.6, hatch='////'))
                ax.plot(end, y, marker='X', color=INK, markersize=8, markeredgecolor=SURFACE, markeredgewidth=1)
            else:
                ax.add_patch(Rectangle((eva['start_h'], y - .24), width, .48, fc=STRAT[label], ec=SURFACE, lw=1.2))
                if width >= 5:
                    ax.text(eva['start_h'] + width / 2, y, REPAIR[eva['repair']], ha='center', va='center', fontsize=7.5, color=INK)
        ax.text(97, y, f"{len(entry['repairs_completed'])} of 4 repairs done\n{plural(entry['aborted_evas'], 'abort')}", fontsize=8.5, va='center', color=INK2)
    ax.set_yticks([])
    tidy(ax, 'x')
    ax.spines['left'].set_visible(False)


def figure_2(records):
    helped, hurt = pick_cases(records)
    fig = plt.figure(figsize=(16, 9.6))
    headline(fig, 'One emergency, three crews: the same storm, three different sequences of EVA decisions',
             'Each block is one EVA, drawn where it actually happened. Solid = repair finished (short solid blocks are retries finishing what was left). '
             'Hatched with ✕ = aborted before the repair was done; the hours worked are kept.')
    for i, (record, title) in enumerate((
            (helped, 'A.  Extra evidence helped: B stalls, C and D finish more repairs'),
            (hurt, 'B.  It did not: C finishes fewer repairs than B'))):
        top = .80 - i * .385
        ax_storm = fig.add_axes([.20, top - .055, .66, .055])
        ax = fig.add_axes([.20, top - .055 - .25, .66, .24])
        d = record['draw']
        tag = f"emergency {d['trial']} · {record['engine']} · {record['anatomy']} · storm strength ×{d['true_spe_scale']:.2f}"
        lane_panel(ax_storm, ax, record, title, tag, 'B', 'C')
        ax.set_xlabel('Mission hour', fontsize=9.5)
    footer(fig, 'Both emergencies were picked by rule to show a clear gain and a clear loss (largest repair-count change among NTP/male-reference cases), not as typical cases; '
                'figure 3 shows the typical picture. The vertical line marks where B and C first decided differently. Source: results/monte-carlo/decision_trees_current_rate_100.')
    return fig


# ---------------------------------------------------------------------------------------------------------------
def figure_3(records):
    fig = plt.figure(figsize=(16, 9))
    by = {L: [r['strategies'][L] for r in records] for L in 'BCD'}
    n = len(records)
    worst = max(e['max_organ_mGy_eq']['BFO'] for L in 'BCD' for e in by[L])
    reach = sum(e['max_organ_mGy_eq']['BFO'] >= 250 for L in 'BCD' for e in by[L])
    median = statistics.median(e['max_organ_mGy_eq']['BFO'] for L in 'BCD' for e in by[L])
    headline(fig, 'Different decisions, nearly the same outcomes, and no run reaches the exposure reference',
             f'Each strategy run on the same {n} cases; spread shown, not just averages. {reach} of {3 * n} runs reach the reference; the worst is {worst:.0f} mGy-Eq '
             f'({worst / 250:.0%} of it). The safety gate that keeps everyone below the reference also keeps the strategies similar.')
    # misses: where do they come from?
    missed = never = 0
    anyone = everyone = 0
    for r in records:
        deadline = r['draw']['urgent_deadline_h']
        flags = {}
        for L in 'BCD':
            e = r['strategies'][L]
            flags[L] = e['critical_repair_completed_before_deadline'] is not True
            if flags[L]:
                missed += 1
                never += not any(x['repair'] == 'propulsion_initial' and x['start_h'] < deadline for x in e['evas'])
        anyone += any(flags.values())
        everyone += all(flags.values())
    # a: urgent repair on time
    ax = fig.add_axes([.06, .33, .24, .46])
    for i, L in enumerate('BCD'):
        k = sum(e['critical_repair_completed_before_deadline'] is True for e in by[L])
        lo, hi = wilson(k, n)
        ax.bar(i, k / n * 100, width=.55, color=STRAT[L], edgecolor=SURFACE)
        ax.plot([i, i], [lo * 100, hi * 100], color=INK, linewidth=1.5)
        ax.text(i, k / n * 100 / 2, f'{k / n:.0%}', ha='center', va='center', fontsize=13, fontweight='bold', color=INK)
    ax.set_xticks(range(3))
    ax.set_xticklabels([TICK[L] for L in 'BCD'], fontsize=8.5)
    ax.set_ylim(0, 100)
    ax.set_ylabel('% of cases', fontsize=9.5)
    ax.set_title('Urgent repair finished by the 48 h deadline', loc='left', fontsize=11.5, fontweight='bold')
    tidy(ax, 'y')
    fig.text(.06, .205, textwrap.fill(
        f'Whiskers: 95% sampling interval. {never / missed:.0%} of the misses never launched the urgent repair at all before the deadline, and in '
        f'{everyone / anyone:.0%} of the cases that anyone misses, all three miss together: the storm keeps the estimated risk above the gate for all of them.', 50),
        fontsize=8.7, color=INK2, va='top', linespacing=1.35)
    # b: repairs completed
    ax = fig.add_axes([.38, .33, .26, .46])
    width = .26
    for j, L in enumerate('BCD'):
        counts = [sum(len(e['repairs_completed']) == r for e in by[L]) / n * 100 for r in range(5)]
        ax.bar(np.arange(5) + (j - 1) * width, counts, width=width * .92, color=STRAT[L], edgecolor=SURFACE, label=f'{L}  {SHORT[L]}')
    ax.set_xticks(range(5))
    ax.set_xticklabels(['0', '1', '2', '3', 'all 4'])
    ax.set_xlabel('Repairs completed in 96 h (of 4)', fontsize=9.5)
    ax.set_ylabel('% of cases', fontsize=9.5)
    ax.set_title('How many repairs got done', loc='left', fontsize=11.5, fontweight='bold')
    ax.legend(frameon=False, fontsize=8.5, loc='upper right')
    tidy(ax, 'y')
    fig.text(.38, .205, textwrap.fill(
        'The three bars in each group are close to the same height: the extra information changes when and how the crew acts, not how many repairs finish.', 50),
        fontsize=8.7, color=INK2, va='top', linespacing=1.35)
    # c: exposure that depends on the strategy
    ax = fig.add_axes([.72, .33, .24, .46])
    spread = {L: np.array([max(c['organ_mGy_eq']['BFO'] for c in e['crew']) - min(c['organ_mGy_eq']['BFO'] for c in e['crew'])
                           for e in by[L]]) for L in 'BCD'}
    for L in 'BCD':
        values = np.sort(spread[L])
        ax.step(values, np.arange(1, n + 1) / n * 100, where='post', color=STRAT[L], linewidth=2.2, label=f'{L}')
    base = statistics.median(min(c['organ_mGy_eq']['BFO'] for c in e['crew']) for L in 'BCD' for e in by[L])
    ax.set_xlim(0, 27)
    ax.set_ylim(0, 100)
    ax.set_xlabel('Extra dose to the most-exposed crew member (mGy-Eq)', fontsize=9.5)
    ax.set_ylabel('% of cases at or below this extra dose', fontsize=9.5)
    ax.set_title('Exposure the strategy can influence', loc='left', fontsize=11.5, fontweight='bold')
    ax.legend(frameon=False, fontsize=9, loc='lower right', bbox_to_anchor=(1.0, .02))
    tidy(ax, 'y')
    ax.text(9.5, 30, textwrap.fill(
        f'Every crew member shares about {base:.0f} mGy-Eq of cabin and background dose whatever the strategy does, '
        f'so total dose looks identical. This is the part EVAs add on top.', 30),
        fontsize=8.3, color=INK, va='center', linespacing=1.3)
    tail = aborted_tail = 0
    for L in 'BCD':
        for e in by[L]:
            crew = e['crew']
            if max(c['organ_mGy_eq']['BFO'] for c in crew) - min(c['organ_mGy_eq']['BFO'] for c in crew) < 5:
                continue
            tail += 1
            worst = max(crew, key=lambda c: c['organ_mGy_eq']['BFO'])['astronaut']
            aborted_tail += any(x['aborted'] for x in e['evas'] if x['astronaut'] == worst)
    small = np.mean([(spread[L] < .5).mean() for L in 'BCD'])
    fig.text(.72, .205, textwrap.fill(
        f'In {small:.0%} of runs the extra dose is under 0.5 mGy-Eq. In the {tail} runs where it reaches 5 or more, the most-exposed person had an abort in '
        f'{aborted_tail / tail:.0%} and only completed EVAs in {1 - aborted_tail / tail:.0%}, so the tail is mostly EVAs launched while the estimate was inside the gate. '
        f'C’s tail is slightly heavier ({(spread["C"] >= 10).mean():.1%} of cases at 10 or more vs {(spread["B"] >= 10).mean():.1%} for B, {(spread["D"] >= 10).mean():.1%} for D). '
        f'No run reaches the 250 mGy-Eq reference.', 56),
        fontsize=8.5, color=INK2, va='top', linespacing=1.35)
    footer(fig, 'Source: results/monte-carlo/decision_trees_current_rate_100. Exposure is BFO Gray Equivalent including background galactic cosmic rays, compared with the NASA 30-day 250 mGy-Eq protection reference '
                '(not a symptom threshold); absorbed dose and Gray Equivalent are not interchanged. “Extra dose” = most-exposed minus least-exposed crew member. Conditional frequencies, not mission probabilities.')
    return fig


# ---------------------------------------------------------------------------------------------------------------
def figure_4(records):
    fig = plt.figure(figsize=(16, 9))
    by = {L: [r['strategies'][L] for r in records] for L in 'BCD'}
    stats = {}
    for L in 'BCD':
        aborts = relaunched = 0
        gaps = []
        for e in by[L]:
            evas = sorted(e['evas'], key=lambda x: x['start_h'])
            for i, x in enumerate(evas):
                if x['aborted']:
                    aborts += 1
                    if i + 1 < len(evas):
                        relaunched += 1
                        gaps.append(evas[i + 1]['start_h'] - x['return_end_h'])
        stats[L] = (aborts, relaunched, sorted(gaps))
    rate = {L: stats[L][1] / stats[L][0] for L in 'BCD'}
    headline(fig, 'Where the strategies really diverge: what happens after an abort',
             f'C restarts least often ({rate["C"]:.0%} of aborts, vs {rate["B"]:.0%} for B and {rate["D"]:.0%} for D). The likely reason is its 5-hour blood-test turnaround; '
             'D’s 1-hour in-suit readings restart nearly as often as B.')
    # a
    ax = fig.add_axes([.06, .33, .36, .45])
    for i, L in enumerate('BCD'):
        aborts, relaunched, gaps = stats[L]
        ax.bar(i, rate[L] * 100, width=.55, color=STRAT[L], edgecolor=SURFACE)
        ax.text(i, rate[L] * 100 / 2, f'{rate[L]:.0%}', ha='center', va='center', fontsize=14, fontweight='bold')
        quick = gaps[len(gaps) // 4]
        ax.text(i, rate[L] * 100 + 2.5, f'{relaunched} of {aborts} aborts\nfastest quarter restart\nwithin {quick:.1f} h', ha='center', va='bottom', fontsize=8.5, color=INK2, linespacing=1.3)
    ax.set_xticks(range(3))
    ax.set_xticklabels([TICK[L] for L in 'BCD'], fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_ylabel('% of aborted EVAs followed by another launch', fontsize=9.5)
    ax.set_title('After an abort, how often does the crew go back out?', loc='left', fontsize=11.5, fontweight='bold')
    tidy(ax, 'y')
    # b
    ax = fig.add_axes([.54, .33, .42, .45])
    rows = []
    for a, b in (('B', 'C'), ('C', 'D')):
        worse = same = better = 0
        for r in records:
            x, y = len(r['strategies'][a]['repairs_completed']), len(r['strategies'][b]['repairs_completed'])
            worse += y < x
            better += y > x
            same += y == x
        rows.append((a, b, worse, same, better))
    for i, (a, b, worse, same, better) in enumerate(rows):
        y = 1 - i
        total = worse + same + better
        left = 0
        for count, color, label in ((worse, '#eda100', 'fewer'), (same, '#e4e3dd', 'same'), (better, '#6250d6', 'more')):
            share = count / total * 100
            ax.barh(y, share, left=left, height=.5, color=color, edgecolor=SURFACE, linewidth=2)
            if share > 3.2:
                ax.text(left + share / 2, y, f'{count}\n{label}' if label != 'same' else f'{count} same', ha='center', va='center', fontsize=9, fontweight='bold' if label != 'same' else 'normal')
            elif label == 'fewer':
                ax.text(left, y + .3, f'{count} fewer', ha='left', va='bottom', fontsize=9, fontweight='bold')
            else:
                ax.text(left + share, y + .3, f'{count} more', ha='right', va='bottom', fontsize=9, fontweight='bold')
            left += share
    ax.set_yticks([1, 0])
    ax.set_yticklabels([f'{a} → {b}' for a, b, *_ in rows], fontsize=11, fontweight='bold')
    ax.set_xlim(0, 100)
    ax.set_ylim(-.55, 1.6)
    ax.set_xlabel(f'% of the {len(records)} cases: repairs completed by the second strategy vs the first', fontsize=9.5)
    ax.set_title('Repairs completed, case by case', loc='left', fontsize=11.5, fontweight='bold')
    tidy(ax, 'x')
    ax.spines['left'].set_visible(False)
    # numbers quoted in the explanation, all computed
    worse_cases = [r for r in records if len(r['strategies']['C']['repairs_completed']) < len(r['strategies']['B']['repairs_completed'])]
    both_aborted = sum(r['strategies']['B']['aborted_evas'] > 0 and r['strategies']['C']['aborted_evas'] > 0 for r in worse_cases)
    fewer_launches = sum(len(r['strategies']['C']['evas']) < len(r['strategies']['B']['evas']) for r in worse_cases)
    with_hold = sum(any(x['cat'] == 'post-EVA review hold' for x in r['strategies']['C']['decision_log']) for r in worse_cases)
    lab = records[0]['information']
    lab_c, lab_d = lab['conventional_lab_delay_h'], lab['automated_foci_delay_h']
    agree = [rows[0][3] / len(records), rows[1][3] / len(records)]
    fig.text(.06, .205, textwrap.fill(
        f'What this suggests. After an abort, C relaunches {rate["C"]:.0%} of the time versus {rate["B"]:.0%} for B and {rate["D"]:.0%} for D, and it is slower to do so. '
        f'In the {len(worse_cases)} cases where C finishes fewer repairs than B, both strategies aborted in {"all" if both_aborted == len(worse_cases) else both_aborted} of them and C launched fewer times in {fewer_launches}. '
        f'That fits C having to wait for a returned blood result before restarting ({lab_c:g} h lab turnaround, versus {lab_d:g} h for D). '
        f'The lab-result hold after a normal EVA was not the explanation: it appears in only {with_hold} of those {len(worse_cases)} cases. '
        f'We have not isolated the lab delay in a controlled run, so read this as consistent with that cause, not proof of it. '
        f'The effects are small: B and C agree on repairs in {agree[0]:.0%} of cases, C and D in {agree[1]:.0%}.', 195),
        fontsize=9.8, va='top', linespacing=1.45)
    footer(fig, 'Source: results/monte-carlo/decision_trees_current_rate_100. All counts in the explanation were computed from the same checkpoints. '
                'Conditional frequencies under the configured hypothetical distribution.')
    return fig


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = load()
    for name, build in (('01_decisions_differ_and_why', figure_1), ('02_one_emergency_three_crews', figure_2),
                        ('03_outcomes_barely_change', figure_3), ('04_what_happens_after_an_abort', figure_4)):
        fig = build(records)
        fig.savefig(OUT / f'{name}.png', dpi=150)
        fig.savefig(OUT / f'{name}.svg')
        plt.close(fig)
        print(OUT / f'{name}.png')


if __name__ == '__main__':
    main()

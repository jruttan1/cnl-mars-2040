"""Reproducible paired Monte Carlo around the existing mission engine.

Frequencies describe the configured hypothetical emergency distribution, not mission
encounter probabilities. Every sampled emergency is reused for B–D and both engines.
"""
import argparse
import csv
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys

from radiation.anatomical_environment import DATA, MANIFEST, ORGANS
from radiation.radiation_model import ROOT, sha256
from .assumptions import DEFAULT_ASSUMPTIONS
from .anatomical_reference import FAX_SOURCES
from .models import Astronaut
from .background_radiation import metadata as gcr_metadata, SOURCE_PATH
from .informed_config import ForecastSpec, InformedConfig
from .mission_recovery import RecoveryConfig, RepairAccess
from .mission_simulator import simulate_mission
from .repair_tasks import REPAIRS
from .run_comparison import summarize_result
from .decision_metrics import compact_log, decision_metrics, decision_report
from .strategies import strategy_b, strategy_c, strategy_d


@dataclass(frozen=True)
class Experiment:
    trials: int = 100
    seed: int = 21
    template: str = 'october_2003_goes10'
    severity: str = '1000'
    mixed_storms: bool = False
    wide_forecast: bool = False
    matched_current_rate: bool = False
    true_spe_scale: tuple[float, float] = (0.35, 1.25)
    forecast_scale_error: tuple[float, float] = (0.6, 1.4)
    engines: tuple[str, ...] = ('NTP', 'NEP')
    anatomies: tuple[str, ...] = ('MAX', 'FAX')
    observation_hours: float = 96.0
    true_profile_origin_h: tuple[float, float] = (24.0, 72.0)
    forecast_origin_error_h: tuple[float, float] = (-6.0, 6.0)
    urgent_deadline_h: tuple[float, float] = (24.0, 72.0)
    eva_work_hours: tuple[float, float] = (6.0, 8.0)
    gcr_scale: float = 1.0
    # Explicit repairable reference scenario; assessed routes, not measured geometry.
    protected_nep_tasks: tuple[str, ...] = REPAIRS
    cleared_ntp_tasks: tuple[str, ...] = REPAIRS
    continued_shelter_feasible: bool = True
    warning_hold_h: float = 0.0
    urgent_repair: str = 'propulsion_initial'
    restart_quiet_hours: float | None = None
    forecast_stress_weight: float = .05
    abort_progress_credit: float = 0.0
    retry_after_abort: bool = False
    b_projection: str = 'current_rate'
    shared_current_rate: bool = False

    def __post_init__(self):
        if type(self.trials) is not int or self.trials < 1 or type(self.seed) is not int or self.seed < 0:
            raise ValueError('Trials must be positive and seed a nonnegative integer')
        if self.template not in ('august_1972', 'october_2003_goes10') or self.severity not in ('100', '1000'):
            raise ValueError('Unsupported storm template or severity')
        if not self.engines or len(set(self.engines)) != len(self.engines) or not set(self.engines) <= {'NTP', 'NEP'}:
            raise ValueError('Select distinct NTP/NEP engines')
        if not self.anatomies or len(set(self.anatomies)) != len(self.anatomies) or not set(self.anatomies) <= {'MAX', 'FAX'}:
            raise ValueError('Select distinct MAX/FAX reference anatomies')
        for field in ('true_profile_origin_h', 'forecast_origin_error_h', 'urgent_deadline_h', 'eva_work_hours', 'true_spe_scale', 'forecast_scale_error'):
            bounds = getattr(self, field)
            if len(bounds) != 2 or not all(math.isfinite(v) for v in bounds) or bounds[0] > bounds[1]:
                raise ValueError(f'{field} requires ordered finite bounds')
        if type(self.mixed_storms) is not bool or self.true_spe_scale[0] <= 0 or self.forecast_scale_error[0] <= 0:
            raise ValueError('Invalid mixed-storm parameters')
        if type(self.wide_forecast) is not bool or (self.wide_forecast and not self.mixed_storms):
            raise ValueError('Wide forecast is an experiment setting for mixed storms')
        if not math.isfinite(self.forecast_stress_weight) or not 0 <= self.forecast_stress_weight < 1:
            raise ValueError('Forecast stress weight must be in [0, 1)')
        if type(self.matched_current_rate) is not bool:
            raise ValueError('Invalid matched current-rate setting')
        if self.restart_quiet_hours is not None and (
                not (self.matched_current_rate or self.retry_after_abort) or not math.isfinite(self.restart_quiet_hours)
                or self.restart_quiet_hours <= 0):
            raise ValueError('A positive restart review duration requires matched current-rate mode or retry_after_abort')
        if type(self.retry_after_abort) is not bool or (self.retry_after_abort and self.restart_quiet_hours is None):
            raise ValueError('retry_after_abort requires restart_quiet_hours')
        if type(self.shared_current_rate) is not bool:
            raise ValueError('shared_current_rate must be true or false')
        if self.b_projection not in ('current_rate', 'ensemble'):
            raise ValueError('b_projection must be current_rate or ensemble')
        if not math.isfinite(self.abort_progress_credit) or not 0 <= self.abort_progress_credit <= 1:
            raise ValueError('Abort progress credit must be between 0 and 1')
        if self.urgent_deadline_h[0] <= 0 or self.eva_work_hours[0] <= 0:
            raise ValueError('Repair durations and deadlines must be positive')
        if not math.isfinite(self.observation_hours) or not 0 < self.observation_hours <= 720:
            raise ValueError('Observation period must be positive and at most 720 hours')
        if self.urgent_deadline_h[1] > self.observation_hours:
            raise ValueError('Observation period must cover all sampled deadlines')
        if any(not math.isfinite(v) or v < 0 for v in (self.gcr_scale, self.warning_hold_h)):
            raise ValueError('GCR scale and warning hold must be finite and nonnegative')
        for tasks in (self.protected_nep_tasks, self.cleared_ntp_tasks):
            if len(set(tasks)) != len(tasks) or not set(tasks) <= set(REPAIRS):
                raise ValueError('Access lists must contain distinct known repair tasks')
        if type(self.continued_shelter_feasible) is not bool or self.urgent_repair not in REPAIRS:
            raise ValueError('Invalid shelter or urgent-repair setting')
        # The forecast ensemble adds +/-6 h around the noisy nominal profile origin.
        earliest = self.true_profile_origin_h[0] + min(0, self.forecast_origin_error_h[0] - 6)
        latest = self.true_profile_origin_h[1] + max(0, self.forecast_origin_error_h[1] + 6)
        duration = 336 if self.template == 'october_2003_goes10' and not self.mixed_storms else 264
        if earliest < 0 or latest + self.observation_hours > duration:
            raise ValueError('Sampled truth/forecast range must cover the entire observation period')


def trial_draw(spec, trial):
    # Trial identity makes resume, loop order and engine selection irrelevant to draws.
    seed = int.from_bytes(hashlib.sha256(f'{spec.seed}:{trial}'.encode()).digest()[:8], 'big')
    rng = random.Random(seed)
    origin = rng.uniform(*spec.true_profile_origin_h)
    error = rng.uniform(*spec.forecast_origin_error_h)
    draw = dict(trial=trial, true_profile_origin_h=origin, forecast_origin_error_h=error,
                forecast_profile_origin_h=origin + error,
                urgent_deadline_h=rng.uniform(*spec.urgent_deadline_h),
                eva_work_hours=rng.uniform(*spec.eva_work_hours),
                measurement_seed=rng.randrange(2**31))
    if spec.mixed_storms:
        scale = rng.uniform(*spec.true_spe_scale)
        scale_error = rng.uniform(*spec.forecast_scale_error)
        draw.update(true_template=rng.choice(('august_1972', 'october_2003_goes10')),
                    true_spe_scale=scale, forecast_scale_error=scale_error,
                    forecast_spe_scale=scale * scale_error)
    return draw


def run_pair(spec, draw, engine, anatomy='MAX', *, labels=('B', 'C', 'D')):
    mission = replace(DEFAULT_ASSUMPTIONS, engine_type=engine, anatomy=anatomy, historical_template=draw.get('true_template', spec.template),
        spe_scale=draw.get('true_spe_scale', 1.0),
        default_spe_severity=f'SAPPHIRE-1-in-{spec.severity}', storm_start_hour=draw['true_profile_origin_h'],
        eva_duration_hours=draw['eva_work_hours'], max_hours=spec.observation_hours,
        observation_end_h=spec.observation_hours, continued_shelter_feasible=spec.continued_shelter_feasible,
        gcr_scale=spec.gcr_scale, abort_progress_credit=spec.abort_progress_credit,
        operational_restrictions=((0.0, spec.warning_hold_h),) if spec.warning_hold_h else ())
    access = tuple(RepairAccess(task, task in (spec.protected_nep_tasks if engine == 'NEP' else spec.cleared_ntp_tasks),
                              task in spec.protected_nep_tasks if engine == 'NEP' else None)
                   for task in REPAIRS)
    recovery = RecoveryConfig(urgent_repair=spec.urgent_repair, repair_access=access,
        ntp_repair_deadline_hours=draw['urgent_deadline_h'], nep_repair_deadline_hours=draw['urgent_deadline_h'])
    # No true future trajectory or true accumulated dose is passed to a strategy.
    forecast = ForecastSpec(historical_template='august_1972' if spec.mixed_storms else spec.template,
        alternative_templates=('october_2003_goes10',) if spec.mixed_storms else (),
        spe_scale=draw.get('forecast_spe_scale', 1.0), severity=f'SAPPHIRE-1-in-{spec.severity}',
        profile_origin_h=draw['forecast_profile_origin_h'], gcr_scale=spec.gcr_scale, anatomy=anatomy)
    if spec.wide_forecast:
        # Approximate the configured multiplicative forecast-error distribution.
        # The optional out-of-range tail is a robustness assumption.
        low_error, high_error = spec.forecast_scale_error
        factors = tuple(1 / (low_error + (high_error - low_error) * index / 4) for index in range(5))
        tail = spec.forecast_stress_weight
        weights = tuple((1 - tail) * w for w in (.125, .25, .25, .25, .125))
        if tail:
            factors += (3 * max(factors),)
            weights += (tail,)
        forecast = replace(forecast, magnitude_factors=factors, magnitude_weights=weights)
    information = InformedConfig(forecast=forecast, seed=draw['measurement_seed'],
                                 forecast_launch_veto=not spec.wide_forecast,
                                 share_storm_evidence=spec.wide_forecast,
                                 matched_current_rate=spec.matched_current_rate,
                                 restart_quiet_hours=spec.restart_quiet_hours,
                                 retry_after_abort=spec.retry_after_abort, b_projection=spec.b_projection,
                                 shared_current_rate=spec.shared_current_rate)
    record = dict(draw=draw, engine=engine, anatomy=anatomy, mission=asdict(mission), recovery=asdict(recovery),
                  information=asdict(information), strategies={})
    for label, policy in zip('BCD', (strategy_b, strategy_c, strategy_d)):
        if label not in labels:
            continue
        result = simulate_mission(policy, config=mission, recovery_config=recovery,
                                  astronauts=[Astronaut(f'Crew {i+1}', gender='female' if anatomy=='FAX' else 'male')
                                              for i in range(mission.crew_size)],
                                  information_config=information)
        entry = summarize_result(result, spec.urgent_repair, information.references)
        entry['aborted_evas'] = sum(eva['aborted'] for eva in entry['evas'])
        entry['projection_mode'] = ('current_rate' if spec.matched_current_rate or spec.shared_current_rate
                                    or (label == 'B' and spec.b_projection == 'current_rate')
                                    else 'future_storm_ensemble')
        entry['decision_log'] = compact_log(result.event_log)
        entry['returned_measurements'] = sum(r['event'] == 'returned' for r in result.measurement_log)
        # Readings merely being available is not the same as a decision using them. The
        # in-EVA biomarker branch (strategies.py) needs D's own policy and is disabled in
        # matched current-rate mode, where readings influence decisions only through the
        # shared storm weights. Report both so neither is mistaken for the other.
        available = sum(bool(e.get('in_eva_markers')) and e['action'] in ('continue', 'abort')
                        for e in result.event_log)
        entry['in_eva_readings_available'] = available
        entry['in_eva_biology_assessments'] = available if label == 'D' and not spec.matched_current_rate else 0
        entry['reassessment_audit'] = dict(
            decisions=[e for e in result.event_log if e['action'] in ('start', 'abort')],
            dose_waits=[e for e in result.event_log if 'dose_wait_until_h' in e],
            live_decisions=[e for e in result.event_log
                            if e.get('in_eva_markers') and e['action'] in ('continue', 'abort')],
            returned_in_eva_readings=[m for m in result.measurement_log if m['event'] == 'returned'
                                      and any(eva['astronaut'] == m['astronaut']
                                              and eva['start_h'] < m['sampled_h'] <= eva['return_started_h']
                                              for eva in entry['evas']
                                              if eva['return_started_h'] is not None)],
            returned_foci=[m for m in result.measurement_log
                           if m['event'] == 'returned' and m['marker'] == 'H2AX'])
        # Full trace for the first draw supports a concrete presentation/Q&A example.
        if draw['trial'] == 0:
            entry['trace'] = dict(decisions=result.event_log, measurements=result.measurement_log,
                                  estimates=result.estimate_history, exposures=result.exposure_history)
        record['strategies'][label] = entry
    return record


def wilson(successes, n):
    if not n:
        return None
    z = 1.959963984540054
    p = successes/n
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n))/denominator
    radius = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/denominator
    return [max(0, center-radius), min(1, center+radius)]


def mean_interval(values):
    """Approximate Monte Carlo sampling CI; not a physical/model uncertainty bound."""
    if len(values) < 2:
        return None
    mean = statistics.mean(values)
    radius = 1.96 * statistics.stdev(values)/math.sqrt(len(values))
    return [mean-radius, mean+radius]


def summarize(records):
    summaries, paired = [], []
    for engine, anatomy in sorted({(r['engine'],r['anatomy']) for r in records}):
        group = [r for r in records if r['engine'] == engine and r['anatomy'] == anatomy]
        for label in 'BCD':
            entries = [r['strategies'][label] for r in group]
            n = len(entries)
            completed = sum(e['all_repairs_completed'] for e in entries)
            critical = sum(e['critical_repair_completed_before_deadline'] is True for e in entries)
            common = [e for e in entries if e['exposure_comparison_basis'] == 'common_observation_period']
            below = sum(e['repairs_completed_below_references'] is True for e in common)
            row = dict(engine=engine, anatomy=anatomy, strategy=label, trials=n,
                all_repairs_completed_fraction=completed/n, all_repairs_completed_ci95=wilson(completed,n),
                urgent_repair_on_time_fraction=critical/n,
                mean_repairs_completed=statistics.mean(len(e['repairs_completed']) for e in entries),
                common_horizon_trials=len(common),
                repairs_below_references_fraction=below/n if len(common)==n else None,
                repairs_below_references_ci95=wilson(below,n) if len(common)==n else None,
                any_reference_exceeded_fraction=sum(e['any_organ_reference_exceeded'] for e in common)/n if len(common)==n else None,
                mean_completed_recovery_h=statistics.mean(e['elapsed_h'] for e in entries if e['all_repairs_completed']) if completed else None,
                mean_aborted_evas=statistics.mean(e['aborted_evas'] for e in entries),
                status_counts={status:sum(e['status']==status for e in entries) for status in sorted({e['status'] for e in entries})})
            for organ in ('BFO', 'Skin', 'Lens'):
                row[f'mean_max_{organ}_mGy_eq'] = statistics.mean(e['max_organ_mGy_eq'][organ] for e in common) if len(common)==n else None
                hits = [e['first_crew_reference_hit_h'][organ] for e in common
                        if e.get('first_crew_reference_hit_h', {}).get(organ) is not None]
                has_timings = len(common) == n and all('first_crew_reference_hit_h' in e for e in common)
                row[f'{organ}_reference_hit_cases'] = len(hits) if has_timings else None
                row[f'median_first_{organ}_hit_h_among_hits'] = statistics.median(hits) if len(common) == n and hits else None
            for metric in ('crew_total_bfo_absorbed_person_mGy', 'crew_mean_bfo_absorbed_mGy'):
                row[f'mean_{metric}'] = (statistics.mean(e[metric] for e in common)
                                         if len(common) == n and all(metric in e for e in common) else None)
            summaries.append(row)
        for baseline, candidate in (('B','C'), ('C','D'), ('B','D')):
            pair = [(r['strategies'][baseline],r['strategies'][candidate]) for r in group]
            complete_delta = [int(b['all_repairs_completed'])-int(a['all_repairs_completed']) for a,b in pair]
            row = dict(engine=engine, anatomy=anatomy, baseline=baseline, candidate=candidate, trials=len(pair),
                completion_fraction_difference=statistics.mean(complete_delta),
                completion_difference_ci95=mean_interval(complete_delta),
                candidate_only_completes=sum(not a['all_repairs_completed'] and b['all_repairs_completed'] for a,b in pair),
                baseline_only_completes=sum(a['all_repairs_completed'] and not b['all_repairs_completed'] for a,b in pair))
            common = all(a['exposure_comparison_basis']==b['exposure_comparison_basis']=='common_observation_period' for a,b in pair)
            metric = 'crew_mean_bfo_absorbed_mGy'
            absorbed_delta = [b[metric] - a[metric] for a, b in pair if metric in a and metric in b]
            row['crew_mean_bfo_absorbed_difference_mGy'] = (statistics.mean(absorbed_delta)
                                                           if common and len(absorbed_delta) == len(pair) else None)
            for organ in ('BFO','Skin','Lens'):
                delta = [b['max_organ_mGy_eq'][organ]-a['max_organ_mGy_eq'][organ] for a,b in pair]
                row[f'mean_max_{organ}_difference_mGy_eq'] = statistics.mean(delta) if common else None
                row[f'max_{organ}_difference_ci95'] = mean_interval(delta) if common else None
            paired.append(row)
    return dict(strategies=summaries, paired_comparisons=paired,
                interpretation='Conditional frequencies under specified independent uniform assumptions; not Mars mission probabilities. CIs reflect Monte Carlo sampling only. Paired differences are candidate minus baseline.')


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    temporary.replace(path)


def save_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in rows)


def initialize_worker():
    # Each immutable source is checksum-validated once per worker; consumers copy/filter.
    from functools import lru_cache
    import radiation.anatomical_environment as ae
    from . import mission_simulator as ms, radiation_information as ri
    cached = lru_cache(maxsize=2)(ae.load_environment)
    ae.load_environment = ms.load_environment = ri.load_environment = cached


def checkpoint_worker(spec, draw, engine, anatomy, path):
    record = run_pair(spec, draw, engine, anatomy)
    atomic_json(path, record)
    return str(path)


def run(spec, output, resume=False, workers=1):
    if type(workers) is not int or workers < 1:
        raise ValueError("Workers must be a positive integer")
    paths = sorted(set([DATA, MANIFEST, ORGANS, ROOT/SOURCE_PATH, *FAX_SOURCES] +
                       list((ROOT/'sim').glob('*.py')) + list((ROOT/'bayes_estimator').glob('*.py'))))
    identity = dict(config=asdict(spec), source_sha256={str(p.relative_to(ROOT)):sha256(p) for p in paths})
    identity = json.loads(json.dumps(identity))
    manifest = dict(**identity, background_gcr=gcr_metadata(spec.gcr_scale), python=sys.version,
        distributions='Independent uniforms over the named ranges; measurement randomness comes from the existing seeded observation model.',
        fixed_assumptions=('Mixed mode: equally sampled historical profiles, continuous fluence multiplier; both profiles in forecast, noisy strength. Fixed source spectral shape, no inferred return period. ' if spec.mixed_storms else 'Known timing-template/severity class; ') + ' noisy forecast origin; configured shape/timing/magnitude forecast ensemble; 5 crew, one outside, four tasks. EVA duration drawn once per emergency and known by all policies. No repair failure draws.',
        access_assumption='Per-task reference clearances explicitly listed in config; they are not geometry calculations.',
        prior_exposure='Emergency interval only; no previous cruise or reactor dose.',
        anatomy_assumption='Separate homogeneous MAX male and FAX female reference cohorts, matched draws. GCR remains the same male-reference proxy for both; no sex-specific biomarker multiplier.',
        restart_assumption=(f'{spec.restart_quiet_hours:g} h of improved common forecast assessments after return; '
                            'both forecast-only and evidence-adjusted cumulative risk must pass the restart gate.'
                            if spec.restart_quiet_hours is not None else 'Use the original strategy-specific abort rules.'),
        baseline=('B, C and D use a common current-rate action rule and vary biological readings.'
                  if spec.matched_current_rate else
                  'B uses estimated current rates through return. C/D retain the future storm ensemble. A is excluded.'))
    if output.exists():
        if not resume:
            raise ValueError('Output exists; choose a new folder or use --resume')
        previous = json.loads((output/'manifest.json').read_text())
        if any(previous[key] != identity[key] for key in identity):
            raise ValueError('Cannot resume: configuration or source hashes changed')
    else:
        output.mkdir(parents=True)
        atomic_json(output/'manifest.json', manifest)
    if workers > 1:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        jobs = [(trial_draw(spec, i), e, a, output/f'trial_{i:05d}_{e}_{a}.json')
                for i in range(spec.trials) for e in spec.engines for a in spec.anatomies
                if not (output/f'trial_{i:05d}_{e}_{a}.json').exists()]
        with ProcessPoolExecutor(max_workers=workers, initializer=initialize_worker) as pool:
            futures = [pool.submit(checkpoint_worker, spec, *job) for job in jobs]
            for count, future in enumerate(as_completed(futures), 1):
                future.result()
                if count % 5 == 0 or count == len(jobs):
                    print(f'{count}/{len(jobs)} new paired cases checkpointed', flush=True)
    # Detect changing code/data before accepting a complete batch.
    if any(sha256(ROOT/p) != digest for p, digest in identity['source_sha256'].items()):
        raise ValueError('Source changed during experiment; results require a fresh run')
    records=[]
    for trial in range(spec.trials):
        draw=trial_draw(spec,trial)
        for engine, anatomy in ((e,a) for e in spec.engines for a in spec.anatomies):
            path=output/f'trial_{trial:05d}_{engine}_{anatomy}.json'
            if path.exists():
                record=json.loads(path.read_text())
                if record['draw'] != draw or record['engine'] != engine or record['anatomy'] != anatomy or set(record['strategies']) != set('BCD'):
                    raise ValueError(f'Invalid checkpoint: {path}')
            else:
                record=run_pair(spec,draw,engine,anatomy)
                atomic_json(path,record)
            records.append(record)
            print(f'{len(records)}/{spec.trials*len(spec.engines)*len(spec.anatomies)} paired cases complete: {engine}/{anatomy}, trial {trial}', flush=True)
    summary=summarize(records)
    summary['decision_metrics']=decision_metrics(records)
    atomic_json(output/'summary.json',summary)
    (output/'DECISIONS.md').write_text(decision_report(summary['decision_metrics']))
    save_csv(output/'strategy_summary.csv',summary['strategies'])
    save_csv(output/'paired_differences.csv',summary['paired_comparisons'])
    save_csv(output/'draws.csv',[dict(engine=r['engine'],anatomy=r['anatomy'],**r['draw']) for r in records])
    save_csv(output/'trial_results.csv',[
        dict(engine=r['engine'], anatomy=r['anatomy'], strategy=label, **r['draw'],
             status=e['status'], repairs_completed=len(e['repairs_completed']),
             all_repairs_completed=e['all_repairs_completed'],
             urgent_repair_on_time=e['critical_repair_completed_before_deadline'],
             repairs_below_references=e['repairs_completed_below_references'],
             outcome_h=e['elapsed_h'], exposure_end_h=e['exposure_observation_end_h'],
             exposure_basis=e['exposure_comparison_basis'], aborted_evas=e['aborted_evas'],
             crew_total_bfo_absorbed_person_mGy=e.get('crew_total_bfo_absorbed_person_mGy'),
             crew_mean_bfo_absorbed_mGy=e.get('crew_mean_bfo_absorbed_mGy'),
             in_eva_biology_assessments=e.get('in_eva_biology_assessments'),
             **{f'first_crew_{organ}_hit_h': e.get('first_crew_reference_hit_h', {}).get(organ)
                for organ in ('BFO', 'Skin', 'Lens')},
             **{f'max_{organ}_mGy_eq':dose for organ,dose in e['max_organ_mGy_eq'].items()})
        for r in records for label,e in r['strategies'].items()])
    (output/'README.md').write_text('''# Paired Monte Carlo results

Read `strategy_summary.csv` for results by engine and reference anatomy and `paired_differences.csv` for matched
strategy differences. `draws.csv` contains sampled inputs; `trial_results.csv` has one row per
strategy per emergency. `manifest.json` records ranges,
fixed assumptions, source hashes, background rates and limitations. Each checkpoint preserves
all three strategy summaries, individual crew doses and EVA attempts. Trial zero additionally
includes full decision, dose and measurement traces. `--resume` accepts identical code/config only.

These are conditional experiment frequencies, not mission encounter or crew-survival probabilities.
See manifest for fixed versus mixed storm mode. Mixed strengths are synthetic fluence multipliers, not sampled return periods.
All strategies share each emergency, observation horizon and measurement seed. Engines and anatomies reuse
matched draws but are summarized separately. No combined cohort success score is produced.
Percentages need enough trials to stabilize; a small pilot only verifies execution.

Wilson intervals describe sampling error for proportions. Paired difference intervals use an
approximate normal Monte Carlo standard error and are omitted for a single trial. These intervals
do not include uncertainty in physics, biomarker calibration or the chosen distributions.
Exposure rankings are suppressed unless every case in the group has a common observation period.
Continuation of cabin exposure after recovery termination depends on the explicit continued-shelter
assumption, not proof of spacecraft survival. Completion times are conditional on completed repairs.
''')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'configs/monte_carlo_2003_1000.json')
    parser.add_argument('--trials',type=int,help='Override independent draws per engine/anatomy cohort')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'results/monte-carlo/2003_1000')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--workers',type=int,default=1)
    args=parser.parse_args()
    try:
        values=json.loads(args.config.read_text())
        if args.trials is not None: values['trials']=args.trials
        spec=Experiment(**values)
        run(spec,args.output_dir.resolve(),args.resume,args.workers)
    except (ValueError,TypeError) as exc:
        parser.error(str(exc))


if __name__=='__main__':
    main()

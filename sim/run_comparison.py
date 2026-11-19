"""Run B–D against identical physics, with a separately configured nominal forecast."""
import argparse
from dataclasses import asdict, replace
import json
import math
from pathlib import Path

import pandas as pd

from radiation.anatomical_environment import DATA, MANIFEST, ORGANS
from radiation.radiation_model import ROOT, sha256, write_preserving
from .assumptions import DEFAULT_ASSUMPTIONS
from .informed_config import ForecastSpec, InformedConfig
from .mission_recovery import RecoveryConfig, RepairAccess
from .background_radiation import metadata as gcr_metadata, SOURCE_PATH as GCR_SOURCE
from .anatomical_reference import dose_vector, FAX_SOURCES
from .repair_tasks import task_descriptions, REPAIRS
from bayes_estimator.longitudinal import MARKERS
from .mission_simulator import simulate_mission
from .strategies import strategy_b, strategy_c, strategy_d


ORGANS_REPORTED = ('BFO', 'Skin', 'Lens')


def organ_outcomes(result, through_hour=None, references=None):
    severity = int(result.scenario.severity.rsplit('-', 1)[1])
    totals = {}
    for depth in (result.scenario.shielding, result.scenario.cabin_shielding):
        totals[depth] = dict(zip(ORGANS_REPORTED, dose_vector(result.scenario.anatomy, severity, depth)[1:]))
    thresholds = dict(zip(ORGANS_REPORTED, references)) if references is not None else {}
    rows = []
    for astronaut in result.astronauts:
        history = [record for record in result.exposure_history if record['astronaut'] == astronaut.name
                   and (through_hour is None or record['end_hour'] <= through_hour)]
        spe_doses = dict.fromkeys(ORGANS_REPORTED, 0.0)
        gcr_doses = dict.fromkeys(ORGANS_REPORTED, 0.0)
        first_hits = dict.fromkeys(thresholds)
        for record in history:
            depth_totals = totals[record['shielding_g_cm2']]
            spe_bfo = record.get('spe_bfo_gray_equivalent_mGy_eq', record['bfo_gray_equivalent_mGy_eq'])
            for organ in ORGANS_REPORTED:
                before = spe_doses[organ] + gcr_doses[organ]
                spe_doses[organ] += spe_bfo * (depth_totals[organ] / depth_totals['BFO'])
                gcr_doses[organ] += record.get(f'gcr_{organ.lower()}_gray_equivalent_mGy_eq', 0)
                after = spe_doses[organ] + gcr_doses[organ]
                if organ in thresholds and first_hits[organ] is None and after >= thresholds[organ]:
                    # Approximate within the recorded interval. Its shielding is fixed
                    # but its hourly SPE rate can change inside the interval.
                    start, end = record['start_hour'], record['end_hour']
                    fraction = (thresholds[organ] - before) / (after - before)
                    first_hits[organ] = start + (end - start) * fraction
        doses = {organ: spe_doses[organ] + gcr_doses[organ] for organ in spe_doses}
        rows.append(dict(astronaut=astronaut.name, bfo_absorbed_mGy=sum(record['bfo_absorbed_dose_mGy'] for record in history),
                         organ_mGy_eq=doses, spe_organ_mGy_eq=spe_doses, gcr_organ_mGy_eq=gcr_doses,
                         first_reference_hit_h=first_hits,
                         gcr_bfo_absorbed_mGy=sum(record.get('gcr_bfo_absorbed_dose_mGy', 0) for record in history),
                         eva_hours=sum(record['end_hour'] - record['start_hour']
                         for record in history if record['location'] != 'cabin')))
    return rows


def summarize_result(result, critical_repair, references):
    entry = dict(status=result.status, elapsed_h=result.outcome_hour,
                 exposure_observation_end_h=result.exposure_observation_end_h,
                 exposure_comparison_basis=result.exposure_comparison_basis,
                 information_config=result.information_config,
                 crew_at_recovery_decision=organ_outcomes(result, result.outcome_hour, references),
                 repairs_completed=result.completed_repairs, crew=organ_outcomes(result, references=references),
                 evas=[dict(astronaut=eva.astronaut.name, repair=eva.repair_type,
                            start_h=eva.start_time, end_h=eva.reported_end_time,
                            completed=eva.completed, aborted=eva.aborted,
                            return_started_h=eva.return_started_h, return_end_h=eva.return_end_h,
                            work_planned_h=eva.work_hours, work_credited_h=eva.credited_work_h)
                       for eva in result.progress + ([result.active_eva] if result.active_eva else [])])
    entry['all_repairs_completed'] = set(result.required_repairs) <= set(result.completed_repairs)
    entry['critical_repair'] = critical_repair
    entry['critical_repair_completed'] = critical_repair in result.completed_repairs
    completion_times = [event['hour'] for event in result.event_log
                        if event['action'] == 'completed' and event.get('repair') == critical_repair]
    entry['critical_repair_completed_h'] = min(completion_times) if completion_times else None
    deadline = (getattr(result.recovery_config, f'{result.scenario.engine_type.lower()}_repair_deadline_hours')
                if result.recovery_config else None)
    entry['critical_repair_completed_before_deadline'] = (
        bool(completion_times and min(completion_times) <= deadline) if deadline is not None else None)
    entry['propulsion_recovery_completed'] = 'propulsion' in result.completed_repairs
    entry['max_organ_mGy_eq'] = {organ: max(c['organ_mGy_eq'][organ] for c in entry['crew'])
                                for organ in ORGANS_REPORTED}
    entry['crew_total_bfo_absorbed_person_mGy'] = sum(c['bfo_absorbed_mGy'] for c in entry['crew'])
    entry['crew_mean_bfo_absorbed_mGy'] = entry['crew_total_bfo_absorbed_person_mGy'] / len(entry['crew'])
    entry['first_crew_reference_hit_h'] = {
        organ: min((c['first_reference_hit_h'][organ] for c in entry['crew']
                    if c['first_reference_hit_h'][organ] is not None), default=None)
        for organ in ORGANS_REPORTED
    }
    entry['any_organ_reference_exceeded'] = any(
        entry['max_organ_mGy_eq'][organ] >= reference
        for organ, reference in zip(ORGANS_REPORTED, references))
    # Assess every policy by the same outcome criteria, including A.
    entry['repairs_below_references_at_reported_end'] = (
        entry['all_repairs_completed'] and not entry['any_organ_reference_exceeded'])
    entry['repairs_completed_below_references'] = (entry['repairs_below_references_at_reported_end']
        if entry['exposure_comparison_basis'] == 'common_observation_period' else None)
    entry['reference_exceedances'] = {
        organ: sum(bool(crew['organ_mGy_eq'][organ] >= reference) for crew in entry['crew'])
        for organ, reference in zip(ORGANS_REPORTED, references)}
    return entry


def positive_hours(value):
    hours = float(value)
    if not math.isfinite(hours) or hours <= 0:
        raise argparse.ArgumentTypeError('Hours must be finite and positive')
    return hours


def task_access_argument(value):
    repair, separator, assessment = value.partition('=')
    if not separator or repair not in REPAIRS or assessment not in ('protected', 'alternative', 'cleared', 'blocked', 'unknown'):
        raise argparse.ArgumentTypeError('Use TASK=protected|alternative|cleared|blocked|unknown with a known repair task')
    return RepairAccess(repair, assessment in ('protected', 'alternative', 'cleared'),
                        True if assessment == 'protected' else False if assessment == 'blocked' else None,
                        assessment == 'alternative')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', choices=('NTP', 'NEP'), default='NTP')
    parser.add_argument('--template', choices=('august_1972', 'october_2003_goes10'), default='august_1972')
    parser.add_argument('--severity', choices=('100', '1000'), default='100')
    parser.add_argument('--forecast-severity', choices=('100', '1000'), default='100')
    parser.add_argument('--forecast-template', choices=('august_1972', 'october_2003_goes10'))
    parser.add_argument('--forecast-origin', type=float, default=48.0)
    parser.add_argument('--seed', type=int, default=21)
    parser.add_argument('--anatomy', choices=('MAX','FAX'), default='MAX')
    parser.add_argument('--gcr-scale', type=float, default=1.0,
                        help='Shared constant GCR reference multiplier; 0 disables, 1 uses published baseline with EVA proxy')
    parser.add_argument('--nep-protected-access', action='store_true',
                        help='Explicit scenario assumption: NEP EVA route and worksite are protected')
    parser.add_argument('--output-dir', type=Path, default=Path('results/strategy_comparison'))
    parser.add_argument('--repair-deadline', type=positive_hours,
                        help='Assumed propulsion repair deadline; not a published engineering limit')
    parser.add_argument('--warning-hold', type=positive_hours,
                        help='Shared procedural no-EVA interval after warning, in hours; experimental assumption')
    parser.add_argument('--nep-access', choices=('unknown', 'protected', 'alternative'), default='unknown',
                        help='Explicit scenario assumption about route AND worksite access')
    parser.add_argument('--task-access', type=task_access_argument, action='append', default=[],
                        help='Task-specific reactor assessment: TASK=protected|alternative|cleared|blocked|unknown. Overrides all-task access flags for that task; repeat for each task.')
    parser.add_argument('--urgent-repair', choices=REPAIRS, default='propulsion_initial')
    parser.add_argument('--monitoring-required', action='store_true', help='Scenario propulsion work needs restored monitoring')
    parser.add_argument('--ground-unavailable', action='store_true')
    parser.add_argument('--preapproved-repair', choices=REPAIRS, action='append', default=[])
    parser.add_argument('--observation-hours', type=positive_hours)
    parser.add_argument('--continued-shelter-feasible', action='store_true')
    parser.add_argument('--return-hours', type=positive_hours, default=DEFAULT_ASSUMPTIONS.return_to_airlock_h)
    parser.add_argument('--d-processing-delay', type=float, default=0.0)
    parser.add_argument('--d-availability', type=float, default=1.0)
    parser.add_argument('--d-unavailable-marker', choices=tuple(MARKERS), action='append', default=[])
    parser.add_argument('--d-sampling-burden', type=float, default=0.0)
    args = parser.parse_args()
    if len({entry.repair for entry in args.task_access}) != len(args.task_access):
        parser.error('--task-access must not repeat a task')
    args.output_dir = args.output_dir.resolve()
    recovery = RecoveryConfig(
        repair_access=tuple(args.task_access),
        urgent_repair=args.urgent_repair,
        monitoring_before_propulsion=args.monitoring_required,
        ground_contact_available=not args.ground_unavailable,
        preapproved_repairs=tuple(args.preapproved_repair),
        ntp_repair_deadline_hours=args.repair_deadline,
        nep_repair_deadline_hours=args.repair_deadline,
        nep_route_and_worksite_protected=True if args.nep_access == 'protected' or args.nep_protected_access else None,
        nep_alternative_eva_access_approved=args.nep_access == 'alternative')
    mission = replace(DEFAULT_ASSUMPTIONS, engine_type=args.engine, historical_template=args.template,
                      gcr_scale=args.gcr_scale,
                      anatomy=args.anatomy,
                      default_spe_severity=f'SAPPHIRE-1-in-{args.severity}',
                      observation_end_h=args.observation_hours,
                      continued_shelter_feasible=args.continued_shelter_feasible,
                      return_to_airlock_h=args.return_hours,
                      operational_restrictions=((0.0, args.warning_hold),) if args.warning_hold else ())
    forecast = ForecastSpec(historical_template=args.forecast_template or args.template,
                            severity=f'SAPPHIRE-1-in-{args.forecast_severity}', profile_origin_h=args.forecast_origin,
                            gcr_scale=args.gcr_scale, anatomy=args.anatomy)
    information = InformedConfig(forecast=forecast, seed=args.seed)
    base_delays = {marker: (information.lymphocyte_processing_delay_h if marker == 'lymphocytes' else
                            information.automated_foci_delay_h if marker in ('H2AX', '53BP1') else 0.0)
                   for marker in MARKERS}
    if not math.isfinite(args.d_processing_delay) or args.d_processing_delay < 0:
        parser.error('Additional D processing delay must be finite and nonnegative')
    advanced = replace(information, instrument_delays_h=tuple((marker, delay + args.d_processing_delay)
                                                             for marker, delay in base_delays.items()),
                       measurement_availability=args.d_availability, unavailable_markers=tuple(args.d_unavailable_marker),
                       sampling_burden_h=args.d_sampling_burden)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = dict(description='Exploratory paired strategy comparison; no clinical or instrument validation',
                   background_gcr=gcr_metadata(args.gcr_scale),
                   mission=asdict(mission), recovery=asdict(recovery),
                   information=asdict(information), repair_tasks=task_descriptions(args.engine),
                   workload_assumption='Four sequential seven-hour work tasks plus explicit return travel; scenario-specific urgent repair and prerequisites',
                   initial_conditions='After damage assessment and protective actions; unknown confirmations block authorization', strategies={})
    summary['source_sha256'] = {str(path.relative_to(ROOT)): sha256(path) for path in
                               (DATA, MANIFEST, ORGANS, ROOT / GCR_SOURCE, ROOT / 'sim/background_radiation.py', ROOT / 'sim/informed_config.py',
                                ROOT / 'sim/radiation_information.py', ROOT / 'sim/strategies.py',
                                ROOT / 'sim/mission_simulator.py', ROOT / 'sim/mission_recovery.py',
                                ROOT / 'sim/models.py', ROOT / 'sim/defaults.py', ROOT / 'sim/repair_tasks.py',
                                ROOT / 'bayes_estimator/longitudinal.py', ROOT / 'sim/anatomical_reference.py', *FAX_SOURCES)}
    for label, policy in zip('BCD', (strategy_b, strategy_c, strategy_d)):
        result = simulate_mission(policy, config=mission, recovery_config=recovery,
                                  information_config=advanced if label == 'D' else information)
        entry = summarize_result(result, args.urgent_repair, information.references)
        summary['strategies'][label] = entry
        for name, records in (('decisions', result.event_log), ('exposures', result.exposure_history),
                              ('measurements', result.measurement_log), ('estimates', result.estimate_history)):
            write_preserving(args.output_dir / f'{label}_{name}.json', json.dumps(records, indent=2) + '\n')
        print(f'{label}: {result.status}; {len(result.completed_repairs)} repairs; {result.current_mission_time:g} h; '
              f'{sum(reading["event"] == "returned" for reading in result.measurement_log)} returned readings')
    summary['exposure_ranking_permitted'] = all(entry['exposure_comparison_basis'] == 'common_observation_period'
                                               for entry in summary['strategies'].values())
    summary['exposure_interpretation'] = ('Common stated observation period' if summary['exposure_ranking_permitted'] else
                                          'Exposure only through each reported end; early stopping is not an exposure benefit')
    write_preserving(args.output_dir / 'summary.json', json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()

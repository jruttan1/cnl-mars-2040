# Operational decisions and comparable exposure

The experiment begins **after initial damage assessment and protective actions**. Configuration
records available confirmations; zero-time `stabilize` acknowledges them, rather than simulating
instant reactor shutdown or cooling. Unknown shutdown, cooling, shielding or task access blocks EVA.
These changes implement decision rules, not reactor transients or dose-based illness diagnosis.

## Urgency and prerequisites

The comparison runner names an urgent task (default `propulsion_initial`, override with
`--urgent-repair`). NTP/NEP task descriptions remain different. The urgent task and its transitive
prerequisites precede otherwise ready work. Monitoring is required only with `--monitoring-required`
or an explicit `RecoveryConfig.repair_prerequisites` edge. The second propulsion task depends on
the first by default; cycles are rejected. Omitted prerequisite tasks mean already-functional systems,
not a way to skip damaged systems. Legacy API calls may leave urgency unset, with no asserted urgency.

Optional deadlines apply to completed urgent **work**, not its final return. Planning includes
inter-task travel/turnaround. No universal deadline or physical deterioration rate is inferred.

## Holds and authorization

- `wait`, `safe_hold`, `shelter`: time advances, cabin exposure accumulates, results arrive, and
  observations are reevaluated. They do not declare the spacecraft unrecoverable.
- `no_recovery_plan`: a terminal recovery decision, e.g. an explicit urgent deadline is infeasible.
- `abort_mission`: abandon the objective; an astronaut outside still returns.
- `resume_mission`: separate readiness/authorization after repairs and crew return.

Use `simulate_mission(..., recovery_schedule=((hour, updated_config), ...))` for explicit future
assessment changes. They are logged and applied at that hour; policies only see current assessments,
not the schedule. Unknown conditions do not become confirmed merely because time passes.

Each astronaut must be explicitly `medically_fit_for_eva` and `rested_for_eva`, in addition to consent,
qualifications, availability and `rest_until_h`. Unknown fitness blocks authorization. Minimum rest
after arrival defaults to one hour as a configurable scenario assumption. Radiation does not diagnose
illness or alter these assessments automatically.

Without confirmed ground contact, only `preapproved_repairs` can be authorized locally. This is
preapproved emergency authority, not unlimited autonomy. Antenna repair does not automatically prove
contact restoration. Mission continuation separately requires readiness and approval, with confirmed
ground contact required by default.

```python
RecoveryConfig(urgent_repair='propulsion_initial', ground_contact_available=False,
               preapproved_repairs=('propulsion_initial',),
               repair_prerequisites=(('propulsion', ('propulsion_initial',)),))
```

## Return and instrument burden

`return_to_airlock_h` defaults to **0.5 h as an illustrative assumption**, not a flight-procedure value.
It is added to the existing seven-hour repair-work duration: normal exposure is 7.5 h before turnaround
at zero sampling burden. Override with `--return-hours`. Earlier presentation charts integrate exactly
seven hours and are not automatically updated to this work-plus-return convention.

Abort stops work and starts return; EVA shielding and exposure continue until actual airlock arrival.
Normal completed work also has a return phase. Rest/turnaround start at arrival, not at the command.
A time cap reserves return time. Completed work is retained despite a new assessment at completion;
incomplete work earns no credit. If observation ends before arrival, the active EVA and unset actual
arrival time identify censoring; the astronaut is not teleported to the cabin.

D stress controls retain biological kernels and C/D's common estimator/decision policy:

| Setting | Effect |
| --- | --- |
| `--d-processing-delay HOURS` | Adds latency to current marker-specific processing defaults |
| `--d-availability FRACTION` | Seeded probability an attempted reading is available |
| `--d-unavailable-marker NAME` | Explicit marker outage; repeat for multiple outages |
| `--d-sampling-burden HOURS` | Occupied time per panel; delays cabin availability or repair completion |

The four-gene panel incurs one collection burden. A failed attempted reading still costs collection
time; a known wholly unavailable panel is not collected. Results wait for collection burden plus
processing. Preflight samples are not repeatedly charged while waiting for the same result. Sampling
does not delay emergency return; in-suit panels are suspended during return. Planning reserves the
configured workload using a conservative discrete panel count and burden/cadence; actual pauses are logged. Biological response
times remain independent of hardware delay and the time the result reaches the estimator.

## Exposure comparison

`outcome_hour` records the end of the recovery decision; `exposure_observation_end_h` records the
exposure ledger endpoint. Outputs include exposure through both endpoints.

Use **both** `--observation-hours N` and `--continued-shelter-feasible` for comparable totals. After
recovery ends, any modeled return is completed, then the crew shelters to that common endpoint.
Cabin dose and pending tests continue, without new repairs. Shelter feasibility is an explicit
conditional assumption, not established by the engineering model. Periods beyond radiation-data
coverage are rejected rather than given an artificial zero-dose tail.

Otherwise `exposure_ranking_permitted` is false and `repairs_completed_below_references` is null.
The separately labelled at-reported-end result remains available. Low exposure caused by early
termination is not a benefit. A common observation endpoint does not itself establish survival,
clinical safety, or a feasible return trajectory.

## Reproduction

```bash
.venv/bin/python -B -m unittest sim.tests.test_operational_realism -v
.venv/bin/python -B -m sim.run_comparison --urgent-repair propulsion_initial \
  --observation-hours 96 --continued-shelter-feasible --output-dir results/operational_reference
.venv/bin/python -B -m sim.run_comparison --urgent-repair propulsion_initial \
  --observation-hours 96 --continued-shelter-feasible --d-processing-delay 2 \
  --d-availability 0.5 --d-sampling-burden 0.1 --output-dir results/operational_d_degraded
```

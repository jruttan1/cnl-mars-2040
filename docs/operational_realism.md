# Operational decisions and comparable exposure

The experiment starts after the first damage assessment and protective actions. The configuration records which
confirmations are available, and the zero-time `stabilize` action acknowledges them. It does not simulate an
instant reactor shutdown or cooling. Unknown shutdown, cooling, shielding or task access blocks EVA. These rules
are decision logic. They are not reactor transients or a dose-based diagnosis of illness.

## Urgency and prerequisites

The comparison runner names an urgent task (default `propulsion_initial`, override with `--urgent-repair`). NTP
and NEP keep different task descriptions. The urgent task and its prerequisites go ahead of other ready work.
Monitoring is a prerequisite only with `--monitoring-required` or an explicit `RecoveryConfig.repair_prerequisites`
edge. The second propulsion task depends on the first by default, and cycles are rejected. A task left out of the
prerequisites means an already working system, so it cannot be used to skip a damaged one. Legacy API calls can
leave urgency unset.

Optional deadlines apply to completed urgent work, not to the final return. Planning includes travel between
tasks and turnaround. No universal deadline or deterioration rate is assumed.

## Holds and authorization

- `wait`, `safe_hold`, `shelter`: time advances, cabin exposure builds up, results arrive and observations are
  re-evaluated. None of these declares the spacecraft unrecoverable.
- `no_recovery_plan`: a terminal recovery decision, for example when an explicit urgent deadline cannot be met.
- `abort_mission`: abandon the objective. An astronaut who is outside still returns.
- `resume_mission`: a separate readiness and authorization step after repairs and crew return.

`simulate_mission(..., recovery_schedule=((hour, updated_config), ...))` applies explicit future changes to the
assessments. They are logged and applied at that hour, and policies see only the current assessment, never the
schedule. Unknown conditions do not become confirmed just because time passes.

Each astronaut must be explicitly `medically_fit_for_eva` and `rested_for_eva`, on top of consent, qualification,
availability and `rest_until_h`. Unknown fitness blocks authorization. Minimum rest after arrival defaults to one
hour, a configurable assumption. Radiation does not change these assessments automatically.

Without confirmed ground contact, only `preapproved_repairs` can be authorized locally. That is preapproved
emergency authority, not unlimited autonomy. An antenna repair does not prove contact is restored. Mission
continuation separately needs readiness and approval, with confirmed ground contact required by default.

```python
RecoveryConfig(urgent_repair='propulsion_initial', ground_contact_available=False,
               preapproved_repairs=('propulsion_initial',),
               repair_prerequisites=(('propulsion', ('propulsion_initial',)),))
```

## Return and instrument burden

`return_to_airlock_h` defaults to 0.5 h as an illustrative assumption, not a flight-procedure value. It is added
to the seven-hour repair work, so normal exposure is 7.5 h before turnaround at zero sampling burden. Override it
with `--return-hours`. Earlier presentation charts integrate exactly seven hours and do not use this convention.

An abort stops work and starts the return, and EVA shielding and exposure continue until the airlock is reached.
A completed repair also has a return phase. Rest and turnaround start at arrival, not at the command. A time cap
reserves return time. Completed work is kept even if a new assessment arrives at completion, and incomplete work
earns no credit unless `abort_progress_credit` says otherwise (see `informed_strategies.md`). If observation ends
before arrival, the active EVA and the unset arrival time mark the run as censored, and the astronaut is not
moved into the cabin.

These D stress controls keep the biological kernels and the shared C and D estimator and policy:

| Setting | Effect |
| --- | --- |
| `--d-processing-delay HOURS` | Adds latency to each marker's default processing time |
| `--d-availability FRACTION` | Seeded probability that an attempted reading is available |
| `--d-unavailable-marker NAME` | Marks a marker as down; repeat for several |
| `--d-sampling-burden HOURS` | Time a panel occupies; delays cabin availability or repair completion |

The four-gene panel costs one collection burden. A failed attempt still costs collection time, and a panel known
to be wholly unavailable is not collected. A result waits for collection burden plus processing. Preflight samples
are not charged again while waiting for the same result. Sampling never delays an emergency return, and in-suit
panels pause during the return. Planning reserves the workload with a conservative count of discrete panels, and
actual pauses are logged. Biological response times do not depend on hardware delay or on when the result reaches
the estimator.

## Exposure comparison

`outcome_hour` is the end of the recovery decision, and `exposure_observation_end_h` is the end of the exposure
ledger. The outputs report exposure through both.

For comparable totals, pass both `--observation-hours N` and `--continued-shelter-feasible`. After recovery ends,
any modeled return finishes and the crew then shelters to the common endpoint. Cabin dose and pending tests
continue, with no new repairs. Shelter feasibility is an explicit assumption that the engineering model does not
establish. A period beyond the radiation-data coverage is rejected and not given an artificial zero-dose tail.

Without both options, `exposure_ranking_permitted` is false and `repairs_completed_below_references` is null. The
at-reported-end result stays available under its own label. Low exposure from early termination is not a benefit.
A common endpoint does not establish survival, clinical safety or a feasible return trajectory.

## Reproduction

```bash
.venv/bin/python -B -m sim.run_comparison --urgent-repair propulsion_initial \
  --observation-hours 96 --continued-shelter-feasible --output-dir results/operational_reference
.venv/bin/python -B -m sim.run_comparison --urgent-repair propulsion_initial \
  --observation-hours 96 --continued-shelter-feasible --d-processing-delay 2 \
  --d-availability 0.5 --d-sampling-burden 0.1 --output-dir results/operational_d_degraded
```

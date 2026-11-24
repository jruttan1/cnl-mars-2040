# Shared mission-recovery rules

Turn these on with `--recovery`, or pass `RecoveryConfig()` to `simulate_mission`. There is one simulator, and it
owns the clock, EVA progress, exposure and outcomes. `sim/mission_recovery.py` only checks rules, and its
configuration is fixed for a run.

| Decision | NTP reference scenario | NEP reference scenario |
| --- | --- | --- |
| Stabilize before EVA | Confirm coast shutdown and temporary cooling | Remote shutdown and damaged-loop isolation; needs remote control |
| Propulsion repair means | External leak isolation, feed and control restoration | External power, cooling and thruster restoration |
| Repair priority | The urgent task and its prerequisites | The urgent task and its prerequisites |
| Worksite clearance | Required for propulsion work | Required for all EVAs in the assumed shielded work area |
| Hard repair deadline | Off by default | Off by default |
| Continue mission only if | Restart and propellant margin confirmed | Sustained power and cooling confirmed |

The windows, access rules, damage details and readiness confirmations are hypothetical scenario assumptions.
They are not measured conditions or limits that hold for the whole technology. Repair priorities differ by engine
without claiming a universal deadline. The optional `*_repair_deadline_hours` values exist for sensitivity runs
and default to `None`. Each repair is a seven-hour EVA by default, and no extra task types or detailed reactor
physics are added.

## Evidence and assumptions

- **CNL facts:** NTP and NEP missions, meteoroid damage to propulsion, monitoring and communications, several
  EVAs of about seven hours, an approaching SPE and unreliable monitoring.
- **Published principles:** the National Academies' *Space Nuclear Propulsion for Human Mars Exploration*,
  chapters 3 and 4 (archived as `national_academies_ntp.html` and `national_academies_nep.html`), separates NTP
  propellant systems from NEP power conversion and heat rejection. CNSC guidance supports continued decay-heat
  removal after shutdown but gives no cooldown duration. Sources and hashes are in
  `data/raw/mission_recovery/provenance.json`.
- **Our assumptions:** every numerical window and boolean gate here. The slide's 10 MWt, 6 Sv/h and 24-hour
  examples are not used as established values, and reactor dose is not calculated.

## Exact behavior

Stabilization is a zero-duration confirmation in the mission loop, not a thermal transient. Shutdown, cooling and
shielding must already be confirmed, or stabilization cannot happen. It cannot be repeated or done during an EVA.
Every EVA needs stabilization, consent, qualification and the usual operational permissions. A monitoring repair
restores engineering checks, not perfect radiation knowledge.

Windows run from mission hour 0 and never reset. A propulsion repair finished exactly at its deadline keeps its
credit. A new exposure or operational concern at that instant is logged for reassessment and does not undo
finished work. An earlier abort still prevents completion. If the deadline passes without the repair, the run ends
as `no_feasible_recovery_plan`, with any active astronaut still accruing exposure on the way back. That means an
assumed recovery option was lost. It does not mean crew death or a reactor accident. A temporary hold advances
time and processes observations, and no longer ends the run. Continued shelter after a terminal decision needs an
explicit feasibility assumption.

Continuation needs completed repairs, the crew inside, engine readiness and authorization. The reactor and
readiness confirmations default to true for a repairable reference scenario, which is an assumption. The NEP
route-protection confirmation defaults to unknown, and approval of an alternative access plan defaults to false.
A repair left out of the config is assumed already working, and its deadline does not apply. NEP's default
priority is advice to strategies, while launch prerequisites and deadlines are enforced by the simulator for every
strategy. Ground-contact authorization and preapproved local repair authority are separate from a
communications-repair prerequisite.

Strategy A checks a lower bound before launching: the remaining propulsion prerequisites plus propulsion itself,
using the configured EVA duration, turnaround and next launch time. If even that cannot fit before the assumed
deadline, A reports no feasible recovery plan instead of launching a futile attempt. If another repair would use
up the remaining time, A prioritizes the critical chain. Finishing exactly at the deadline is allowed, and no
check applies once propulsion is repaired or its deadline is off. This is a necessary-time check and not a
schedule guarantee, since later restrictions and crew availability can still delay work. A checks again at each
decision and uses neither actual dose nor future storm intensity.

## NEP reactor access

Reactor access is separate from SPE shielding. Before any NEP EVA, check the worksite and the whole outbound and
return route:

```text
Within the reactor shadow shield's protected region?
  Yes -> reactor worksite conditions cleared? -> existing SPE/operational checks
  No / unknown -> approved alternative EVA access? -> same clearance and SPE checks
                  No -> do not launch; revise access plan or consider remote repair
```

Each of the four tasks has its own `RepairAccess` assessment in `RecoveryConfig.repair_access`:
`communications`, `monitoring`, `propulsion_initial` and `propulsion`. An assessment records worksite clearance,
protection of the worksite and the whole route, and approval of an alternative access procedure. NTP uses
per-task worksite clearance. NEP also needs protected access or the approved alternative. Clearance never
bypasses shutdown, cooling, shielding integrity, stabilization, prerequisites or crew permissions. The launch
check enforces the assessment for every strategy.

The older global switches remain as all-task assumptions for existing scenarios. A task entry replaces them
completely for that task, so an unknown or blocked entry cannot inherit a blanket approval. With no task entry,
NEP protection stays unknown, and the legacy NTP reference scenario keeps its assumed worksite clearance. A task's
physical location is never inferred from its name, and protected communications does not mean protected radiators.

The comparison runner takes repeated `--task-access TASK=STATUS` options:

- `protected`: worksite cleared, and the route and worksite protected.
- `alternative`: worksite cleared, and a separately justified alternative access plan approved.
- `cleared`: worksite cleared, but NEP route protection stays unknown (not enough for a NEP EVA).
- `blocked` or `unknown`: no clearance for this task.

This example clears communications and monitoring and blocks both radiator tasks. It is an assumed access
scenario, not a claim about the real spacecraft:

```sh
.venv/bin/python -m sim.run_comparison --engine NEP \
  --task-access communications=protected --task-access monitoring=protected \
  --task-access propulsion_initial=unknown --task-access propulsion=blocked \
  --output-dir results/nep_task_access_example
```

Task assessments are saved in the comparison summary's recovery configuration. Shutdown alone approves no task,
and none of these confirmations calculates reactor dose.

The 0.4 and 20 g/cm² aluminium references apply only to the SPE model, not to the reactor shadow shield. Cone
geometry, reactor dose, cooldown duration and remote repair are not simulated. Remote repair is a planning option
outside the model and gives neither permission for a human EVA nor automatic repair credit. The access check
changes no SPE rate, dose calculation or deadline.

```python
from sim.mission_recovery import RecoveryConfig

constraints = RecoveryConfig(nep_repair_deadline_hours=24.0,
                             ntp_restart_and_propellant_margin=False)
# simulate_mission(policy, ..., recovery_config=constraints)
```

Use the same scenario and configuration for every strategy and vary only what each observes and decides. B, C and
D are described in `informed_strategies.md`, and the Monte Carlo study is in `monte_carlo.md`. Radiation inputs
are unchanged, and calls without recovery keep the legacy behavior. Event logs and summaries record decisions,
configuration and `qualitative_constraints_v4`, and there is no separate recovery ledger.

## Paired urgency experiments

`sim.run_sensitivity` exercises the gates with shared repair deadlines and procedural warning holds. A deadline
applies to propulsion recovery and its prerequisites, not necessarily to the final communications repair. The
default sweep values are illustrative. The warning hold is a preset restriction shared by all strategies and uses
no true storm data. The study assumes protected NEP access explicitly and does not weaken the default
unknown-access gate. Outputs separate repair completion, reference exceedances and simulator status, so don't read
`mission_continuation_authorized` alone as an exposure-safe or validated outcome.

## Repair accounting

A delayed candidate departure counts the selected noncritical EVA and its turnaround before any remaining critical
repair chain, and critical candidates are counted once. This is still a minimum-time check and not a guarantee
against later restrictions or failed repairs. At normal and terminal time boundaries, a fully completed work
interval earns repair credit before exposure and operational reassessment, and an `assessment_required` log
records concurrent concerns. Completed repair alone never bypasses the continuation checks.

## Four-EVA reference workload

All strategies use the same four sequential EVAs of about seven hours, with a one-hour turnaround. The jobs below
are team assumptions, not CNL-specified tasks.

| Work item / ID | NTP | NEP |
| --- | --- | --- |
| 1 / monitoring | Restore external sensors and wiring needed for repair assessment | Same |
| 2 / propulsion_initial | Repair a remotely isolated, accessible hydrogen-feed section | Isolate or bypass a damaged, accessible radiator-loop section |
| 3 / propulsion | Repair separate external engine-control connections | Restore additional heat-rejection capacity |
| 4 / communications | Repair antenna and feed connections | Same |

The reference assumes minimum safe-access information, shutdown and temporary cooling are confirmed before EVA.
Restored monitoring is a prerequisite for propulsion work only when configured that way. The list is not a
universal order of work for nuclear spacecraft. Worksites, compatible spares, repair interfaces and autonomous
repair authority are assumed available, and no human reactor-core repair is proposed. Ground communications are
not a default prerequisite, and a configured communications prerequisite overrides that.

The first propulsion task must come before the second, and both must finish to credit propulsion recovery. The
first alone does not establish useful cooling capacity, stop a modeled leak, extend the deadline or authorize
restart, and each of those would need its own assumption. The optional critical deadline covers the urgent task
and its actual prerequisites, and other work can finish afterward. Continuation needs all four repairs plus the
engineering and crew checks.

When monitoring is a prerequisite to both propulsion tasks, the critical work can finish at 24 h and all four
returns at 33 h with the default 0.5 h return and 1 h turnaround. Legacy three-task and subset scenarios still
work, with an omitted task assumed already resolved. Use the recovery model to enforce prerequisites, because
without it the legacy run follows the configured order but enforces no engineering gates. Do not describe
three-task results as four-task results.

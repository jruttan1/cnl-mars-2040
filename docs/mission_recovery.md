# Shared mission-recovery rules

Enable with `--recovery` or pass `RecoveryConfig()` to `simulate_mission`.
There is one simulator: it owns the clock, EVA progress, exposure and outcomes.
`sim/mission_recovery.py` only checks rules. Its configuration is fixed for a run.

| Decision | NTP reference scenario | NEP reference scenario |
| --- | --- | --- |
| Stabilize before EVA | Confirm coast shutdown and temporary cooling | Remote shutdown and damaged-loop isolation; requires remote control |
| Propulsion repair means | External leak isolation/feed/control restoration | External power/cooling/thruster restoration |
| Repair priority | Scenario urgent task and necessary prerequisites | Scenario urgent task and necessary prerequisites |
| Worksite clearance | Required for propulsion work | Required for all EVAs in the assumed shielded work area |
| Hard repair deadline | Disabled by default | Disabled by default |
| Continue mission only if | Restart and propellant margin confirmed | Sustained power and cooling confirmed |

**The windows, access rules, damage details and readiness confirmations are hypothetical scenario
assumptions, not measured conditions or technology-wide limits.** Repair priorities differ by engine,
without claiming a universal completion deadline. Optional `*_repair_deadline_hours` values remain
available for explicitly configured sensitivity comparisons; both default to `None`. Each existing repair remains a
seven-hour EVA by default; no extra task types or detailed reactor physics are added.

## Evidence versus assumptions

- **CNL facts:** NTP/NEP missions, meteoroid damage to propulsion/monitoring/communications,
  multiple approximately seven-hour EVAs, approaching SPE and unreliable monitoring.
- **Published principles:** the National Academies' *Space Nuclear Propulsion for Human Mars
  Exploration*, chapters 3–4 (archived as `national_academies_ntp.html` and
  `national_academies_nep.html`), distinguishes NTP propellant systems from NEP power conversion
  and heat rejection. CNSC guidance supports continued decay-heat removal after shutdown,
  not a spacecraft cooldown duration. Sources and hashes are in `data/raw/mission_recovery/provenance.json`.
- **Our assumptions:** every numerical window and boolean gate here. The slide's 10 MWt,
  6 Sv/h and 24-hour examples are not used as established values. Reactor dose is not calculated.

## Exact behavior

Stabilization is a zero-duration procedural confirmation in the existing mission loop, not a
simulated thermal transient. Shutdown, cooling and shielding must already be confirmed; missing
confirmation prevents stabilization. Stabilization cannot be repeated or performed during EVA.
All EVAs require stabilization, consent, qualification and existing operational permissions.
Monitoring repairs restore engineering checks, not perfect radiation knowledge.

Windows run from mission hour zero and never reset. A propulsion repair completed exactly at its
deadline retains completion credit. A new exposure or operational concern at that instant
is logged for reassessment; it does not undo finished work. Earlier aborts still prevent completion. Otherwise the simulator ends with
`no_feasible_recovery_plan`, with any active astronaut still accruing outside exposure during return.
This means an assumed recovery option was lost, not crew death or a predicted reactor accident.
A temporary hold advances time and processes observations; it no longer ends the run.
Continued shelter after a terminal decision requires an explicit feasibility assumption for comparison.

Continuation requires completed repairs, crew inside, engine readiness and authorization.
Existing reactor/readiness confirmations default to true for a repairable reference scenario, not as empirical facts.
The new NEP route-protection confirmation defaults to unknown and alternative access approval to false.
An explicitly omitted repair is assumed already functional; its deadline does not apply.
NEP's default priority is advisory to strategies, while launch prerequisites and deadlines are enforced
by the simulator regardless of strategy. Ground-contact authorization and preapproved local repair
authority are separate from a communications-repair prerequisite.

Strategy A now checks a simple lower bound before launching: remaining propulsion prerequisites plus
propulsion itself, using the configured EVA duration, turnaround and next launch time. If even that
cannot fit before the assumed deadline, A reports no feasible recovery plan instead of launching a futile attempt.
If doing another repair first would use the remaining time, A prioritizes the critical chain.
Completion exactly at the deadline is allowed. No deadline check applies once propulsion is repaired
or when its deadline is disabled. This is a necessary-time check, not a scheduling guarantee: future
restrictions and crew availability can still delay work, and A checks again at each decision.
It uses neither actual accumulated dose nor future storm intensity. No deadline values or physical
assumptions should be inferred from this policy. Temporary holds now advance the clock; see
`operational_realism.md` for explicit return, rest, autonomy and common-period exposure accounting.

## NEP reactor access: separate from SPE shielding

Before any NEP EVA, check the worksite **and the entire outbound/return route**:

```text
Within the reactor shadow shield's protected region?
  Yes -> reactor worksite conditions cleared? -> existing SPE/operational checks
  No / unknown -> approved alternative EVA access? -> same clearance and SPE checks
                  No -> do not launch; revise access plan or consider remote repair
```

Each of the four tasks now has an independent `RepairAccess` assessment in
`RecoveryConfig.repair_access`: `communications`, `monitoring`, `propulsion_initial`, and
`propulsion`. Each assessment records worksite clearance, protection of the worksite and entire
outbound/return route, and approval of an alternative access procedure. NTP also uses per-task
worksite clearance; NEP additionally requires protected access or the approved alternative.
Clearance never bypasses shutdown, cooling, shielding integrity, stabilization, prerequisites,
or crew permissions. The shared launch boundary enforces the assessment for all four strategies.

The older global switches remain explicit **all-task assumptions** for existing scenarios.
A task entry replaces those switches completely for that task, so an unknown or blocked entry
cannot inherit a blanket approval. Without a task entry, NEP protection remains unknown by default;
the legacy NTP reference scenario retains assumed worksite clearance. No task's actual physical
location is inferred from its name. Protected communications does not establish protected radiators.

The comparison runner accepts repeated `--task-access TASK=STATUS` options:

- `protected`: worksite cleared and outbound/return route plus worksite protected.
- `alternative`: worksite cleared and a separately justified alternative access plan approved.
- `cleared`: worksite cleared, but NEP route protection remains unknown (insufficient for NEP EVA).
- `blocked` or `unknown`: no clearance for this task.

For example, this explicitly assumed access scenario clears communications and monitoring but
blocks both radiator tasks; it is not a claim about the actual spacecraft geometry:

```sh
.venv/bin/python -m sim.run_comparison --engine NEP \
  --task-access communications=protected --task-access monitoring=protected \
  --task-access propulsion_initial=unknown --task-access propulsion=blocked \
  --output-dir results/nep_task_access_example
```

Task assessments are saved in the comparison summary's recovery configuration.
Shutdown alone does not approve any task, and none of these confirmations calculates reactor dose.

The 0.4 and 20 g/cm² aluminium references apply only to the existing SPE model, not to the reactor
shadow shield. Cone geometry, reactor dose, cooldown duration and remote repair are not simulated.
Remote repair is an external planning option, not permission for a human EVA or automatic repair credit.
No SPE rates, accumulated-dose calculations, or repair deadlines change with this access check.

```python
from sim.mission_recovery import RecoveryConfig

constraints = RecoveryConfig(nep_repair_deadline_hours=24.0,
                             ntp_restart_and_propellant_margin=False)
# simulate_mission(policy, ..., recovery_config=constraints)
```

Use identical scenario/configuration across strategies; vary only their observations and decisions.
B–D are implemented as described in `informed_strategies.md`; a Monte Carlo study is not yet provided.
Radiation inputs and calculations are unchanged;
calls without recovery retain legacy behavior. Existing event logs and summaries record decisions,
configuration and `qualitative_constraints_v4`; no separate recovery ledger is created.

Verification (2026-11-17): eight legacy runs across both engines, timing templates and severities
were unchanged, excluding the new stabilization flag. All 94 protected source/frozen files retained
their SHA-256 hashes. Temporary checks covered 29 mission runs, safety/readiness gates, delayed
repair failure, disabled deadlines, exact/fractional deadline boundaries, time-step independence,
exposure accounting and invalid inputs. No permanent test suite was added.

## Paired urgency experiments

`sim.run_sensitivity` exercises existing gates with shared repair deadlines and procedural
warning holds. A deadline applies to propulsion recovery and its prerequisites, not necessarily
the final communications repair. Default sweep values are explicit illustrative assumptions.
The warning hold is a preset operational restriction shared by A–D; it uses no true storm data.
The study assumes protected NEP access explicitly and does not weaken the default unknown-access gate.
Comparison outputs distinguish repair completion, reference exceedances and simulator status.
Do not interpret `mission_continuation_authorized` alone as an exposure-safe or validated outcome.

## Repair accounting corrections

Delayed candidate departures include the selected noncritical EVA and its turnaround before
any remaining critical repair chain. Critical candidates are counted once. This remains a
minimum-time feasibility check, not a guarantee against later restrictions or failed repairs.
At normal and terminal time boundaries, a full completed work interval earns repair credit
before exposure/operational reassessment. An `assessment_required` log records concurrent
concerns. Repair completion alone does not bypass continuation checks.

## Four-EVA reference workload (current default)

All four strategies use the same four sequential, approximately seven-hour EVAs and
one-hour turnaround. The jobs below are team assumptions, not CNL-specified tasks.

| Work item / ID | NTP | NEP |
| --- | --- | --- |
| 1 / monitoring | Restore external sensors/wiring needed for repair assessment | Restore external sensors/wiring needed for repair assessment |
| 2 / propulsion_initial | Repair remotely isolated, accessible hydrogen-feed section | Isolate/bypass damaged accessible radiator-loop section |
| 3 / propulsion | Repair separate external engine-control connections | Restore additional heat-rejection capacity |
| 4 / communications | Repair antenna/feed connections | Repair antenna/feed connections |

This reference assumes minimum safe-access information, shutdown and temporary cooling
are already confirmed before EVA. Restored monitoring is required for propulsion work only when
explicitly configured. This workload list is not a universal execution order for nuclear spacecraft.
Worksites, compatible spares, repair interfaces and autonomous repair authority are assumed
available; no human reactor-core repair is proposed. Ground communications are not a default
prerequisite. A configured communications prerequisite overrides that assumption.

The first propulsion task must precede the second. Both must finish to credit propulsion
recovery; the first alone does not establish useful cooling capacity, stop a modeled leak,
extend the deadline or authorize restart. These effects would require separate assumptions.
The optional critical deadline covers the named urgent task and its actual prerequisites.
Other work may finish afterward. Continuation
requires all four repairs and existing engineering/crew checks.

When monitoring is explicitly prerequisite to both propulsion tasks, the critical work can finish
at 24 h and all four returns finish at 33 h with the default 0.5 h return and 1 h turnaround.
Explicit legacy three-task or subset scenarios remain supported: an omitted task is assumed
already resolved. Use the recovery model for prerequisite enforcement. Without it, legacy
execution follows the configured order but does not enforce engineering gates.
Earlier three-task results must not be described as four-task results.

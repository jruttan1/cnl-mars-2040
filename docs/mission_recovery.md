# Shared mission-recovery rules

Enable with `--recovery` or pass `RecoveryConfig()` to `simulate_mission`.
There is one simulator: it owns the clock, EVA progress, exposure and outcomes.
`sim/mission_recovery.py` only checks rules. Its configuration is fixed for a run.

| Decision | NTP reference scenario | NEP reference scenario |
| --- | --- | --- |
| Stabilize before EVA | Confirm coast shutdown and temporary cooling | Remote shutdown and damaged-loop isolation; requires remote control |
| Propulsion repair means | External leak isolation/feed/control restoration | External power/cooling/thruster restoration |
| Repair priority | Existing configured order; monitoring before propulsion | Monitoring, propulsion/cooling, communications |
| Worksite clearance | Required for propulsion work | Required for all EVAs in the assumed shielded work area |
| Complete propulsion repair by | 32 mission hours | 16 mission hours |
| Continue mission only if | Restart and propellant margin confirmed | Sustained power and cooling confirmed |

**The windows, access rules, damage details and readiness confirmations are hypothetical scenario
assumptions, not measured conditions or technology-wide limits.** They demonstrate the cost of delay;
they do not establish that NEP is inherently less safe. Set either `*_repair_deadline_hours` to `None`
to disable that window, or change it for sensitivity comparisons. Each existing repair remains a
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
deadline succeeds unless an operational abort applies. Otherwise the simulator ends with
`ntp_propellant_recovery_window_lost` or `nep_thermal_recovery_window_lost`, returning an active EVA
with its accrued exposure and no partial repair credit. This means the assumed recovery option was
lost—not crew death or a predicted reactor accident. A hold/abandon decision ends the modeled
window; it does not simulate indefinite safe shelter or guarantee a return trajectory.

Continuation requires completed repairs, crew inside, engine readiness and authorization.
Boolean confirmations default to true for a repairable reference scenario, not as empirical facts.
An explicitly omitted repair is assumed already functional; its deadline does not apply.
NEP's default priority is advisory to strategies, while launch prerequisites and deadlines are enforced
by the simulator regardless of strategy. `communications_before_propulsion` can require ground involvement.

Strategy A now checks a simple lower bound before launching: remaining propulsion prerequisites plus
propulsion itself, using the configured EVA duration, turnaround and next launch time. If even that
cannot fit before the assumed deadline, A requests a hold instead of launching a futile attempt.
If doing another repair first would use the remaining time, A prioritizes the critical chain.
Completion exactly at the deadline is allowed. No deadline check applies once propulsion is repaired
or when its deadline is disabled. This is a necessary-time check, not a scheduling guarantee: future
restrictions and crew availability can still delay work, and A checks again at each decision.
It uses neither actual accumulated dose nor future storm intensity. No deadline values or physical
assumptions were changed by this policy update; hold still ends the modeled decision window.

```python
from sim.mission_recovery import RecoveryConfig

constraints = RecoveryConfig(nep_repair_deadline_hours=24.0,
                             ntp_restart_and_propellant_margin=False)
# simulate_mission(policy, ..., recovery_config=constraints)
```

Use identical scenario/configuration across strategies; vary only their observations and decisions.
B–D and Monte Carlo remain unimplemented. Radiation inputs and calculations are unchanged;
calls without recovery retain legacy behavior. Existing event logs and summaries record decisions,
configuration and `qualitative_constraints_v3`; no separate recovery ledger is created.

Verification (2026-11-17): eight legacy runs across both engines, timing templates and severities
were unchanged, excluding the new stabilization flag. All 94 protected source/frozen files retained
their SHA-256 hashes. Temporary checks covered 29 mission runs, safety/readiness gates, delayed
repair failure, disabled deadlines, exact/fractional deadline boundaries, time-step independence,
exposure accounting and invalid inputs. No permanent test suite was added.

# Paired Monte Carlo experiment

The runner calls the existing mission engine. It does not introduce a second simulator, new
clinical outcomes, or a weighted score. The initial experiment fixes the **2003 timing profile and
1-in-1,000 SAPPHIRE spectrum**. NTP/NEP and MAX/FAX reference cohorts are reported separately.

## Run it

```sh
.venv/bin/python -m sim.run_monte_carlo --trials 100 --output-dir results/monte-carlo/2003_1000_100draws
```

This means 100 independent emergencies, each evaluated for two engines, two reference anatomies,
and A–D: **1,600 mission executions**. A pilot with `--trials 2` runs 32 executions and is only a
software check, not a stable performance estimate. Output is written after each four-strategy group.
Repeat the exact command with `--resume` after interruption. Resume refuses changed configuration
or source hashes. To change assumptions, use a new folder.

Edit `configs/monte_carlo_2003_1000.json` or pass `--config PATH`.

## Starting random inputs

| Input | Distribution | Interpretation |
|---|---|---|
| Historical profile origin | Uniform 24–72 h | Which hour in the historical storm record corresponds to emergency hour zero |
| Forecast origin error | Uniform −6 to +6 h | Noisy forecast center = true profile origin + error; individual strategies do not receive the true origin |
| Urgent-repair deadline | Uniform 24–72 h | Team assumption, shared by every strategy; applies to `propulsion_initial` |
| EVA work duration | Uniform 6–8 h | Drawn once for the emergency and shared by all four tasks; represents uncertain workload across cases, **not an unannounced mid-EVA overrun** |
| Biological measurement noise | Existing seeded observation model | New seed each emergency, shared across C/D and matched engine/anatomy cohorts |

These ranges and their independence are experimental choices, not measured distributions or CNL
facts. Source-profile origin is not a validated SPE-onset time relative to Mission Control's warning.
The selected historical shape and severity class are assumed known to the forecast; timing is imperfect.
Forecast ensemble uncertainty remains the existing ±6 h and 0.7/1/1.3 magnitude factors. The true
SAPPHIRE event magnitude is fixed within this first experiment. Return periods are not encounter
probabilities. No probability-weighted average over engine types or sexes is produced.

Keep shielding, crew count, task access, GCR, and biomarker calibration fixed initially. Test D
processing latency, availability, and calibration as separate controlled sensitivity experiments.
Otherwise it becomes hard to identify what caused a performance difference.

## Matched current-rate recovery experiment

Use `configs/monte_carlo_matched_bounded_forecast.json` for the same 100
emergencies, both engines and both reference anatomies as the original matched
current-rate run. Each strategy keeps its original assay schedule and evaluates
the same departure and continuation rules. The forecast magnitude grid
approximates the sampled forecast-error range. The original 5% out-of-range
strength tail is a separate sensitivity condition in
`configs/monte_carlo_matched_restart.json`, which uses the same restart protocol.

The [restart protocol](informed_strategies.md#forecast-and-quantities) checks
both the forecast's recent rate and the selected astronaut's accumulated dose
before a return to an interrupted repair. Two qualifying hours after return is a
scenario assumption. The main comparison retains atomic repair work and assumes
the current estimated rate persists for the planned EVA and return.

```bash
.venv/bin/python -m sim.run_monte_carlo \
  --config configs/monte_carlo_matched_bounded_forecast.json \
  --output-dir results/monte-carlo/bcd_bounded_forecast_full_100 --workers 8
```

## Fixed starter assumptions

- Five crew, one astronaut outside at a time, four tasks, existing return/rest/turnaround rules.
- All four NTP worksites cleared and all four NEP routes/worksites protected, explicitly listed
  task by task in the configuration. Omit a task from its clearance list to block it. These are
  a repairable reference scenario, not measured spacecraft geometry or approval of real EVA access.
- First propulsion task urgent; second depends on first. Monitoring is not automatically a prerequisite.
- Zero shared warning hold: A is the existing immediate/procedural comparator, not a clinically
  validated conservative response to an SPE. Set `warning_hold_h` for a shared hold sensitivity.
- Common 96-hour dose observation, assuming continued cabin shelter remains feasible after
  recovery termination. If that assumption is disabled, exposure rankings are suppressed when
  observation periods differ. Mission recovery time remains distinct from exposure end time.
- Constant GCR enabled with the documented EVA proxy; prior cruise exposure and reactor dose excluded.

## Male and female reference cohorts

`MAX` and `FAX` are separate homogeneous reference-anatomy cohorts. The same random emergency
is reused across both, as well as across engines and strategies. No mixed-sex crew optimization
or personalized body-size response is claimed. Each policy's forecast uses the known cohort anatomy.
Astronaut gender labels alone do not change physics; the explicit scenario anatomy selects transport.

MAX uses the preserved corrected anatomical table. FAX uses the four archived OLTARIS exports
in `data/raw/oltaris/fax_2026-11-18`, verified against their saved SHA-256 checksums. FAX Gray
Equivalent values are in cGy-Eq and are multiplied by 10, while absorbed doses already use mGy.
Separate full-event BFO, skin and lens totals are distributed using the same historical weights.
This is an organ-specific transport change, not a generic female sensitivity multiplier.
The existing GCR reference remains a male-reference proxy shared by both cohorts. Biomarker
response functions/noise are also shared; no sex-specific medical calibration has been established.

## Outcomes

There is no single numerical grade. Report these side by side:

1. Fraction completing the urgent repair by its deadline (checked against actual completion time).
2. Fraction completing all four repairs within the observation window.
3. Fraction completing all repairs while every crew member remains below all three modeled organ
   references over the common observation period. This is not proof of clinical safety.
4. Maximum individual BFO, skin and lens Gray Equivalent; reference exceedance frequency.
5. Repair count, completion time conditional on finishing, aborted EVAs, and termination categories.

The same thresholds apply to A–D. The worst-exposed crew member is assessed for each organ;
these maxima need not be the same person. No crew-death probability is inferred.

Outputs: `strategy_summary.csv`, `paired_differences.csv`, `trial_results.csv`, `draws.csv`,
`summary.json`, and `manifest.json`. Trial checkpoints retain configurations, individual crew
outcomes and EVA attempts. Trial zero also retains detailed exposure, measurement and decision logs.
Paired comparisons report B−A, C−B, D−C, and D−A for the same emergencies. Proportion intervals
use Wilson's method; paired mean differences use an approximate 95% Monte Carlo standard-error
interval (unavailable with one draw). They quantify sampling noise under this chosen experiment,
not uncertainty in radiation physics, biology, ethical judgment, or the assumed distributions.

## Mixed-storm experiment (18 November)

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m sim.run_monte_carlo --config configs/monte_carlo_mixed_storms.json --workers 4 --output-dir results/monte-carlo/mixed_storms_100`.

One hundred independent emergencies reuse exactly the same draws for A–D, NTP/NEP,
and MAX/FAX reference cohorts. Each draw chooses either historical profile with
probability 0.5, then a continuous proton-fluence multiplier uniformly from 0.35 to
1.25 of the corrected 1,000-year source spectrum. This includes magnitudes below,
between, and above the reference scenarios. It does **not** reproduce the 100-year
spectral shape or establish intermediate return periods. Spectral hardness remains
fixed. These are deliberately selected stress-test distributions, not inferred
space-weather probabilities.

The forecast contains both historical shapes, three timing offsets and three strength
factors (18 members). Its central strength is the true multiplier times an independent
uniform error from 0.6 to 1.4. Its origin has an independent ±6-hour error. No true
profile selection is supplied to the policy. Ensemble bounds are illustrative and
need not contain truth; they are not a calibrated 95% forecast interval.

The emergency begins at historical-profile hour 24–72. This varies storm phase at
emergency onset, **not** a future storm-arrival time. Earlier exposure before mission
hour zero is excluded. Seven hours of repair work, the additional half-hour return,
four tasks, five crew and a 48-hour urgent deadline remain fixed. All exposure
comparisons use 96 hours including cabin exposure after operational termination,
conditional on continued shelter being feasible. The deadline is a team assumption.

SPE multipliers scale only solar exposure. They do not scale GCR or reactor fields.
Reactor access remains a task-specific clearance assumption; no quantitative reactor
radiation is calculated. MAX and FAX are separate reference cohorts, not mixed-sex
crews or personalized biological response models. All tasks have reference clearance,
so this batch may show little NTP/NEP differentiation. Strategy A with zero warning
hold is the existing immediate-repair procedural comparator.

Parallel workers checksum-validate source tables on first load and cache them locally.
Checkpoints retain paired outcomes; the manifest records code/data hashes, checked
again before accepting the batch. Sampling intervals cannot cover model inadequacy,
forecast calibration errors, biomarker extrapolation, or unmodeled engineering hazards.

## B–D revision

Current comparison and Monte Carlo runners exclude Strategy A. The old A implementation
and historical results remain for provenance, but are withdrawn as evidence for a
health-first numerical baseline. New checkpoints require B/C/D only and changed code
hashes prevent resuming pre-revision batches.

The revised shared policy uses posterior scenario probabilities for coherent total
BFO/skin/lens exposure, including the proposed EVA and return. It gates the joint
probability of any reference exceedance at 5%. Six-hour cabin panels let C and D
collect delayed evidence while sheltered. See `informed_strategies.md` for the
persistent-scenario assumption and limits. This does not establish clinical validation
or guarantee C/D superiority.

A pilot can use the first 12 emergencies of the mixed-storm seed, selected without regard to
outcomes. It retains both engines, both reference anatomies, the same physical draws, and all
workload/reference values.
Use a new output directory; old 100-emergency results are not results for this revision.

The first full revised BCD run (`bcd_full_100`) was stopped during behavioral audit
because crew rotation allowed repeated short aborted attempts on the same task.
It is incomplete and is not a final comparison. `bcd_reassessed_full_100` is the
fresh rerun with shared reassessment and restart hysteresis. No checkpoints from
the old policy are reused. Its watchdog stops on invariant failures or three
aborted attempts on one task, requiring inspection rather than silently accepting
repeated launch/abort cycles.

A further audit stopped `bcd_reassessed_full_100`: a fast post-return lymphocyte
result allowed a restart while the post-return H2AX result was pending, followed
by another abort at H2AX arrival. The final rerun is `bcd_reassessed_v2_full_100`.
C/D now specifically require the returned post-return H2AX result. Compact restart
and returned-H2AX logs are retained for every checkpoint, and the watchdog checks
the actual evidence and risk margin for each post-abort launch. Neither interrupted
batch is a completed comparison, and none of its checkpoints is reused.

## Dose and reference timing outputs

The trial outputs include total crew BFO absorbed dose in person-mGy and the same
total divided by crew size in mGy. Each checkpoint records the first hour each
astronaut reaches each BFO, skin or lens reference, plus the earliest such hour
across the crew for each organ. A missing crossing means the reference was never
reached within that run's observation window. Crossing times are linearly
interpolated within the exposure intervals, using the accumulated mGy-Eq for each
organ. The strategy summary reports the number of cases reaching each reference
and the median crossing hour among those cases. It compares doses only over a
common observation period. The individual and crew timings are retrospective
simulation outcomes and do not enter the decision policy.

## Decision-tree experiment (B, C and D decide differently because they know different things)

`configs/monte_carlo_decision_trees_current_rate.json` is the primary experiment for showing how the three
strategies **decide** differently on the same emergency. It replaces the matched current-rate mode, which forced
C and D onto B's rule and so could not show decision differences.

**No strategy knows the future.** B, C and D all project today's *estimated* dose rate forward through the planned EVA
and return, and re-estimate it every hour (`shared_current_rate`). That is a predictive estimate, not a forecast of the
storm's future trajectory, so a rising storm makes any of them stop (abort) and a falling one lets them start.
`configs/monte_carlo_decision_trees.json` is a labelled sensitivity in which all strategies integrate the forecast
ensemble's future (`b_projection: ensemble`); it is not the primary result.

| Setting | Value | Why |
|---|---|---|
| `shared_current_rate` | true | All three project the current estimated rate; none integrates a future trajectory |
| `forecast_stress_weight` | 0 | The 5% "forecast badly wrong" member equals the launch risk tolerance and exceeds the 2.5% restart tolerance, so it blocked B and the retry rule on its own |
| `abort_progress_credit` | 1.0 | An abort keeps the hours worked; a retry only finishes what remains. Assumption (0 reproduces the older all-or-nothing repair) |
| `retry_after_abort` | true, 2 h review | Every strategy holds an aborted repair until the same restart review passes. Previously only C held it, permanently |

What differs between the trees (information and policy, not hard-coded outcomes):

- **B** forecast-derived estimate only. No biology. Crew chosen by rotation. Storm weights stay at the forecast prior.
- **C** adds returned conventional readings (H2AX, lymphocytes, with their delays). They update the shared storm weights, rank crew by estimated exposure, and hold an astronaut until a post-EVA H2AX result returns.
- **D** adds faster foci processing and in-suit readings, which drive in-EVA continue/abort decisions. D's optional dose-saving
  waits need a future departure projection, so they cannot fire when nobody uses a future projection.

At hour 0 all three hold identical information, so identical early decisions are correct, not a defect.
Results lead with `DECISIONS.md` (how often decisions differ, the first divergence hour, and what caused it), then outcomes
with their spread across emergencies. `python -m sim.write_results <folder>` writes `RESULTS.md`.
Decisions are classified using the compact decision log stored in every checkpoint (`sim/decision_metrics.py`).

Limits: the abort credit, restart review, ensemble members and their equal weights are experimental assumptions.
Hindsight feasibility is unchanged by the credit.

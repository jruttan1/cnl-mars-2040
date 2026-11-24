# Monte Carlo experiment

The runner calls the same mission engine as everything else. It adds no second simulator, no clinical
outcome and no weighted score. Strategies B, C and D face the same random emergency, so any
difference between them comes from what they know and how they decide. Strategy A is not in the Monte Carlo.
Its old implementation stays in the repo as a baseline for the single-mission runs.

## The primary experiment

`configs/monte_carlo_decision_trees_current_rate.json` asks one question: does extra information change
what the crew does? Each of 100 emergencies runs for NTP and NEP, for the MAX and FAX reference anatomies
and for B, C and D, which is 1,200 mission runs.

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1   # stops worker processes fighting over CPU cores
.venv/bin/python -m sim.run_monte_carlo --config configs/monte_carlo_decision_trees_current_rate.json \
  --output-dir results/monte-carlo/decision_trees_current_rate_100 --workers 10
.venv/bin/python -m sim.write_results results/monte-carlo/decision_trees_current_rate_100
.venv/bin/python charts/12_decision_tree_results.py
```

It takes about 11 minutes on 10 cores. If a run is interrupted, repeat the same command with `--resume`.
Resume refuses to continue if the config or source code has changed, so use a new folder when you change
assumptions. A pilot with `--trials 2` is a software check, not a performance estimate.

### What each strategy knows

No strategy knows the future. B, C and D all project today's estimated dose rate through the planned EVA and
the return, and they re-estimate it every hour (`shared_current_rate`). That is a predictive estimate of the
current rate, not a forecast of where the storm goes next. A rising storm makes any of them abort, and a
falling one lets them start. At hour 0 the three hold the same information, so identical early decisions
are expected.

- **B** uses the forecast-derived estimate only. It has no biology and picks crew by rotation.
- **C** adds returned blood readings (γ-H2AX with a 5 h lab delay, lymphocytes). They update the storm
  weights, rank the crew by estimated exposure, and hold an astronaut until a post-EVA γ-H2AX result is back.
- **D** adds faster foci processing (1 h) and in-suit readings, which can trigger an abort mid-EVA.
  Its optional dose-saving waits need a projection of the future, so they never fire under a shared
  current-rate estimate.

All three clear the same gate: the probability that any organ reaches its reference (BFO 250, skin 1,500,
lens 1,000 mGy-Eq) must be 5% or less to launch or continue.

### Settings

| Setting | Value | Why |
|---|---|---|
| `shared_current_rate` | true | All three project the current estimated rate and none integrates a future trajectory |
| `forecast_stress_weight` | 0 | The 5% "forecast badly wrong" member equals the launch tolerance and exceeds the 2.5% restart tolerance, so by itself it blocked B and the retry rule |
| `abort_progress_credit` | 1.0 | An abort keeps the hours worked, and a retry only finishes what remains. This is an assumption; 0 gives the older all-or-nothing repair |
| `retry_after_abort` | true, 2 h review | Every strategy holds an aborted repair until the same restart review passes. Before this, only C held it, and permanently |

The defaults in the code keep the older behavior (`abort_progress_credit` 0, `retry_after_abort` off), so older
configs still reproduce.

### What it found

Decisions differ in 32 to 38% of cases, and most first splits come from new evidence moving the risk
estimate across the 5% gate or from an in-EVA reading. Outcomes barely move. The urgent repair finishes on
time in 42 to 43% of cases for all three, all four repairs finish in 2 to 4%, and no run reaches the 250 mGy-Eq
BFO reference (the worst is 158). More information changes the decisions here, but it does not raise the
repair count or lower crew dose. Figures and tables are in `results/presentation/decision_trees/`.

## Random inputs

| Input | Distribution | Meaning |
|---|---|---|
| Storm shape | 1972 or 2003 profile, 50/50 | Which historical profile times the dose |
| Storm strength | Uniform 0.35 to 1.25 of the corrected 1,000-year spectrum | Spans weaker and stronger than the reference storms. It does not change spectral hardness or give intermediate return periods |
| Emergency start | Uniform, profile hour 24 to 72 | Storm phase at mission hour 0. It is not a storm arrival time, and earlier exposure is excluded |
| Forecast origin error | Uniform, plus or minus 6 h | The forecast's timing is off by this much |
| Forecast strength error | Uniform 0.6 to 1.4 times the true strength | The forecast's central strength |
| Biological measurement noise | Seeded observation model | A new seed per emergency, shared by C and D and by matched engine and anatomy cases |

The forecast holds both historical shapes, three timing offsets and three strength factors (18 members). It is
never told the true shape. Its bounds are illustrative and need not contain the truth, so they are not a
calibrated interval.

Fixed in the primary config: seven hours of work per EVA plus a 0.5 h return, four tasks, five crew, one
astronaut outside at a time, and a 48 h deadline for the urgent task (`propulsion_initial`). All doses are
compared over 96 h, including cabin exposure after recovery ends, which assumes continued sheltering stays
feasible. The deadline is a team assumption. These ranges and their independence are experimental choices.
They are not measured distributions or CNL facts, and return periods are not encounter probabilities.

Storm strength scales only the solar dose. GCR and reactor fields are untouched. No reactor dose is calculated,
and task access is an assumption: all four NTP worksites are cleared and all four NEP routes are protected. That
is a repairable reference scenario, not measured spacecraft geometry. Because every task is cleared, NTP and
NEP may look alike.

## Male and female cohorts

`MAX` and `FAX` are separate reference anatomies, not mixed crews. The same random emergency runs on both, on
both engines and under every strategy, and each strategy's forecast uses the known cohort anatomy. MAX uses
the preserved corrected anatomical table. FAX uses the four archived OLTARIS exports in
`data/raw/oltaris/fax_2026-11-18`, checked against their saved SHA-256 hashes. FAX Gray Equivalent values are in
cGy-Eq and get multiplied by 10, while its absorbed doses are already in mGy. This changes organ-specific
transport only. It is not a generic female multiplier. The GCR reference and the biomarker response and noise
are shared by both cohorts, and no sex-specific medical calibration exists.

## Outcomes

There is no single score. The runner reports these side by side:

1. Fraction that finish the urgent repair by its deadline (checked against actual completion time).
2. Fraction that finish all four repairs within the observation window.
3. Fraction that finish all repairs with every crew member below all three organ references over the 96 h.
   This does not prove clinical safety.
4. Maximum individual BFO, skin and lens Gray Equivalent, and how often a reference is reached.
5. Repair count, completion time, aborted EVAs and how each run ended.

The worst-exposed crew member is assessed per organ, and those maxima can be different people. The runner
infers no crew-death probability.

Decision metrics come first in the results. For each pair of strategies, `sim/decision_metrics.py` finds the
first point where their launch and abort sequences differ and sorts the cause into four groups: new evidence
moved the risk across the gate, an abort call differed mid-EVA, a post-abort reassessment differed, or another
rule applied. It works from the compact decision log stored in every checkpoint and never re-simulates.

Output files: `strategy_summary.csv`, `paired_differences.csv`, `trial_results.csv`, `draws.csv`,
`summary.json`, `manifest.json`, and the written `RESULTS.md` and `DECISIONS.md`. Checkpoints keep the
configuration, each crew member's outcome and every EVA attempt, and trial 0 also keeps the detailed logs.
Proportion intervals use Wilson's method. Paired mean differences use an approximate 95% standard-error
interval, which is unavailable with one draw. These intervals measure sampling noise only. They say nothing
about uncertainty in the radiation physics, the biology or the assumed distributions.

The runner also records when each crew member first reaches each organ reference, interpolated within the
exposure intervals, and compares doses only over the common 96 h window. These crossing times are results.
They never feed a decision.

## Other configurations

These are sensitivities and earlier experiments, kept so results can be traced. None is the primary result.

| Config | Purpose |
|---|---|
| `monte_carlo_factorial_*.json` (four) | Separates the forecast stress allowance from the retry rule on identical emergencies. Neither changes outcomes much, because the stress member blocks retries on its own. `sim/analyze_factorial.py` writes the attribution report |
| `monte_carlo_decision_trees.json` | Same as the primary but every strategy integrates the forecast ensemble's future (`b_projection: ensemble`). B never aborted in this mode, so it is a labelled sensitivity |
| `monte_carlo_matched_*.json` | Forces C and D onto B's decision rule so only the evidence differs. It cannot show decision differences |
| `monte_carlo_mixed_storms.json`, `monte_carlo_bcd_biomarker_decisions.json` | Mixed-storm runs from before the retry and restart changes |
| `monte_carlo_2003_*` and `monte_carlo_1972_*` | Early single-profile runs with random deadlines (24 to 72 h) and work durations (6 to 8 h) |

Parallel workers checksum-validate the source tables on first load and cache them locally. The manifest records
code and data hashes, and the runner checks them again before accepting the batch.

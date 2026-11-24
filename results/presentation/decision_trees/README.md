# Decision-tree Monte Carlo: figures and provenance

Figures come as PNG for slides and SVG for editing.

| File | Message |
|---|---|
| `01_decisions_differ_and_why` | B, C and D decide differently in 32 to 38% of cases, and most first splits trace to new evidence |
| `02_one_emergency_three_crews` | One storm, three EVA sequences (a gain and a loss picked by rule, not typical cases) |
| `03_outcomes_barely_change` | Outcomes and exposure are nearly the same, and no run reaches the 250 mGy-Eq reference |
| `04_what_happens_after_an_abort` | C goes back out least often after an abort, which fits its 5 h lab turnaround but is not isolated |

`charts/12_decision_tree_results.py` computes every number printed on a figure from the run's checkpoints.
Results are conditional frequencies under a hypothetical emergency distribution and are not mission probabilities.

## Provenance

- **Run:** `configs/monte_carlo_decision_trees_current_rate.json` (copied to `provenance/config.json`). Seed 21,
  100 emergencies, each on NTP and NEP, on MAX and FAX, under B, C and D.
- **Settings:** all strategies project today's estimated dose rate and none sees the future. The forecast stress
  allowance is off, abort progress credit is 1.0, and every strategy can retry after an abort with a 2 h restart
  review. These are team assumptions, not CNL facts.
- **Raw data:** the checkpoints (about 70 MB) are git-ignored under
  `results/monte-carlo/decision_trees_current_rate_100/`. `provenance/` keeps the small tables: `RESULTS.md`,
  `DECISIONS.md`, `summary.json` and `manifest.json`.
- **Source hashes:** the manifest hashes were taken when the run started. `sim/decision_metrics.py` has since
  changed only the wording of the report tables. No simulation or decision logic changed after the run.

## Reproduce

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1   # avoids CPU oversubscription
.venv/bin/python -m sim.run_monte_carlo --config configs/monte_carlo_decision_trees_current_rate.json \
  --output-dir results/monte-carlo/decision_trees_current_rate_100 --workers 10     # about 11 min on 10 cores
.venv/bin/python -m sim.write_results results/monte-carlo/decision_trees_current_rate_100
.venv/bin/python charts/12_decision_tree_results.py
```

## Known limit

Outcomes barely differ between strategies here, because the safety gate keeps everyone far below the exposure
reference.

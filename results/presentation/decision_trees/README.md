# Decision-tree Monte Carlo: figures and provenance

Figures (PNG for slides, SVG to edit):

| File | Message |
|---|---|
| `01_decisions_differ_and_why` | B, C and D decide differently in 32–38% of cases; most first splits trace to new evidence |
| `02_one_emergency_three_crews` | One storm, three EVA sequences (a gain and a loss, picked by rule, not typical cases) |
| `03_outcomes_barely_change` | Outcomes and exposure are nearly the same; no run reaches the 250 mGy-Eq reference |
| `04_what_happens_after_an_abort` | C restarts least often after an abort; consistent with its 5 h lab turnaround, not isolated |

Every number printed on a figure is computed from the run's checkpoints by `charts/12_decision_tree_results.py`.
Results are conditional frequencies under the configured hypothetical emergency distribution, not mission probabilities.

## Provenance

- Run: `configs/monte_carlo_decision_trees_current_rate.json` (copy in `provenance/config.json`), seed 21, 100 emergencies × NTP/NEP × MAX/FAX × B/C/D.
- Settings: all strategies project today's estimated dose rate (none sees the future); forecast stress allowance off;
  abort progress credit 1.0; retry after abort for every strategy with a 2 h restart review. All are team assumptions, not CNL facts.
- Raw checkpoints (about 70 MB) are git-ignored under `results/monte-carlo/decision_trees_current_rate_100/`. `provenance/` keeps the small tables:
  `RESULTS.md`, `DECISIONS.md`, `summary.json`, `manifest.json`.
- The manifest's source hashes were taken when the run started. `sim/decision_metrics.py` later got a wording-only change
  (a table column label); no simulation or decision logic changed after the run.

## Reproduce

```bash
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1   # avoids CPU oversubscription
.venv/bin/python -m sim.run_monte_carlo --config configs/monte_carlo_decision_trees_current_rate.json \
  --output-dir results/monte-carlo/decision_trees_current_rate_100 --workers 10     # about 11 min on 10 cores
.venv/bin/python -m sim.write_results results/monte-carlo/decision_trees_current_rate_100
.venv/bin/python charts/12_decision_tree_results.py
```

## Known limits

- Outcomes barely differ between strategies here; the safety gate keeps everyone far below the exposure reference.
- Unit tests were archived outside this repository during the submission cleanup; this work was checked by invariant audits on the run output, not by that suite.

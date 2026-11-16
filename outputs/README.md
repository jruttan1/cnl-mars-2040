# CNL radiation outputs

- **mission_radiation_environment.csv** — frozen v1.0 baseline for Strategies A–D. This presentation copy matches the working CSV in `../data/processed/`.
- **charts/** — eight current PNG figures. Older King-only figures are separate in `charts/historical/`.
- **model/baseline_validation.md** — numerical checks and interpretation limits.
- **model/baseline_manifest.json** — frozen CSV checksum and provenance. Recorded paths refer to the project root.
- **model/** — supporting audits and reusable numerical results; large intermediate tables are generated locally and excluded from Git.

The baseline contains both SAPPHIRE scenarios, six aluminium shielding levels and nine timing variants across 264 hours. Select one scenario, shielding level and timing variant; do not sum variants. `estimate_type == "central"` selects the default timing assumption. Hours are measured from storm start; the default 72-hour display covers storm hours 48–120.

Dose rates and cumulative values describe an idealized tissue target, not verified astronaut whole-body doses. `data_quality` describes the historical timing observations; all doses are modeled.

From the project root:

```python
from radiation_model import load_baseline, baseline_interval_dose
baseline = load_baseline()
print(baseline_interval_dose("SAPPHIRE-1-in-100", 0.4, 16, 23,
                            baseline=baseline))  # 3.8272391527 tissue-target mGy
```

Edit individual figures in `../charts/`. Keep the frozen baseline unchanged while developing strategy code. Generated `.txt` captions were removed; plotting scripts may recreate them, and Git ignores them.

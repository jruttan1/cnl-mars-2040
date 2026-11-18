# Outputs

**Start here: [Open the six-chart gallery](final_case/index.html).**
The full-resolution PNGs are together in `final_case/`. JSON/CSV files elsewhere are supporting records,
not the presentation interface. Regenerate with `.venv/bin/python -B charts/build_final_case.py`.

## Results you can use

- `strategy_a/` or `runs/<name>/`: generated mission summary, timeline, decisions and crew exposure.
- `analysis/anatomical_eva/`: anatomical EVA comparison; retained method/provenance and regenerated chart/tables.
- `charts/`: regenerated supporting figures and captions.
- `validation/oltaris_anatomical/`: retained spectrum overlay, fit-error tables and validation evidence.

Mission runs use `summary.json` for assumptions/status, `event_log.csv` for decisions and
`bfo_exposure_history.csv` for accumulated exposure intervals. They keep absorbed mGy separate
from Gray Equivalent mGy-Eq. NASA reference comparisons are not compliance certificates.
Qualitative constraints use the same event log, not a second recovery ledger.

## Frozen/reference records: do not delete

- `mission_radiation_environment.csv`: frozen SHIELDOSE reference copy.
- `model/baseline_manifest.json`: frozen SHIELDOSE checksum and source configuration.
- `model/baseline_validation.md`, `model/sapphire_transport_audit.json` and
  `model/historical/radiation_environment_audit.json`: scientific reference validation/audits.

Old recovery runs, test/cleanup reports, file inventories and generated regression fixtures were
removed from the active repository. Their recovery copies are outside the repo; see the main README.
Historical test results inside retained scientific reports are past evidence, not an installed test suite.

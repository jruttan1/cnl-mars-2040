# Output map

Scientific definitions, assumptions and commands are consolidated in [the project README](../README.md).

Retained records:
- `mission_radiation_environment.csv`: frozen SHIELDOSE reference presentation copy; never disposable.
- `model/baseline_manifest.json`, `model/baseline_validation.md`: reference checksum and validation.
- `model/sapphire_transport_audit.json`, `model/historical/radiation_environment_audit.json`: source/calculation audits.
- `model/historical/mission_radiation_environment.csv`, `model/synthetic_sapphire_interval_exposure.csv`: existing test fixtures.
- `validation/oltaris_anatomical/`: corrected spectrum/anatomical validation evidence.
- `validation/repository_cleanup/`: cleanup inventory, baseline/after tests and integrity checks.
- `analysis/anatomical_eva/README.md`, `analysis/anatomical_eva/provenance.json`: analysis method and provenance; generated CSVs/figure were archived.
- `analysis/repository_file_guide.txt`, `analysis/all_local_files_inventory.txt`: updated local inventories.

Recreated on demand and Git-ignored:
- `strategy_a/`, `strategy_a_goes10/`: mission summaries, event/exposure ledgers, NASA reference comparisons and timelines.
- `charts/`: independent reference figures/captions.
- `analysis/anatomical_eva/*.csv` and `*.png`: shared-environment EVA comparison outputs.
- Intermediate full-event/hourly tables and legacy proxy/Band diagnostic outputs.

The external archive path and full move manifest are recorded in `validation/repository_cleanup/manifest.json`.
The old `charts/09_strategy_a_mission_timeline.png` and pre-integration consistency audit are historical,
not current simulator evidence. They are preserved externally.

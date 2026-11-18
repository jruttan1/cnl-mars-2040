# CNL mission simulator

The simulator estimates BFO exposure during hypothetical repair EVAs using **SAPPHIRE-derived
organ-dose estimates distributed using historical solar particle event timing profiles**.
The common OLTARIS anatomical environment is frozen as `oltaris_bfo_v1`. Strategy A is implemented;
Strategies B–D and Monte Carlo simulation are not implemented. An optional shared qualitative mission-recovery model now adds engineering, operational and crew-permission constraints.

## Start here

```bash
.venv/bin/python -B run_strategy_a.py
.venv/bin/python -B run_strategy_a.py --template october_2003_goes10 --output-dir outputs/strategy_a_goes10
```

For a new environment, create `.venv` with Python 3.12 and install `requirements.txt`.
The project test suite was removed at the owner's request. Historical test logs remain as past
validation evidence, not current automated coverage. A recovery copy of the removed suite is at
`/Users/jack/Documents/cnl_archive/removed_tests_20261117_195041/tests/`.
Edit `sim/assumptions.py` for everyday mission settings and `sim/defaults.py` for advanced options.
`sim/strategies.py` contains policy rules; `sim/models.py` defines observations and decisions;
`sim/mission_simulator.py` owns progression and hidden exposure accounting.

## Frozen scientific inputs

| Input | Role |
|---|---|
| `data/processed/oltaris/mission_bfo_environment.csv` | Primary anatomical exposure environment: 21,600 hourly bins |
| `data/processed/oltaris/mission_bfo_environment_manifest.json` | Source hashes, quantities, geometry and interpretation |
| `data/processed/oltaris/radiation_environment_freeze.json` | Pins dataset and manifest checksums; exporter refuses overwrite |
| `data/processed/oltaris/oltaris_sapphire_anatomical_summary.csv` | Four corrected Band/MAX run summaries |
| `data/processed/oltaris/oltaris_sapphire_organ_doses.csv` | 112 organ records with distinct units and provenance |
| `data/processed/mission_radiation_environment.csv` | Frozen SHIELDOSE tissue-target reference, 64,800 bins |
| `outputs/mission_radiation_environment.csv` | Preserved duplicate frozen SHIELDOSE presentation copy |
| `outputs/model/baseline_manifest.json` | Frozen SHIELDOSE checksum and configuration/source hashes |

No frozen radiation dataset was regenerated during repository cleanup. Do not run exporters or edit
frozen inputs as part of strategy development. A future scientific revision requires explicit authorization
and a separately versioned environment, not replacing v1 in place.

The anatomical totals are:

| SAPPHIRE severity | Aluminium g/cm² | BFO absorbed mGy | BFO Gray Equivalent mGy-Eq |
|---|---:|---:|---:|
| 100-year | 0.4 | 415.1 | 623.3 |
| 100-year | 20 | 43.14 | 63.99 |
| 1,000-year | 0.4 | 723.7 | 1087.0 |
| 1,000-year | 20 | 75.2 | 111.6 |

These are full-event totals under constant shielding. The mission selects EVA/cabin shielding for each
interval and sums exposure, including cabin time. Absorbed mGy is an exposure input for future biological
response models. Gray Equivalent mGy-Eq is kept separately for NASA organ-limit reference comparisons.
Organ dose equivalent and effective dose equivalent in mSv are neither of those quantities.

The NASA comparison uses Volume 1 Revision C, Table 4.8-1: BFO 250 mGy-Eq over 30 days and
500 mGy-Eq over one year. It covers modeled mission contribution only and does not certify compliance:
prior/background exposure and correspondence of source/NASA response-specific RBE definitions remain
unverified. The standard and GOES channel documentation are preserved in `data/raw/reference_documents/`.

## Source and timing model

SAPPHIRE/SPENVIS supplies event-integrated energy spectra for the 100-year main scenario and 1,000-year
stress test. These are severity scenarios, not predictions of occurrence during the mission. The corrected
Band approximation supersedes the earlier Weibull attempt; integral-spectrum errors at the original
81 energies per event are below approximately 3.2%, which is not a dose-error bound.

Corrected user-supplied OLTARIS summaries and organ records are preserved byte-for-byte under
`data/raw/oltaris/sapphire_corrected_band_2026-11-16/`. Native corrected solver exports remain pending
authenticated retrieval. MAX is a modeled adult male anatomy; crew sex/weight do not personalize exposure.
The 0.4 and 20 g/cm² aluminium spheres are EVA/cabin surrogates, not verified hardware. Other shielding
depths are not supported by the anatomical simulator.

| Timing template | Record | Status |
|---|---|---|
| `august_1972` | 264 hourly bins, eight missing hours per channel | Default; reconstructed gaps retain flags |
| `october_2003_goes10` | 336 complete supplied hourly bins | Enabled comparison |
| `october_1989` | 96/360 hours missing | Disabled; source retained |
| Separate 2003 OMNI2 CSV | 205/336 hours missing | Excluded; not the GOES-10 input |

Hourly dose = full-event organ dose × normalized hourly weight. Weights sum to one over the complete
selected record, not over an EVA or displayed window. This assumes fixed spectral shape and treats
historical timing as a proxy; it is not time-resolved transport or an actual future forecast.

Integral channels >10, >30 and >60 MeV, combined with log-linear, linear and PCHIP gap filling, produce
nine timing alternatives. The default is >10 MeV/log-linear. With no GOES gaps, its interpolation methods
coincide within each channel. Sensitivity bands are not confidence intervals and cannot bound an unseen
peak. The 1972 central peak EVA (storm hours 64–71) allocates 35.2% of its dose to three interpolated hours;
that fraction is not a dose-error estimate. The anatomical chart hatches those periods and compares all
methods at the same EVA start. Overlapping seven-hour windows are alternatives, not doses to sum.

GOES documentation describes integral proton flux in protons cm⁻² s⁻¹ sr⁻¹ with hourly averages from
five-minute data. Exact numerical matching of the supplied file to the official archive remains unverified.
The 1972 source also retains its documented threshold-order anomalies. Complete sampled coverage does
not establish physical event closure or Earth-to-mission propagation timing.

Reference spectra are applied to a hypothetical mission near **1.25 AU without distance adjustment**.
Original reports retain 1.2 AU labels and OLTARIS its 1 AU environment label. No extra duration or radial
multiplier is applied to already event-integrated spectra/doses.

## Independent references and retained legacy dependencies

SHIELDOSE-2 remains frozen and independent: idealized tissue at the centre of aluminium spheres,
4π irradiation, no proton nuclear attenuation. Its six shielding coordinates are 0.4, 1, 2, 5, 10 and
20 g/cm². Numerical rad are converted with 1 rad = 10 mGy. These are not anatomical BFO doses and
must not be substituted for current simulator values or clinical symptom thresholds.

All scientific source groups remain in `data/raw/`: verified November 16 SPENVIS sources and transport
exports, earlier reports needed for legacy-association checks, King OLTARIS reference databases, corrected
and superseded OLTARIS records, OMNIWeb originals and official reference documents. Full-year OMNI2
inputs remain under `data/processed/raw_nasa_omni2/`. Some source duplicates are deliberately retained
because provenance paths and preservation checks refer to them.

`prepare_data.py`, `spenvis_audit.py`, `radiation_model.py` and `organize_oltaris_anatomical.py` retain the
existing dataset-generation/audit paths. `prepare_data.py` still requires five tables in
`data/raw/archive/previous_processed/`: `spe_hourly.csv`, `spe_spectra.csv`, `shielding_dose.csv`,
`organ_dose.csv` and `exposure_settings.csv`. Those are rebuild inputs, not disposable backups.
The preservation manifest in `data/raw/archive/before_verified_sapphire/` and original move/validation
records are also retained. Their historical paths describe earlier locations; the cleanup manifest maps
moved records to the external archive. No scientific provenance was rewritten.

`bfo_proxy.py` and `audit_band_spectra.py` remain because existing regression tests import them. The
former is an unverified King-ratio experiment, not a simulator input; the latter retains Band normalization
diagnostics. Superseded Weibull data remain required by the organizer for historical comparisons.
Failed MULASSIS NaN results are excluded, not treated as zero. Removing these legacy modules or their
tests would be a separate scope decision. `radiation_model.ipynb` is an independent SHIELDOSE/reference
notebook; its saved outputs have been cleared, with original contents archived.

## Mission behavior and strategy development

Defaults: five crew, one astronaut per EVA, one simultaneous EVA, seven-hour repairs, one-hour global
turnaround, crew rotation and no consecutive assignments to the same astronaut. Communications,
monitoring and propulsion each require one completed EVA. Emergency hour zero is storm hour 48;
the mission ceiling is 264 hours, capped by remaining source coverage. Engine default is NTP. NTP/NEP have different repair contexts, but neither label implies different default timing or doses. Optional case constraints enforce repair prerequisites and permissions. Neither mode calculates reactor radiation.

A repair finishes only after its full uninterrupted EVA; aborted attempts make no partial progress.
Return to cabin is instantaneous at abort. Travel, airlock duration, fatigue and medical rest are not
modeled. Crew accumulate exposure inside and outside. Completion stops the run; exposure is never
extrapolated beyond the record. Mission completion does not establish survival or medical safety.

Strategy A receives immutable operational observations, not the true exposure history or future storm.
Its default rule uses a continuous-EVA time cap and optional preset restrictions. The dose-estimate
policy is inactive unless both an independent assumed estimate and explicit experimental BFO threshold
are supplied. Estimated cabin rate defaults to zero; actual cabin exposure does not. No default clinical
abort threshold is assumed. Operational boundaries and fractional-bin integration retain existing behavior.

```bash
.venv/bin/python -B run_strategy_a.py --restriction 3 5
.venv/bin/python -B run_strategy_a.py --estimated-external-rate 200 --abort-threshold 1000
.venv/bin/python -B run_strategy_a.py --scenario SAPPHIRE-1-in-1000 --engine NEP
```

The numeric estimate/threshold example is experimental, not a medical recommendation. Canonical crew
fields distinguish `bfo_initial_absorbed_dose_mGy`, `bfo_absorbed_dose_mGy`,
`bfo_initial_gray_equivalent_mGy_eq` and `bfo_gray_equivalent_mGy_eq`. Legacy attribute aliases refer
only to BFO absorbed dose; they do not convert old tissue-target results.

Future B uses forecasts; C conventional biodosimetry; D multimodal biodosimetry. Those observation
models need explicit errors, availability times, missingness and latency. Perfect future knowledge, if
used, must be labeled an oracle benchmark. Paired strategy experiments must share scenario, timing,
crew, constraints and, when stochastic models exist, random seeds. Compare repair completion, duration,
aborts and individual organ exposure without assuming any strategy wins. Health/biomarker models,
individual symptoms and Monte Carlo simulation remain unimplemented.

## Outputs and repository structure

```text
cnl/
  sim/                       mission engine, records, assumptions and strategies
  charts/                    all reproducible plotting scripts
  data/processed/oltaris/    frozen primary anatomical environment and source tables
  data/processed/            historical observations and frozen SHIELDOSE reference
  data/raw/                  scientific sources, provenance and required rebuild inputs
  outputs/model/             frozen reference manifest, audits and retained reference tables
  outputs/validation/        scientific validation records and cleanup verification
  outputs/analysis/          historical inventories and retained analysis method/provenance
  *.py, *.ipynb              runners, data generators and reference notebook
```

Generated plots and disposable mission results are intentionally absent after cleanup and ignored on
future runs. The anatomical chart can be regenerated with
`.venv/bin/python -B charts/09_anatomical_eva_exposure.py` without rebuilding frozen environments.
Strategy runs create `outputs/strategy_a/` or the chosen output directory. Their ledger keeps absorbed
mGy and Gray Equivalent separate. Repeated existing exporters may create new version backups in
`data/raw/archive/model_output_versions/`; this cleanup does not alter exporter behavior.

Two generated CSVs formerly used as regression fixtures remain as reference outputs: `outputs/model/historical/mission_radiation_environment.csv`
and `outputs/model/synthetic_sapphire_interval_exposure.csv`. Frozen copies, checksums and scientific
audit/provenance files are not covered by broad output-ignore patterns. See `outputs/README.md` for the
output map. The inventories in `outputs/analysis/` predate simplification and test removal; they are historical snapshots.

## Cleanup archive and reproducibility

Historical backups, superseded reports, prior plots and disposable run results were moved to:

`/Users/jack/Documents/cnl_archive/cleanup_2026-11-17_183446`

`moves.json` there records each original path, SHA-256, Git classification, reason and archive path.
Pre-cleanup uncommitted changes, original documentation/notebook, tests, hashes and deterministic mission
states are preserved there. Git-tracked generated removals remain visible as working-tree deletions;
no staging, commits, index edits or Git-history changes were performed. Python bytecode was the only
permanently deleted material. `.venv/` remains installed and ignored.

The cleanup report and verification are under `outputs/validation/repository_cleanup/`. At the cleanup snapshot, scientific-source records, frozen data, code and tests were byte-identical and notebook code cells were unchanged. That cleanup made no simulation changes; the later optional recovery implementation is documented below.

## Qualitative engineering recovery (optional)

Enable the shared `sim/mission_recovery.py` model with `--recovery`:

```bash
.venv/bin/python -B run_strategy_a.py --recovery --engine NTP --output-dir outputs/runs/recovery_ntp
.venv/bin/python -B run_strategy_a.py --recovery --engine NEP --output-dir outputs/runs/recovery_nep
```

This is a small shared rule checker, not a second emergency simulator:
- Confirm reactor shutdown, cooling and shielding before EVA work.
- Restore monitoring before propulsion work; optionally require communications too.
- Respect crew consent and repair qualifications.
- Require completed repairs, crew return and approval before mission continuation.

NTP/NEP define different repair contexts, not invented cooldowns or technology-specific risk scores.
The existing mission configuration owns repair order and timing. There are no added support reserves,
kit budgets, checkout durations or failure schedules. Case facts, engineering context and configurable
assumptions are separated in [docs/mission_recovery.md](docs/mission_recovery.md); source records remain
in `data/raw/mission_recovery/`. The simplified model version is `qualitative_constraints_v2`.

Strategy A uses these rules; B–D remain placeholders. Calls without `recovery_config` retain legacy
behavior. All strategies must share the same constraints. `summary.json` records configuration and status;
the existing `event_log.csv` records decisions and reasons. Holds and continuation approvals are not
predictions of survival, a feasible return trajectory or health effects. Frozen radiation inputs are unchanged.

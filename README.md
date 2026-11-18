# CNL Mars mission simulator

**What this does:** compares mission decisions during repair EVAs while tracking each astronaut's
estimated radiation exposure. Strategy A works; Strategies B–D and Monte Carlo are not implemented yet.

The radiation input is **SAPPHIRE-derived organ-dose estimates distributed using historical solar
particle event timing profiles**. It is not measured astronaut dose or a prediction of health outcomes.

## Start here

**Open the finished figures: [Final-case chart gallery](outputs/final_case/index.html).**
Six PNGs are together in `outputs/final_case/`; you do not need to browse JSON or CSV files to see them.
Recreate the whole gallery with `.venv/bin/python -B charts/build_final_case.py`.

```bash
.venv/bin/python -B -m sim.run_strategy_a --recovery
.venv/bin/python -B -m sim.run_strategy_a --recovery --engine NEP --template october_2003_goes10 --output-dir outputs/runs/nep_goes10
.venv/bin/python -B charts/09_anatomical_eva_exposure.py
```

The first two commands run missions; the third makes the anatomical exposure comparison chart.
Results are written to `outputs/strategy_a/`, your chosen run directory, or `outputs/analysis/anatomical_eva/`.
Without `--recovery`, the mission runs without the optional qualitative case constraints.
For a fresh setup, create a Python 3.12 `.venv` and install `requirements.txt`.

## Files you actually work with

| File | Purpose |
| --- | --- |
| `sim/assumptions.py` | Everyday settings: crew size, EVA length and turnaround. |
| `sim/defaults.py` | Advanced mission and radiation-scenario selections. |
| `sim/strategies.py` | Decision rules; B–D are placeholders. |
| `sim/mission_recovery.py` | Shared repair prerequisites, reactor confirmations, crew permissions and continuation checks. |
| `docs/mission_recovery.md` | Plain-language case constraints and which parts are assumptions. |
| `sim/run_strategy_a.py` | Runs the mission and exports results. |
| `sim/mission_simulator.py`, `sim/models.py` | Mission progression and records; normally leave these alone. |

The existing scheduler assumes five crew, one astronaut outside at a time, seven-hour repairs and
one-hour turnaround. It rotates crew without consecutive assignments. Aborts do not earn partial repair
credit; returning to the cabin is instantaneous. Crew accumulate dose both inside and outside.
Mission hour zero defaults to storm hour 48, with a 264-hour ceiling capped by remaining data coverage.
These are scenario/scheduling assumptions, not validated flight procedures.

## Four useful charts

Run any of these with `.venv/bin/python -B charts/<filename>`:
- `01_spe_proton_flux.py`: the measured 1972 timing profile.
- `03_sapphire_spectra.py`: the 100-year and 1,000-year proton spectra.
- `06_shielding_sensitivity.py`: the independent SHIELDOSE tissue-target shielding reference.
- `09_anatomical_eva_exposure.py`: the primary anatomical EVA dose comparison.

`build_final_case.py` collects these figures, a current mission timeline and the retained spectrum-fit
validation into the gallery. The other Python files in `charts/` are shared plotting helpers.

## Radiation: what the numbers mean

Corrected OLTARIS MAX full-event totals, using the **Band fit**, not the superseded Weibull fit:

| Severity | Aluminium g/cm² | BFO absorbed mGy | BFO Gray Equivalent mGy-Eq |
| --- | ---: | ---: | ---: |
| 100-year | 0.4 | 415.1 | 623.3 |
| 100-year | 20 | 43.14 | 63.99 |
| 1,000-year | 0.4 | 723.7 | 1087.0 |
| 1,000-year | 20 | 75.2 | 111.6 |

- **mGy** is absorbed organ dose, the exposure input for a future biological-response model.
- **mGy-Eq** is kept separately for NASA BFO reference comparisons. It is not mGy or mSv.
- Organ/effective dose equivalents in **mSv** must not be substituted for either quantity.
- The 0.4/20 g/cm² spheres represent EVA/cabin shielding assumptions, not verified spacecraft hardware.
  MAX anatomy is not personalized to each crew member; other shielding depths are unsupported here.
- NASA comparisons use the archived Revision C references (250 mGy-Eq/30 days, 500/year), mission
  contribution only. Prior exposure and matching RBE definitions remain unverified: no compliance claim.

Historical proton flux supplies the peaks and dips; OLTARIS supplies total dose. Weights sum to one
over the complete event, assuming a fixed spectral shape—not time-resolved particle transport.
The 1972 template has 264 hours with eight missing per channel; GOES-10 2003 has 336 complete supplied
hours. The default is >10 MeV/log-linear filling; nine channel/filling alternatives measure sensitivity,
not statistical confidence. In the highlighted 1972 seven-hour window, 35.2% of dose is allocated to
interpolated observations; that is not a dose-error percentage. Overlapping EVA windows are alternatives,
not doses to sum. The sparse 1989 and separate 2003 OMNI2 records are not enabled mission templates.

The corrected spectrum fit differs by about 3.2% or less at original energy nodes, not necessarily in dose.
Corrected user-supplied CSVs are preserved; native corrected OLTARIS solver exports remain pending.
Exact matching of the supplied GOES data to the official archive and physical event closure remain unverified.
The hypothetical mission is near **1.25 AU without distance rescaling**; original source distance labels remain.

## Scientific files: keep, don't manually edit

| Location | Why it stays |
| --- | --- |
| `data/processed/oltaris/` | Readable anatomical summaries plus the frozen hourly environment, manifest and checksums. |
| `data/processed/` | Historical timing tables and the frozen independent SHIELDOSE reference. |
| `data/raw/` | Original scientific exports, case document, engineering references and provenance. |
| `outputs/model/` | Frozen SHIELDOSE manifest and scientific audit records. |
| `outputs/mission_radiation_environment.csv` | Preserved frozen SHIELDOSE presentation copy. |
| `outputs/validation/oltaris_anatomical/` | Spectrum overlay, error tables and anatomical validation evidence. |

SHIELDOSE is an independent idealized tissue-target reference, **not** the simulator's anatomical BFO input.
It uses aluminium spheres, 4π irradiation and proton results without nuclear attenuation; rad × 10 = mGy.
Source duplicates, excluded/failed runs and older fits stay where provenance or reproduction depends on them.
The five source tables in `data/raw/archive/previous_processed/` are required rebuild inputs, not junk.

`anatomical_environment.py` loads and checks frozen data. `radiation_model.py`, `prepare_data.py`,
`organize_oltaris_anatomical.py`, `spenvis_audit.py` and `audit_band_spectra.py` preserve the calculations,
data preparation and scientific checks. They are infrastructure, not files to edit for strategy development.
Do not regenerate frozen environments while developing strategies.

## Boundaries for the final case

All strategies must share the same radiation and physical constraints; only their information and decisions
should differ. Strategy A does not see true/future dose. Its optional dose-estimate abort rule requires explicit
experimental settings; there is no default clinical threshold. NTP/NEP labels do not invent different repair
times. Symptoms, biomarkers, survival, reactor physics and return trajectories are not modeled.

The test suite has been removed at the owner's request. Old experiments, alternate charts, the notebook,
inventories and administrative logs are no longer in the active repo. Recovery copies and cleanup checks
are outside it at `/Users/jack/Documents/cnl_archive/final_case_cleanup_20261117_195447/`;
the removed tests are at `/Users/jack/Documents/cnl_archive/removed_tests_20261117_195041/`.

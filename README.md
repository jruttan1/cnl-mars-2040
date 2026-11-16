# CNL Mars 2040 — synthetic radiation environment

**SAPPHIRE 100-year SPE is the main scenario; the 1,000-year SPE is the extreme stress test.** Both now use the verified November 16 SHIELDOSE-2 exports. No additional physics simulations were run.

## What the dose quantities mean

- **Tissue-target absorbed dose:** energy deposited per unit mass in the idealized tissue target simulated by SHIELDOSE-2.
- **Organ absorbed dose:** energy deposited per unit mass in a modeled human organ; it requires an anatomical or organ-specific transport model.
- **Whole-body exposure:** requires a defined anatomical exposure quantity and cannot be inferred from this simplified tissue-target dose alone.
- **Effective dose equivalent:** a radiation-protection quantity in Sv, distinct from absorbed dose in Gy. It cannot be substituted for tissue or organ absorbed dose.

Clinical reference levels in Chart 07 apply to the stated human exposure conditions. They are not thresholds for automatically labeling these modeled tissue-target doses as safe, fatal or symptom-producing.

## How the sources connect

- **OMNIWeb:** measured August 1972 proton intensity supplies the hourly peaks, dips and decay.
- **SAPPHIRE:** supplies a separate event-integrated energy spectrum for each event severity.
- **SHIELDOSE-2:** supplies absorbed dose in its idealized tissue target behind aluminium for the corresponding SAPPHIRE spectrum.
- **OLTARIS King:** remains an independent historical reference; its doses do not normalize synthetic SAPPHIRE events.

The model calculates `hourly dose = event dose × normalized hourly weight`. Weights sum to one across the **complete assumed 264-hour event**, not only the displayed 72 hours. Dose rate is hourly dose divided by the one-hour bin duration. Integrating the whole modeled event reproduces the supplied transport total.

This is a **synthetic reconstruction using the August 1972 timing template**, not a measured 2040 storm. It assumes a fixed spectrum through time and that the available historical record defines the complete modeled event. The 1972 timestamps identify the template, not a forecast date.

## Verified shielding results

Both runs use tissue at the centre of aluminium spheres, **4π irradiation**, with **no proton nuclear attenuation**. The six depths are mass per area in **g/cm²**, not millimetres. `0.4 g/cm²` is an idealized lightly shielded EVA reference; `20 g/cm²` is an idealized cabin shielding reference. Neither is a verified spacesuit or spacecraft design.

| Aluminium shielding (g/cm²) | Main: 100-year absorbed dose (mGy) | Extreme: 1,000-year absorbed dose (mGy) |
|---:|---:|---:|
| 0.4 | 74,571 | 127,280 |
| 1 | 22,306 | 38,573 |
| 2 | 7,963.5 | 13,862 |
| 5 | 1,664 | 2,903.7 |
| 10 | 476.16 | 830.93 |
| 20 | 134 | 233.83 |

These are **event-integrated tissue-target calculations**, not measured astronaut whole-body doses or direct health predictions. Numerical exports are in rad: **1 rad = 10 mGy; 1 Gy = 1,000 mGy.** Sv/mSv are different radiation-weighted quantities and are not substituted for absorbed dose.

Original reports, numerical exports and source plots are in `data/raw/spenvis/sapphire_100yr/` and `sapphire_1000yr/`. All eight files were moved byte-for-byte from Downloads. [The manifest](data/raw/spenvis/verified_sapphire_manifest.json) records original paths, checksums and your confirmed run pairing. The importer independently checks source frequencies, every spectral row, transport settings, common run timestamps, shielding coordinates, and numerical/report agreement. HTML dose values are rounded; the numerical export's precision is retained.

Older SHIELDOSE tables with ambiguous associations and failed MULASSIS effective-dose outputs remain preserved and excluded from synthetic-dose normalization. Raw data remains hidden only in VS Code Explorer.

## Charts

Run scripts from the project root after `source .venv/bin/activate`:

```bash
python charts/04_radiation_dose_rate.py
python charts/05_cumulative_exposure.py
python charts/06_shielding_sensitivity.py
```

- **04 — Tissue-target dose rate:** all four main/extreme and external/cabin curves on one shared logarithmic dose axis, making the shielding difference visible while retaining the weaker tail.
- **05 — Cumulative tissue-target dose:** modeled tissue-target dose accumulated since the emergency begins. Panels have separate linear scales. The highlighted seven-hour interval is preselected, not optimized; its accumulated tissue-target dose is printed on the plot.
- **06 — Tissue-target shielding sensitivity:** both scenarios at all six actual SHIELDOSE-2 coordinates. It shows full-event totals, with logarithmic axes; connecting lines do not perform interpolation.

Each produces a PNG and research-style `.txt` caption in `outputs/charts/`. Historical King-only figures remain in `outputs/charts/historical/`. Scripts `historical_04` and `historical_05` still reproduce the historical time curves.

Other scripts remain available: 01 historical measured flux; 02 one selected shielding dataset; 03 SAPPHIRE spectrum comparison; 07 separate clinical reference; 08 synthetic hourly proton fluence. Chart 02 defaults to verified SPENVIS rows when selected; `--allow-provisional` explicitly selects older provisional rows.

## Settings and assumptions

Edit `radiation_config.json`:

- `emergency_start_utc`: default August 4, 1972 at 00:00 UTC, template hour 48.
- `emergency_duration_hours`: default 72; an illustrative display window, not a CNL requirement.
- `eva_start_hour`, `eva_duration_hours`: default 0 and 7. Changing these does not search for the lowest-dose interval.
- Environment `shielding_g_cm2`: choose an exact exported depth. All six levels remain in the reusable modeled data.

Eight OMNI hours are missing, including gaps near the peak. Original measurements stay unchanged. The modeled copies use log-linear filling centrally, with linear and PCHIP alternatives; boundary extrapolation is rejected. Combined with the >10, >30 and >60 MeV timing channels, these give nine alternative histories. Shading and CSV bounds describe **timing sensitivity**, not confidence intervals, transport uncertainty or bounds on an unobserved peak. Do not add alternative histories together.

SAPPHIRE fluence is event-integrated, not hourly intensity. Its absolute fluence is not obtained from OMNI measurements. Your stated 1.25 AU setting and the reports' displayed 1.2 AU label are retained separately; exported fluences are unchanged, with factor 1 and no additional physical radial attenuation.

## Data and reproducibility

`data/processed/` contains:

- `spe_hourly.csv`: original historical timing observations.
- `spe_scenarios.csv`: the two separate source spectra and settings.
- `shielding_dose.csv`: 2,764 rows, including 12 newly verified absorbed-dose results; older results retain their own provenance/status.
- `mission_radiation_environment.csv`: 28,512 full-event rows: two scenarios × six shielding levels × nine timing variants × 264 hours. Filter `estimate_type == "central"`, then select one scenario and location/shielding level.

In the mission CSV, `cumulative_dose_mGy` is at the **start** of the hour; `cumulative_end_dose_mGy` is at its **end**. Rates are mGy/h. Metadata explicitly identifies `dose_quantity=absorbed_dose`, `target_type=idealized_tissue`, `target_geometry=centre_of_aluminium_spheres`, `unit=mGy` and `nuclear_attenuation=false`. The existing `geometry=center_of_aluminum_sphere` key is retained as a compatible alias. `unit` describes event/cumulative/interval dose; rate columns use `dose_rate_unit=mGy/h`. Metadata also retains source hashes, target/geometry, attenuation settings, gap flags, temporal method and sensitivity bounds. Full-event doses, configured interval doses, temporal weights and the verification audit are in `outputs/model/`.

```python
from radiation_model import load_baseline, baseline_interval_dose
baseline = load_baseline()  # CSV only; no transport or time-profile rerun
print(baseline_interval_dose("SAPPHIRE-1-in-100", 0.4, 16, 23,
                             baseline=baseline))  # tissue-target mGy
```

All four strategies use this same frozen baseline. Strategy A now runs end to end; B–D remain unimplemented. No optimization, reactor radiation or clinical outcome model is implemented.

```bash
python prepare_data.py                       # reproducible import; no duplicate dose rows
python radiation_model.py                    # regenerate numerical outputs
python -m unittest discover -s tests -v
jupyter lab radiation_model.ipynb
```

For a fresh environment: `python3.12 -m venv .venv`, activate it, then `python -m pip install -r requirements.txt`. The overview notebook supports local Jupyter and Colab with the whole project in Google Drive; set `CNL_PROJECT_ROOT` if automatic discovery is ambiguous. Earlier source files and changed output versions remain preserved in the raw archive.

## Frozen baseline v1.0

Strategies A–D should read the same `mission_radiation_environment.csv`. Its first seven columns are `scenario`, `hour`, `shielding_g_cm2`, `dose_rate_mGy_h`, `cumulative_dose_mGy`, `timing_variant`, and `data_quality`. Choose one scenario, shielding depth and timing variant; never sum alternative variants. The default query selects the central variant.

`hour` starts at the synthetic **storm** beginning. Bins cover [0,264); cumulative dose is at bin start, with `cumulative_end_dose_mGy` supplied for the end. Seven-hour starts can be anywhere from 0 through 257, including fractional starts. The example queries storm hours 16–23; emergency hours 16–23 correspond to storm hours 64–71 under the default display. `data_quality` describes the historical template observation or filled gap; every dose value is modeled.

The 72-hour display covers storm hours 48–120 and resets plotted cumulative dose to zero. Changing the display does not change the full-event baseline. The checksum in `outputs/model/baseline_manifest.json` freezes this artifact: loading detects alterations and regeneration refuses different values. Scientific changes require an explicitly reviewed new version.

### Magnitude review and limits

The large light-shield values are present in the numerical exports: 7,457.1 rad = 74.571 Gy for the main event, and 12,728 rad = 127.28 Gy for the extreme event. At 20 g/cm² the values are 0.134 and 0.23383 Gy. Unit conversion and full-event conservation were checked; values were not rescaled to appear more reasonable.

This is source/numerical consistency, **not independent validation of the radiation transport physics or astronaut risk**. The idealized 4π sphere, absent proton nuclear attenuation, fixed spectrum through time, missing peak observations and assumed 264-hour event closure limit interpretation. Timing envelopes do not bound transport error or unseen peaks. Different OLTARIS events/targets cannot directly validate these absolute doses. See `outputs/model/baseline_validation.md` for the final checks. No anatomical or clinical model is included in the radiation baseline. The separate Strategy A simulator is described below.

## Repository layout and local archives

Start with `outputs/` for the frozen CSV and presentation PNGs. Edit chart scripts in `charts/`; develop strategy code in `sim/mission_simulator.py`. The original radiation model and source data remain in their existing paths.

Git excludes the local virtual environment, caches, old backup snapshots and two large reproducible intermediate tables. The five archived CSV inputs required by `prepare_data.py` remain included, along with source reports, tests and the frozen baseline. No original data was deleted. Historical backup hashes are checked when those local files exist; a clean checkout does not require unused backups. The baseline manifest records the files as reviewed at freeze time; later organization/documentation changes do not change its frozen CSV checksum.

Generated figure-caption `.txt` files have been removed; running chart scripts can recreate them, and Git ignores them. Raw numerical `.txt` exports and `requirements.txt` are required project files and are retained.

## Run Strategy A

```bash
source .venv/bin/activate
python run_strategy_a.py
python -m unittest discover -s tests -v
```

The demonstration completes communications, monitoring and propulsion repairs at mission hours 7, 15 and 23. Three of the five sample crew members each perform one seven-hour EVA, separated by a one-hour global turnaround. Mission hour 0 corresponds to **storm hour 48**. The default uses `SAPPHIRE-1-in-100`, central timing `gt10MeV__log_linear`, 0.4 g/cm² outside and 20 g/cm² inside. All crew accumulate cabin exposure whenever they are not on an EVA. Outputs are:

- `outputs/strategy_a/summary.json`: configuration, crew doses/times, attempts and repair outcomes.
- `outputs/strategy_a/event_log.csv`: every start, continuation, delay, abort, completion and termination reason.
- `outputs/charts/09_strategy_a_mission_timeline.png`: EVA intervals and time inside, with aborted attempts distinguished.

### Operational assumptions, not case-established procedures

One astronaut performs each EVA; any sample astronaut can attempt any repair. Repairs succeed only after seven uninterrupted hours. Aborted attempts make no partial progress. Return to the cabin is instantaneous at the abort boundary; travel, airlock time and fatigue are not modeled. The configurable turnaround applies after every attempt, including aborts. The available crew member with the fewest previous attempts is assigned first, with input order breaking ties; true dose is never used for assignment.

The default fallback is a **seven-hour continuous-EVA time cap** and optional preset operational restriction intervals. This bounds an attempt but is not a validated radiation-safety rule. With no reliable dose estimate available, the experimental 1,000 mGy abort parameter is inactive. Strategy A never sees exact accumulated modeled dose, the CSV, or future radiation. It receives an immutable operational observation containing availability, repair status, elapsed EVA time and an optional imperfect estimate.

To exercise the experimental dose-estimate policy, supply a fixed assumed external estimate rate. This rate is deliberately independent of the true radiation CSV; it is not a calibrated sensor or forecast. Its cumulative estimate is checked at each decision boundary and can cross the threshold within a time step. Cabin estimates default to zero (an assumption, not zero actual cabin dose). Crew whose estimate reaches the threshold cannot launch again; it does not reset after an abort. No threshold is a NASA limit, medical diagnosis or claim of safety.

```bash
python run_strategy_a.py --restriction 3 5
python run_strategy_a.py --estimated-external-rate 200 --abort-threshold 1000
python run_strategy_a.py --scenario SAPPHIRE-1-in-1000 --engine NEP
```

These rerun the same output paths. The first example aborts the initial attempt at hour 3, keeps that repair outstanding and retries when the restriction ends. `--eva-time-cap`, `--turnaround`, `--max-hours`, `--time-step` and `--storm-start` control other assumptions. Smaller steps are supported and exposure uses exact fractional-bin integration. Operational boundaries split steps; radiation peaks do not drive decisions. At an exact completion boundary, an active restriction or exceeded optional estimate takes precedence over repair success.

Repair priorities are `repair_order_ntp` and `repair_order_nep` in `sim/defaults.py`; both inherit `required_repair_types` (communications, monitoring, propulsion) because no distinct engineering priorities are established here. Pass an explicit repair sequence to `simulate_mission()` to override them. No repair deadlines are assumed. Crew `available_from` times can delay assignment.

Runs terminate when repairs finish, the configured emergency duration is reached, or the radiation record ends. An in-progress attempt at the terminal boundary is aborted unless it has completed its full seven hours and no abort rule applies. No exposure extrapolation is permitted. Inputs are copied so repeated runs start fresh. A repair-completed status is not proof of mission survival or medical safety; all reported mGy remain **idealized tissue-target absorbed dose**.

Code responsibilities: `sim/models.py` holds shared records and restricted observations; `sim/strategies.py` holds Strategy A and B–D stubs; `sim/mission_simulator.py` handles progression and hidden exposure; `run_strategy_a.py` runs and presents the demonstration. The original frozen radiation files and their calculations are unchanged.

## Centralized mission assumptions

Edit the four everyday settings in `sim/assumptions.py`: crew size, astronauts per EVA, EVA duration and turnaround. Advanced defaults live in `sim/defaults.py` and are inherited automatically; you normally do not need to edit them. The runner passes one shared object through the mission. `MissionConfig` remains a compatibility alias, not a separate configuration. Explicit crew/scenario/repair arguments to `simulate_mission()` override automatic construction; otherwise everything comes from this object.

| Parameter | Default | Basis |
|---|---|---|
| Crew size | 5 | Team assumption |
| Astronauts per EVA | 1 | Team assumption |
| EVA duration | 7 h | CNL specifies approximately seven hours; exact duration is the modeled value |
| Minimum EVA turnaround | 1 h | Team assumption; return/deploy, with next astronaut preparing during the previous EVA |
| Maximum simultaneous EVAs | 1 | Team assumption |
| Crew rotation | Enabled | Team assumption; fewest prior attempts first |
| Consecutive assignments to the same astronaut | Disabled | Team assumption; explicitly enable to permit repeat assignments |
| Required repairs | Communications, monitoring, propulsion | Categories based on CNL damage description; one successful EVA per category is a team simplification |
| Main / worst SPE | SAPPHIRE 100-year / 1,000-year | Team modeling choices from available scenarios |
| External / cabin shielding | 0.4 / 20 g/cm² aluminium | Selected idealized radiation-model references, not verified hardware |
| Simulation time step | 1 h | Team modeling choice |
| Maximum duration | 264 h | Available full radiation timeline |
| Emergency start / timing member | Storm hour 48 / `gt10MeV__log_linear` | Team-selected window and existing central temporal reconstruction |
| Engine | NTP | Team demonstration choice; NEP configurable |
| Continuous EVA cap | Follows configured EVA duration | Team operational fallback; independently configurable |
| Experimental abort budget | 1,000 mGy | Hypothetical tissue-target budget, not a NASA or medical limit |
| External dose estimate | Unavailable | Team assumption; experimental budget inactive without an estimate |
| Cabin estimate rate | 0 mGy/h | Optional estimate assumption only; actual modeled cabin dose still accumulates |
| Preset restrictions | None | Team-configurable operational intervals |
| Engine-specific repair priorities | Inherit required repair order | No distinct engineering priorities imposed |

Turnaround is the global return/deployment gap, separate from `Astronaut.available_from`. The approved consecutive-EVA restriction stays enabled; `allow_consecutive_evas=True` explicitly permits repeat assignments. No medical rest period is modeled. Only single-person, sequential EVAs are supported.

The 264-hour duration is a ceiling. Starting at storm hour 48 leaves 216 hours of data; no extrapolation occurs.

```python
from sim.assumptions import MissionAssumptions
from sim.mission_simulator import simulate_mission
from sim.strategies import strategy_a

config = MissionAssumptions(crew_size=5, turnaround_hours=0)
result = simulate_mission(strategy_a, config=config)
```


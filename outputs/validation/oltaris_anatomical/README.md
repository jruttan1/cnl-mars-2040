# Corrected OLTARIS anatomical results and spectrum validation

## Recommendation

The new files specify **Band**, not Weibull. Keep the old Weibull run as superseded history.
The corrected Band inputs are adequate as a close numerical approximation over the supplied
0.1–1000 MeV grid: maximum absolute integral-fluence error is below 3.2% for both events.
This is a descriptive fit assessment, not a NASA acceptance criterion or validation of organ doses.
The prior Weibull was substantially less accurate and should not be used as the current fit.

Before quantitative mission use, resolve the source report’s **1.2 AU** versus run label **1 AU**
(the supplied notes also mention no correction to 1.25 AU). No distance scaling is applied here.
Obtain original corrected OLTARIS exports/input records to independently verify the four reruns.

## Dose semantics and provenance

- Raw attachments are copied byte-for-byte; SHA-256 hashes and original paths are in provenance.json.
- Four runs and 112 organ records are retained. Corrected data are user-supplied summaries, not raw solver exports.
- Absorbed dose (mGy), dose equivalent (mSv), and Gray Equivalent (mGy-Eq) stay separate.
- Effective dose equivalent is a whole-body weighted quantity, not an organ absorbed dose.
- Missing Gray Equivalent entries remain empty, not zero. Reported Bone zeros are retained, not reinterpreted.
- CNS absorbed dose is retained in mGy as supplied; its cGy-to-mGy conversion is claimed by the supplied source field, not repeated.
- Point absorbed dose is not BFO or whole-body dose. Results are event totals, not daily/yearly rates.
- Spherical aluminium is a surrogate, not verified suit/cabin geometry. Settings and job IDs come from the attachments.
- The old effective-dose export is entirely mSv; its BFO value is 588.90587 mSv.
  Old BFO 474.4 mGy and 713.1 mGy-Eq come only from the earlier user project summary.
  Old summary 603.2 mSv agrees with the exported 603.1618 mSv at displayed precision.
- The old .dat files are depth lookup databases, not organ tables; they are archived without relabeling or conversion.

## Corrected anatomical summary

| Return period (yr) | Al (g/cm²) | BFO absorbed (mGy) | BFO equivalent (mSv) | BFO Gray Equivalent (mGy-Eq) | Effective equivalent (mSv) |
|---:|---:|---:|---:|---:|---:|
| 100 | 0.4 | 415.1 | 533.6 | 623.3 | 490 |
| 100 | 20 | 43.14 | 57.35 | 63.99 | 89.23 |
| 1000 | 0.4 | 723.7 | 929.6 | 1087 | 854.4 |
| 1000 | 20 | 75.2 | 99.86 | 111.6 | 155.2 |

## Validation method

The two original HTML source reports are parsed directly; all 81 native energies per event
are cross-checked against data/processed/spe_scenarios.csv. Spacecraft and model integral
columns are identical. No interpolation, refitting, transport or dose scaling is performed.
Signed error = 100 × (analytic integral / original integral − 1). Metrics weight each native node equally;
they are not dose-response weighted. Fluence agreement does not bound dose error.

Band convention: E in MeV, m = 938.2720813 MeV, r = sqrt(E(E+2m))/1000 (GV),
r0 = supplied R0_MV/1000, rb = (gamma2−gamma1)r0.
Below rb: F = J0 r^(−gamma1) exp(−r/r0). Above rb:
F = J0 rb^(gamma2−gamma1) exp(gamma1−gamma2) r^(−gamma2).
Parameters are read from the corrected summary, without another normalization correction.
The existing outputs/model/band_validation audit documents the earlier MV/GV mismatch and export checks.
That audit’s transport exports are not evidence that these corrected reruns were independently checked.
Previous Weibull comparison uses F = 1.110e12 exp(−2.25498 E^0.27765), never the swapped exponent convention.

## Integral-fluence errors at exact source energies

| Energy (MeV) | Corrected 100-year (%) | Corrected 1,000-year (%) | Old 100-year Weibull (%) |
|---:|---:|---:|---:|
| 0.1 | +3.172 | +2.643 | +37.013 |
| 1 | -1.781 | -1.515 | -4.502 |
| 5 | -0.068 | -0.198 | -23.846 |
| 10 | +1.610 | +1.343 | -25.902 |
| 20 | +3.146 | +2.909 | -20.431 |
| 32 | +2.620 | +2.603 | -9.363 |
| 50 | -1.828 | -1.649 | +9.269 |
| 63 | -2.371 | -2.200 | +21.674 |
| 100 | -1.965 | -1.858 | +41.798 |
| 200 | -1.013 | -0.970 | +45.563 |
| 500 | +0.343 | +0.293 | +0.170 |
| 1000 | +1.484 | +1.378 | -45.551 |

Full native-grid errors: spectrum_percentage_errors.csv; band-specific metrics: spectrum_metrics.csv.
Overlay: spectrum_overlay.png. No conclusions are drawn outside 0.1–1000 MeV.

## Reproduction and isolation

Run `.venv/bin/python organize_oltaris_anatomical.py` after initial archival.
Run `.venv/bin/python -m unittest discover -s tests -p test_oltaris_anatomical.py` for checks.
Only standalone anatomical datasets and validation outputs are written. The frozen baseline,
mission configuration and strategy code are neither imported nor modified. No simulation is run.

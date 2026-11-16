# Baseline v1.0 review — 16 November 2026

## Scope

Source verification, numerical conservation and a bounded physical-plausibility review of the existing synthetic model. This is not independent transport validation or validation for astronaut health predictions. No transport simulation or underlying dose/timing calculation was changed.

## Evidence and checks

- Both SAPPHIRE return periods have matching source reports and six SHIELDOSE-2 tissue-target outputs. Source spectra, transport settings, numerical exports and rounded HTML values agree. Run pairing and event-integrated interpretation also rely on the user's explicit confirmation; transport reports do not embed an input-spectrum hash.
- All 12 rad values convert to mGy by multiplication by 10. No additional seconds-per-hour, 4π, event-duration or radial multiplier is applied to event dose. No OLTARIS total or fluence-only severity ratio normalizes these scenarios.
- 264 contiguous UTC one-hour template bins, beginning 1972-08-02 00:00. Eight missing observations per channel remain missing in observations and are flagged in the modeled copies. Central log-linear filling and alternative linear/PCHIP filling are preserved; no zero filling or boundary extrapolation.
- 108 complete histories: two scenarios × six shielding levels × nine timing variants. Every history has weights summing to one and reproduces its source total. Maximum full-event conservation error: 2.91e-11 mGy (floating-point roundoff).
- Cumulative dose never decreases. All 258 integer seven-hour starts were checked for all 108 histories (27,864 interval queries), plus fractional starts. Interval dose equals summed hourly dose and cumulative-dose differences. Invalid selections and intervals outside the record are rejected.
- Storm hours 16–23 at 0.4 g/cm², main scenario, central timing: **3.8272391527 mGy**. Emergency hours 16–23 instead mean storm hours 64–71 with the default configuration.
- Moving the display start from August 4 to August 5 leaves the full-event baseline identical. The default 72-hour display is storm hours [48,120); plotted cumulative dose resets at display start.
- The pre-review and final full-event numerical tables are identical. All 204 pre-existing raw/archive file hashes remain unchanged; source observations, spectra and transport values are preserved.
- All eight main chart scripts and both historical chart scripts executed successfully. PNGs decoded successfully and all eight main figures were visually inspected. The notebook executed sequentially. Chart 07 retains separate clinical references with no tissue-target dose overlay or clinical classification.

The final test suite passed all 19 tests (`python -m unittest discover -s tests -v`).

## Absolute magnitudes and physical limits

At 0.4 g/cm² the main event is 7,457.1 rad = 74.571 Gy = 74,571 mGy; the extreme event is 12,728 rad = 127.28 Gy = 127,280 mGy. At 20 g/cm² they are 0.134 and 0.23383 Gy. These high values are in the source exports, not a unit-conversion or time-normalization error.

Dose decreases at every sampled shielding depth for each scenario. The 0.4-to-20 g/cm² dose ratios are 556.5 and 544.33. Extreme-to-main dose ratios are approximately 1.71–1.75 across the six depths. Source fluence above 10 MeV is approximately 2.087e10 and 3.537e10 protons/cm². High fluence and light shielding are qualitatively consistent with large target doses; this does not establish that their absolute magnitude is an accurate astronaut prediction.

SHIELDOSE-2 models tissue at the centre of aluminium spheres with 4π irradiation and no proton nuclear attenuation. The omitted physics and idealized geometry have unquantified effects here; no error magnitude or sign is assumed. These are not verified suit/cabin constructions, anatomical organ doses, whole-body astronaut doses or effective dose equivalents. Clinical reference levels cannot classify these outputs as safe, fatal or symptom-producing.

Time reconstruction assumes a fixed spectrum/response through time and closes the event at the end of the available 264-hour record. The historical spectrum is not assumed identical to SAPPHIRE. Missing observations near peaks and alternate energy-channel timing affect when dose is assigned. Timing envelopes are neither confidence intervals nor physical bounds on transport errors or unseen peaks. Alternative histories must not be summed together.

The exported fluence uses radial factor 1; the report displays 1.2 AU and the user reports 1.25 AU. No additional physically specific radial attenuation is calculated. OLTARIS King results have a different event and target/geometry and cannot independently validate these SAPPHIRE absolute doses by direct comparison.

## Strategy-facing artifact

`data/processed/mission_radiation_environment.csv` contains 28,512 rows. Hours are storm-relative bin starts; cumulative dose is at bin start and `cumulative_end_dose_mGy` gives bin-end dose. `data_quality` describes the historical template only: all doses are modeled. Provenance, units, geometry, scenario and timing metadata accompany each row.

`load_baseline()` and `baseline_interval_dose()` use this CSV without regenerating the model. The checksum manifest freezes v1.0 and rejects changed numerical exports. Future scientific changes require an explicitly reviewed baseline version; all four strategies should consume this same artifact.

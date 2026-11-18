# Anatomical EVA absorbed-dose comparison

This chart uses the common simulator environment: a synthetic time allocation of the corrected OLTARIS MAX **BFO absorbed dose**,
not the historical point/tissue absorbed dose and not the old King-ratio BFO proxy.
The 0.4 g/cm² aluminium sphere is an EVA shielding surrogate, not a validated spacesuit.
The 100-year and 1,000-year event totals are 415.1 and 723.7 mGy respectively.
No mSv or Gray Equivalent values are used in these calculations.

## Method and chart

For each complete historical record, the nonnegative timing weights sum to one.
Multiply those weights by the anatomical event-total dose; divide by bin duration for mGy/h.
The 1972 record has 264 hours and the 2003 GOES-10 record has 336 hours. They are normalized
separately, not renormalized to the EVA or a 72-hour display window. Physical event closure is unverified.
Historical proton measurements supply the relative peaks and dips, not measured astronaut dose.
The x axes use historical elapsed hours; timestamps are template dates, not a future forecast.

- Top: instantaneous modeled BFO rate under continuous EVA-reference shielding; log axis exposes dips.
- Middle: integrated dose for a seven-hour EVA starting at each valid hourly start. These overlapping
  windows are alternatives, not separate doses to add together.
- Bottom: cumulative additional BFO dose from zero during an example seven-hour EVA. The start is
  selected retrospectively at the largest central seven-hour dose, separately for each template.
  It is not a proposed EVA schedule or strategy optimization. Both return periods use the same start.
  Accumulation cannot dip; only its slope changes. No pre-EVA dose or post-EVA cabin dose is included.

The center uses >10 MeV/log-linear gap filling. Bands span >10, >30, >60 MeV and three existing
gap-fill choices, using each complete member history before taking bounds. They represent timing
sensitivity only, not confidence intervals or full dose uncertainty. Filled historical gaps retain flags
in hourly_bfo_profiles.csv and are hatched on the rate and example accumulation panels.
interpolation_sensitivity.csv compares all nine alternatives at the SAME central peak-window start.
The 35.2% 1972 filled-bin contribution is an allocation fraction, not an error estimate.
Counts/source hashes are in provenance.json.

## Interpretation limits

A fixed spectral shape through time is assumed: an event-integrated anatomical response is distributed
according to a proton-channel timing proxy. This is not time-resolved transport and does not account for
spectral hardening/softening, individual anatomy, attitude, realistic shielding, or dosimeter readings.
The inputs are user-supplied corrected summaries, not independently verified corrected solver exports.
Reference spectra are applied to a hypothetical mission near 1.25 AU without distance adjustment.
Source spectra report 1.2 AU; runs are labeled 1 AU.
The two synthetic severities differ only by their anatomical total within a given timing template.
These are not independent simulated time histories or predictions of event occurrence.

The result is an accumulated **modeled organ exposure**, not a health-effect model, medical threshold
assessment, or validated operational astronaut dose tracker. Further validated dosimetry and an explicit
health-response framework would be needed to translate exposure into effects.

## Reproduce

`.venv/bin/python charts/09_anatomical_eva_exposure.py`

Only outputs/analysis/anatomical_eva is written. Frozen baseline files, radiation_config.json, existing
SHIELDOSE reference charts and strategy logic remain unchanged. No transport simulation is rerun.

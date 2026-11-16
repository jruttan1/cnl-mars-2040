# OMNIWeb August 1972: measured hourly proton flux

Validated 2026-11-12. The two downloads were found with added `.txt` suffixes. Originals remain in CNL; byte-identical copies are in `originals/`. SHA-256 hashes and detailed gap times are in `validation.json`.

## What the data contain
264 consecutive hourly records, August 2 00:00 through August 12 23:00 UTC, 1972 (leap-year days 215–225). The final bin ends August 13 00:00. No duplicate or absent timestamp rows. All three selected quantities really are integral proton flux above 10, 30 and 60 MeV, not solar-wind density. NASA identifies IMP-5 SPME as the source for this period.

The format file defines six fields: year (I4), day of year (I4), hour (I3), and three fluxes (F9.2). NASA's documentation supplies the units cm^-2 s^-1 sr^-1 and missing code 99999.99, which the format file does not include. Each hour denotes the beginning of an hourly average, not an instantaneous measurement. The thresholds overlap: do not add the three channels.

## Outputs and columns
`hourly_measured_proton_flux.csv`: UTC bin start/end; original year/day/hour; hours since reference start; three measured flux channels; missing-channel labels (MeV thresholds); and threshold-order inversion flag (1 means >10 < >30 or >30 < >60). Empty flux cells mean missing, never zero. `measured_proton_flux_hours.png` plots the measurements with logarithmic flux and hours on the horizontal axis. The chosen hour zero is August 2 00:00 UTC, matching the requested window; it is not a measured physical event onset. Rebase hours only after adopting an explicit onset definition.

## Validation and uncertainties
Each channel has 256 valid values and 8 missing values. Missing UTC hour starts:
- 1972-08-04T17:00:00+00:00
- 1972-08-04T18:00:00+00:00
- 1972-08-04T20:00:00+00:00
- 1972-08-07T13:00:00+00:00
- 1972-08-08T02:00:00+00:00
- 1972-08-08T03:00:00+00:00
- 1972-08-11T10:00:00+00:00
- 1972-08-11T11:00:00+00:00

Measured maxima (not missing-value codes):
- >10 MeV: 67,750.00 at 1972-08-04T21:00:00+00:00 (hour 69)
- >30 MeV: 19,745.22 at 1972-08-04T21:00:00+00:00 (hour 69)
- >60 MeV: 6,257.96 at 1972-08-04T14:00:00+00:00 (hour 62)

Five valid rows violate the ideal ordering of integral energy thresholds. They are retained and flagged; no channel differences, clipping, smoothing, background subtraction or interpolation were applied. NASA cautions that these historical values are unreliable as absolute quiet-time galactic fluxes but useful for solar/shock particles. No per-hour statistical errors, calibration uncertainties, directional distribution or quality flags were included in this download. No numerical uncertainty band is justified. Hourly averaging hides shorter spikes. A near-Earth measurement is not automatically the environment at an EVA location. The window ends above its initial >10 MeV level, so full-event coverage is not established.

## Relation to OLTARIS King / 0.4 g/cm²
The neighboring `OLTARIS_Aug1972_King_Al0p4_gcm2` export reports Effective Dose Equivalent 1238.012 mSv. This is an event-integrated effective-dose-equivalent quantity, not absorbed dose in mGy. Its configuration association is user-supplied, as documented in that folder. Keep organ, depth-dependent absorbed-dose and dose-equivalent quantities separate.

For a first-pass allocation after agreeing the event window and gap treatment, choose ONE measured channel F_i as a temporal proxy. With bin width Δt_i in hours, define A = sum(F_i Δt_i), w_i = F_i Δt_i / A, allocated bin quantity Q_i = Q_total w_i, and allocated rate Q_i/Δt_i. Apply separately to the chosen OLTARIS total and preserve its units. For one-hour bins the rate is Q_total F_i / sum(F_j × 1 hour). Integrating a seven-hour EVA uses bin overlaps, not seven samples plus both endpoints.

This assumes a fixed dose response and spectral shape through time. Actual spectral hardening/softening changes shielding penetration, secondary production and organ response. The three overlapping integral channels do not determine a unique differential spectrum, especially the >60 MeV tail; choosing a different channel gives a sensitivity scenario, not a statistical uncertainty interval. A King event spectrum and this measured window need not have matching fluence or duration.

No hourly astronaut dose series was generated: gaps and unconfirmed event boundaries would make full-total normalization misleading. Normalizing only the 256 measured bins would allocate the entire event total to an incomplete observation set. Required next inputs: a justified event integration window with adequate pre/post coverage; recovery or explicit scenario treatment of the eight missing hours; time-resolved differential proton spectra (or defensible spectral assumptions including the high-energy tail), angular assumptions and the matching shielding/organ dose-response calculation. The measurements are sufficient for the plotted proton flux, but insufficient for measured astronaut dose rates.

## Source
NASA OMNIWeb Data Documentation, sections 3 and 7, accessed 2026-11-12: https://omniweb.gsfc.nasa.gov/html/ow_data.html
Original download references: https://omniweb.gsfc.nasa.gov/staging/omni2_5AkMqBOXbn.lst and https://omniweb.gsfc.nasa.gov/staging/omni2_5AkMqBOXbn.fmt (staging links may expire). Local files are authoritative for this extraction.

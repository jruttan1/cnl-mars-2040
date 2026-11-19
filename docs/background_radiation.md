# Background galactic cosmic radiation

The mission engine now adds constant GCR exposure during cabin time, EVA work, and return travel.
All strategies and both engines share the same physical background. This does not alter the frozen
SAPPHIRE spectra, full-event totals, or historical SPE timing files.

## Reference and numerical choices

Source: Cucinotta, Kim and Chappell, **NASA/TP-2011-216155**, July 2011,
[Table 2.7(a,b), printed pages 30–31](https://ntrs.nasa.gov/api/citations/20130001648/downloads/20130001648.pdf).
Original PDF, selected values and SHA-256 are archived in `data/reference/gcr/`.
The published calculations are male organ doses in aluminium spheres at solar minimum.

| Channel | Published shielding | BFO mGy/day | BFO mGy-Eq/day | Skin mGy-Eq/day | Lens mGy-Eq/day |
|---|---:|---:|---:|---:|---:|
| EVA proxy | 5 g/cm² | 0.5088 | 0.9238 | 1.0296 | 1.0203 |
| Cabin | 20 g/cm² | 0.4986 | 0.8627 | 0.9378 | 0.9271 |

Code retains the annual values and divides by 365 × 24 for hourly integration. Absorbed dose and
Gray Equivalent use separate published columns; no mSv conversion is made.

**The EVA value is a proxy, not a calculation for a 0.4 g/cm² suit.** The source's lightest tabulated
shield is 5 g/cm². We use that value to represent light shielding for this small background addition,
while retaining the separate 0.4 g/cm² SPE transport. This may understate EVA GCR, and is not a
conservative upper bound. A matched OLTARIS GCR run is needed to remove this approximation.
Likewise, this male reference is not personalized anatomy or a validated 2040/1.25-AU prediction.
Solar minimum is a reference condition, not a prediction of the solar cycle or an event probability.
The chosen source predates more recent GCR models; results should be treated as scenario inputs.

## Integration and interpretation

- Every crew member accumulates background continuously, including while waiting or sheltered.
- Physical histories record SPE and GCR contributions separately. Reported organ totals add each
  organ's own GCR rate; they never multiply GCR BFO by SPE skin/lens ratios.
- B/C/D forecasts include a constant, independently configured background. SPE forecast magnitude
  and arrival-time perturbations do not change GCR. Equal true/forecast background is a stated
  nominal-information assumption, not access to hidden future SPE data.
- Biological signals currently use total absorbed BFO history with the existing exploratory response
  kernels. This assumes equal signal per absorbed mGy across the modeled fields; it is not a validated
  GCR heavy-ion biomarker calibration. Gray Equivalent is not fed into the biomarker likelihood.
- Exposure before emergency hour zero is still excluded. These totals do not establish whole-mission
  exposure, remaining annual allowance, or clinical safety. Reactor dose remains excluded.
- Existing saved runs and SPE background-slide figures are not regenerated or relabelled as totals.

The comparison and Strategy A runners accept `--gcr-scale`. The default is 1; 0 reproduces SPE-only
physics. Other nonnegative values are sensitivity multipliers, not published confidence bounds.
In the comparison runner the selected scale applies to all strategies and their nominal forecasts.
A simple robustness check is 0, 0.5, 1, and 1.5; this is an analyst-selected sweep, not a probability model.
Python callers can set `Scenario.gcr_scale` / mission defaults and independently set
`ForecastSpec.gcr_scale` to study background estimation error.

The 20 g/cm² cabin reference adds about 1.50 mGy absorbed or 2.59 mGy-Eq BFO over 72 hours.
Thus it matters to honest dose accounting even if the larger SPE dose still drives many decisions.

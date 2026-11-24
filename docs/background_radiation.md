# Background galactic cosmic radiation

The mission engine adds a constant GCR dose during cabin time, EVA work and return travel. Every strategy and
both engines share the same background. It does not change the frozen SAPPHIRE spectra, the full-event totals or
the historical SPE timing files.

## Reference values

Source: Cucinotta, Kim and Chappell, NASA/TP-2011-216155, July 2011,
[Table 2.7(a,b), printed pages 30 and 31](https://ntrs.nasa.gov/api/citations/20130001648/downloads/20130001648.pdf).
The original PDF, the selected values and their SHA-256 are archived in `data/reference/gcr/`. The published
numbers are male organ doses in aluminium spheres at solar minimum.

| Channel | Published shielding | BFO mGy/day | BFO mGy-Eq/day | Skin mGy-Eq/day | Lens mGy-Eq/day |
|---|---:|---:|---:|---:|---:|
| EVA proxy | 5 g/cm² | 0.5088 | 0.9238 | 1.0296 | 1.0203 |
| Cabin | 20 g/cm² | 0.4986 | 0.8627 | 0.9378 | 0.9271 |

The code keeps the annual values and divides by 365 × 24 for hourly integration. Absorbed dose and Gray
Equivalent come from separate published columns, and no mSv conversion is made.

The EVA value is a proxy and not a calculation for a 0.4 g/cm² suit. The lightest shield in the source is
5 g/cm², so we use it for light shielding in this small background term and keep the 0.4 g/cm² SPE transport
separate. That may understate EVA GCR and is not a conservative bound. A matched OLTARIS GCR run would remove the
approximation. The male reference is not personalized anatomy or a validated 2040 prediction at 1.25 AU. Solar
minimum is a reference condition and not a forecast of the solar cycle. The source predates newer GCR models, so
treat the results as scenario inputs.

## How it is used

- Every crew member accumulates background continuously, including while waiting or sheltered.
- Physical histories record SPE and GCR separately. Reported organ totals add each organ's own GCR rate, and GCR
  BFO is never scaled by SPE skin or lens ratios.
- B, C and D forecasts include a constant background, set independently. Forecast magnitude and timing
  perturbations do not change GCR. Equal true and forecast background is a nominal-information assumption and does
  not give any strategy hidden knowledge of the SPE.
- Biological signals use total absorbed BFO history with the exploratory response kernels. That assumes equal
  signal per absorbed mGy across all the modeled fields, and it is not a validated heavy-ion biomarker
  calibration. Gray Equivalent never enters the biomarker likelihood.
- Exposure before emergency hour 0 is still excluded. The totals do not establish whole-mission exposure, the
  remaining annual allowance or clinical safety, and reactor dose stays excluded.
- Saved earlier runs and the SPE background figures were not regenerated as totals.

The comparison and Strategy A runners accept `--gcr-scale`. The default is 1, and 0 gives SPE-only physics. Other
nonnegative values are sensitivity multipliers and not published confidence bounds. In the comparison runner the
scale applies to every strategy and its nominal forecast. A simple robustness check is 0, 0.5, 1 and 1.5, which is
an analyst-chosen sweep and not a probability model. Python callers can set `Scenario.gcr_scale` and
`ForecastSpec.gcr_scale` separately to study errors in the background estimate.

The 20 g/cm² cabin reference adds about 1.50 mGy absorbed, or 2.59 mGy-Eq of BFO, over 72 hours. That is small
next to a large SPE dose, but it still belongs in honest dose accounting.

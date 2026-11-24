# CNL Mars 2040: SAPPHIRE 1-in-100-year event

Start here: this folder contains a solar-proton event source, a simplified aluminium shielding calculation, and an unsuccessful effective-dose calculation. Folder labels are confirmed by the solar-fluence report; downstream dose association still needs checking.

## Files

| File | What it contains | Original name |
|---|---|---|
| [solar-proton-fluence-report.pdf](solar-proton-fluence-report.pdf) | SAPPHIRE 1-in-100-year source spectrum, numerical tables and exposure settings. | `Solar particle fluences.pdf` |
| [solar-proton-fluence-log-energy.png](solar-proton-fluence-log-energy.png) | Integral and differential fluence chart; logarithmic energy axis. | `fluxs_spec.png` |
| [solar-proton-fluence-linear-energy.png](solar-proton-fluence-linear-energy.png) | Same spectrum with a linear energy axis; fluence axes remain logarithmic. | `fluxs_spec-linear.png` |
| [mulassis-effective-dose-report.html](mulassis-effective-dose-report.html) | Short effective-dose report; dose and error are NaN. | `Mulassis-report-file` |
| [mulassis-effective-dose-output.txt](mulassis-effective-dose-output.txt) | Original structured text output: layers, shield mass per area, dose and error. | `Mulassis-output-file` |
| [shieldose2-tissue-dose-report.html](shieldose2-tissue-dose-report.html) | 25-row aluminium shielding table, tissue dose in rad, model assumptions. | `radiation-shielding-absorption` |
| [shieldose2-tissue-dose-output.txt](shieldose2-tissue-dose-output.txt) | Original numerical thickness-versus-dose data, plus mission metadata. | `shieldose-output` |
| [shieldose2-tissue-dose-vs-aluminium.png](shieldose2-tissue-dose-vs-aluminium.png) | Dose-versus-thickness chart; linear thickness and logarithmic dose axis. | `radiation-absorption-cart` |

## Solar-proton source: key findings

Source: `solar-proton-fluence-report.pdf`, integral and differential proton spectra table. Energy grid spans **0.10 to 1000 MeV**.

| Energy threshold | Integral fluence above threshold (protons/cm²) |
|---|---|
| 0.10 MeV | 2.465E+11 |
| 1 MeV | 1.219E+11 |
| 10 MeV | 2.087E+10 |
| 100 MeV | 2.378E+08 |
| 1000 MeV | 4.397E+05 |

The spectrum contains many more low-energy than high-energy protons. The log-energy chart makes the low-energy range easier to inspect; the linear-energy chart spreads out the high-energy range. Dotted curve: integral fluence, left axis. Solid curve: differential fluence, right axis.

## What the numbers mean

- `2.087E+10` means 20,870,000,000. MeV is particle energy, not absorbed dose.
- Integral fluence (protons/cm²) counts protons above a stated energy. Differential fluence (protons/cm²/MeV) describes the spectrum per energy interval. These are event totals, not particles per second. Do not add integral rows together.
- Both source reports say no magnetic shielding, model fluence at **1.2 AU**, and exposure factors **1.0000**. Mission total and segment exposure are **72 hours**; a separate orbit-exposure column says **8 hours**. Confirm what that orbit setting represents before using it. The saved MULASSIS metadata gives a **3-day** duration; the 1-in-100 SHIELDOSE text explicitly gives 1 to 4 July 2040.
- The report says ion range H to U, but the displayed spectra and dose source are solar protons. These files do not establish a complete heavy-ion or galactic cosmic-ray environment.
- The return-period label describes the model's rare-event scenario. It is not a prediction that an event will happen during this mission, nor a multiplier for the 3-day exposure.

## Shielding result: useful trend, uncertain scenario association

Source: the local SHIELDOSE-2 report and its chart. Settings: **SHIELDOSE-2 2.10**, target **tissue**, centre of **aluminium spheres**, proton results **without nuclear attenuation**. Total dose equals the solar-proton contribution in all 25 rows.

| Aluminium thickness | Mass per area | Reported absorbed dose | Converted dose (1 rad = 0.01 Gy) |
|---|---|---|---|
| 0.05 mm | 0.014 g/cm² | 155,900 rad | 1,559 Gy |
| 1 mm | 0.270 g/cm² | 11,330 rad | 113.3 Gy |
| 5 mm | 1.350 g/cm² | 1,441 rad | 14.41 Gy |
| 10 mm | 2.700 g/cm² | 488.7 rad | 4.887 Gy |
| 20 mm | 5.400 g/cm² | 144.8 rad | 1.448 Gy |

Values above follow the rounded report tables. The 1-in-100 text output preserves more digits (for example, 144.77 rad at 20 mm). More aluminium reduces dose in this particular calculation. Mass per area means shield mass spread over area; it is not a length.

**Important mismatch:** both folders' SHIELDOSE reports have exactly the same displayed dose values at all 25 thicknesses, although their source fluences differ. Their report times also differ (22:00:02 for the 1-in-1000 PDF; 22:24:16 for the 1-in-100 HTML, on 11 November 2026). This could be reused/stale output or another configuration issue; the saved files do not prove the cause. Do not use these results to claim the two event scenarios give equal dose. Recompute and check the input spectrum used by each run.

This is an absorbed-dose calculation in a simplified geometry. It does not establish astronaut effective dose in Sv, a safe habitat design, or actual dose at the Mars surface. The files do not document Mars atmosphere/regolith transport, realistic habitat geometry, a body model, or complete secondary-particle treatment. Do not convert rad or Gy directly into Sv.

## MULASSIS result: no usable effective dose yet

Sources: `mulassis-effective-dose-report.html` and `mulassis-effective-dose-output.txt`. The text output records **26 layers**, **5.320000 g/cm²** total shielding and solar-proton input. The short report rounds thickness to **5.3 g/cm²**. Dose and its error are both **NaN Sv**: a numerical result was not obtained. NaN is not zero dose. The output identifies MULASSIS ml-v01-19 and Geant4 geant4-09-02-ref-00 (19 December 2008).

The saved files do not include the layer materials, individual thicknesses, transport settings, run log, random seed or number of simulated primary particles. **Monte Carlo particle count is unknown.** A low count would make the estimate unreliable, especially for rare transmitted particles, but no low count can be confirmed here. The cause of NaN cannot be diagnosed from these summary files alone. The row's 26 is a layer count, not a particle count.

## Next steps for the CNL Mars simulation

1. Start with the solar-fluence report as the source definition. Export the original numerical spectrum and full SPENVIS input settings for each event; charts are for viewing, not precise numerical input. Keep the scenarios separate.
2. Confirm **1.2 AU** is intentional for the chosen Mars scenario and confirm mission dates, exposure interpretation, energy range and angular distribution. Do not silently rescale the saved data.
3. If your simulation needs differential input, use the differential table and its energy-bin convention. Integrate over bin widths to obtain particles/cm² per bin; check the result against integral thresholds. Match the simulation's source-area and angular normalization. Do not divide by time unless a time profile or explicitly assumed average rate is needed.
4. Rerun SHIELDOSE after selecting each source spectrum. Save the input provenance and verify the new dose tables actually correspond to their respective spectra. Use the current aluminium-sphere curve only as a provisional comparison case under the stated assumptions.
5. Retrieve the MULASSIS input deck and full run log. Check all 26 layers, source normalization and dose scoring. Record primary particle count, seed and statistical uncertainty. If the count is low, increase it and check that results and uncertainties stabilize across higher-count runs and independent seeds. No required count or confidence level is established by these files.
6. Obtain a finite dose and finite uncertainty before comparing MULASSIS runs. For the Mars simulation, explicitly model the intended atmosphere, surface shielding, habitat materials and geometry, relevant particle populations and secondary radiation; have the setup reviewed before drawing crew-dose conclusions.

## Preservation notes

Only filenames were changed; all original file bytes were preserved. Existing `.pdf` and `.png` extensions were retained; extensionless HTML, text and PNG files received matching extensions. Hidden `.DS_Store` files are Finder metadata and were left alone. Some original report links reference missing SPENVIS pages (for example `spenvis_sep.html`); no such missing page was supplied or recreated.

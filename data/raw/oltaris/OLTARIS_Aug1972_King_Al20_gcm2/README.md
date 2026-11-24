# OLTARIS: August 1972 King SPE, Al 20 g/cm²

## Scenario and assignment

User-reported configuration: historical August 1972 King solar particle event, free space at 1 AU, aluminium sphere thickness distribution **20 g/cm²**, NASA-Q dose equivalents and effective-dose organ outputs. Kept separate from the 0.4 g/cm² and SPENVIS/SAPPHIRE datasets. Copied from the explicitly supplied Downloads files on 2026-11-12; source files were retained.

The five `.dat` files identify `job_3`, creation time `Thu Nov 12 17:04:02 2026`, TARIS FORTRAN 5.01. Assignment of job_3 to 20 g/cm² follows the user's report of the new download and its later job metadata. The headers do not independently verify sphere thickness, event model, 1 AU location, phantom or all response settings. `effective_dose_equivalent-2.txt` has no job metadata; it is associated with this run by the supplied download grouping, not by dose magnitude alone. Confirm with the OLTARIS job settings if formal configuration verification is required.

## Files and units

| Saved file | Contents/use |
| --- | --- |
| `effective_dose_equivalent_and_organ_results_mSv.txt` | Semicolon-delimited effective dose equivalent and organ totals in mSv. No populated duration, daily rate or annual rate. |
| `absorbed_dose_vs_aluminum_and_tissue_depth_mGy.dat` | Absorbed dose (mGy) versus aluminium and tissue depth (g/cm²). |
| `NASA_Q_leukemia_dose_equivalent_vs_depth_mSv.dat` | Leukemia dose equivalent (mSv) versus aluminium/tissue depth (g/cm²). Not a prediction of leukemia incidence or blood-cell damage. |
| `NASA_Q_solid_cancer_dose_equivalent_vs_depth_mSv.dat` | Solid-cancer dose equivalent (mSv) versus aluminium/tissue depth (g/cm²). Not a cancer-incidence prediction. |
| `NASA_Q_solid_cancer_dose_equivalent_by_particle_vs_depth_mSv.dat` | Solid-cancer dose equivalent (mSv) resolved by particle type across the depth grid. |
| `particle_fluence_vs_energy_isotope_and_depth.dat` | Differential fluence, particles/(EU*·cm²), versus energy, particle/isotope and aluminium/tissue depth. EU* = MeV for photons/electrons/positrons and MeV/amu for other particles. Header specifies fluence, not a per-second flux. |

The `.dat` exports contain OLTARIS headers, dimension records and wrapped arrays; they are not ordinary CSV files. No Point 1 export was supplied for job_3. The supplied `li_Flux_Point_1.dat` is explicitly job_1 and remains only in the 0.4 folder.

## Findings grounded in file contents

- Effective Dose Equivalent: **89.81773000000001 mSv**; Bfo: **48.20886 mSv**; Brain: **150.5727 mSv**; Lens: **251.643 mSv**; Skin: **306.4029 mSv**. These are exported radiation-weighted totals, not absorbed doses in Gy. Bone is exported as 0.0, without explanation.
- The four paired depth databases (absorbed dose, leukemia dose equivalent, solid-cancer dose equivalent and fluence) have **identical non-comment content** to the job_1 downloads. Their job/time headers differ. Consequently these database exports do not themselves demonstrate a shielding-dependent change between the selected spheres. They tabulate multiple depths rather than a single selected sphere's organ result.
- The organ totals do differ from the saved 0.4 dataset (effective dose equivalent 1238.012 mSv; Bfo 1255.8992 mSv). Attribution solely to shielding assumes the remaining job settings were unchanged, as reported by the user.
- Dose tables contain 21 × 21 aluminium/tissue depth grids spanning 0 to 100 g/cm². The fluence database declares 100 energy points × 66 particle entries × 21 × 21 depths. Grid coordinates are not proof of the selected sphere thickness.
- No time profile or populated exposure duration is supplied; these totals do not establish a particular EVA dose or dose rate.

## Byte-preservation manifest

All six files were copied byte for byte and verified. Only names changed; no numeric data were edited.

| Original download | Saved filename | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `effective_dose_equivalent-2.txt` | `effective_dose_equivalent_and_organ_results_mSv.txt` | 569 | `f42aab388b5aa5c964f9c111e0625b352a969b42375a2b3952387a1743b7fac5` |
| `li_dose_database_mGy-2.dat` | `absorbed_dose_vs_aluminum_and_tissue_depth_mGy.dat` | 7658 | `3f0915b71a99801ab9c6e1332f5b36d4e8fcb01f75e4702d90933c18aef621b8` |
| `li_doseq_NASA_Leukemia_database_mSv-2.dat` | `NASA_Q_leukemia_dose_equivalent_vs_depth_mSv.dat` | 7679 | `969c8a4de027856c870669ba6853e0467561536800690b0480edaebcd3049a0a` |
| `li_doseq_NASA_Solid_Cancer_database_mSv-2.dat` | `NASA_Q_solid_cancer_dose_equivalent_vs_depth_mSv.dat` | 7683 | `4d96c1ab161f26ea4db5c9b7ed1a9b15c5037673d1cadd47160e778147b09366` |
| `li_flux_database-2.dat` | `particle_fluence_vs_energy_isotope_and_depth.dat` | 43663021 | `2e9d739bdea8fd3e24662cd4f66836de0e73b065a51935a9ccd6956a9cd186c5` |
| `li_doseq_NASA_Solid_Cancer_part_database_mSv.dat` | `NASA_Q_solid_cancer_dose_equivalent_by_particle_vs_depth_mSv.dat` | 438775 | `180dfc8dae0ee4584250f61e6f941aebbe778044be8ab8b674226c540ad4ff25` |

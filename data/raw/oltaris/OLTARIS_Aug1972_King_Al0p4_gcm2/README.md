# OLTARIS: August 1972 King SPE, Al 0.4 g/cm²

## Scenario and provenance

These six files were recovered from the attachments to the ChatGPT conversation “Ingest Conversation Context” (6af393dd-8eb8-83ea-bd79-3826c1282130) and copied without changing any bytes on 2026-11-12. Original attachments remain intact. This folder is separate from the SPENVIS/SAPPHIRE runs.

User-specified configuration: historical August 1972 King solar particle event; free space at 1 AU; aluminium sphere thickness distribution of **0.4 g/cm²**, with NASA-Q dose equivalent settings and effective-dose organ outputs where applicable. This is **not a 20 g/cm² sphere run**.

Verification limits: the five `.dat` headers identify `job_1`, TARIS FORTRAN version 5.01, and creation time `Thu Nov 12 16:53:35 2026`. They do not independently establish the event model, 1 AU location, selected sphere thickness distribution, anatomical phantom, or all quality-factor settings. The leukemia and solid-cancer dose-equivalent types are explicit in their headers; NASA labeling also comes from their original filenames. The effective-dose text has no job/configuration metadata. Association of all six with this configuration is supplied by the user, not independently proved by the numeric tables. The prior conversation's later 20 g/cm² recommendation does not redefine these exports.

## Files, units and use

| File | Contents and use |
| --- | --- |
| `effective_dose_equivalent_and_organ_results_mSv.txt` | Semicolon-delimited effective dose equivalent and named organ results. Header labels total values in mSv; rows contain only that total, without populated daily/yearly rates or a duration. Use for reported effective/organ outputs, not absorbed dose in Gy. |
| `absorbed_dose_vs_aluminum_and_tissue_depth_mGy.dat` | Absorbed dose in mGy versus aluminium and tissue depths, both in g/cm². Use for depth-dependent absorbed-dose comparisons. |
| `NASA_Q_leukemia_dose_equivalent_vs_depth_mSv.dat` | Leukemia dose equivalent in mSv versus aluminium/tissue depths in g/cm². Use for this radiation-quality-weighted dose quantity, not cancer incidence. |
| `NASA_Q_solid_cancer_dose_equivalent_vs_depth_mSv.dat` | Solid-cancer dose equivalent in mSv versus aluminium/tissue depths in g/cm². Use for this radiation-quality-weighted dose quantity, not cancer incidence. |
| `particle_fluence_vs_energy_isotope_and_depth.dat` | Differential fluence in particles/(EU*·cm²), versus energy, particle/isotope, aluminium depth and tissue depth. Use for particle spectra across the transport grid. Despite original “flux” filename, the header specifies fluence, with no per-second unit. |
| `particle_fluence_vs_energy_and_isotope_point_1.dat` | Differential fluence in particles/(EU*·cm²) at Point 1 versus energy and particle/isotope. The physical location/depth of Point 1 is not specified in this file. |

EU* is MeV for photons, electrons and positrons, and MeV/amu for all other particles, as stated in both fluence headers. The `.dat` files retain OLTARIS comment lines, dimension declarations and wrapped arrays; they are not ordinary CSV files.

## Findings verified from the files

- The effective-dose file reports Effective Dose Equivalent **1238.012 mSv**, Bfo **1255.8992 mSv**, Brain **2453.724 mSv**, Lens **29692.66 mSv**, and Skin **88166.23 mSv**. These are the exported mSv values, not absorbed doses in mGy or Gy. `Bone;0.0` is also present; the export does not explain this zero.
- Each dose database declares a 21 × 21 grid. Both depth axes include 0, 0.4, 20 and 100 g/cm² and span 0 to 100 g/cm². Those are transport database coordinates; the presence of 20 g/cm² does not establish a separate sphere configuration.
- The full fluence database declares 100 energy points × 66 particle entries × 21 aluminium depths × 21 tissue depths. The Point 1 export declares 100 energy points × 66 particle entries. The energy grid spans 0.01 to 2500 EU*.
- No exposure duration is populated in the organ text, so daily or annual rates cannot be established from it. No whole-body dose is inferred here from an individual depth-grid value.

## Original names and byte-preservation record

Each saved data file was verified against its attachment using SHA-256. Only filenames changed.

| Original attachment | Saved filename | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `effective_dose_equivalent.txt` | `effective_dose_equivalent_and_organ_results_mSv.txt` | 582 | `a90fa96b2058c46f5f69d6cc16a890da4b4eebb8f12a90cb9b7fb3ccfdf36d77` |
| `li_dose_database_mGy.dat` | `absorbed_dose_vs_aluminum_and_tissue_depth_mGy.dat` | 7,658 | `4532dee5c6fc6fa3261b50ac67d848be573d58a7bfa345d900225118a21bcdc4` |
| `li_doseq_NASA_Leukemia_database_mSv.dat` | `NASA_Q_leukemia_dose_equivalent_vs_depth_mSv.dat` | 7,679 | `f6cd5e71ed8c0ae3c3a951ee4721cc57db9cb4d7309f74e8e98120168a1d1cbf` |
| `li_doseq_NASA_Solid_Cancer_database_mSv.dat` | `NASA_Q_solid_cancer_dose_equivalent_vs_depth_mSv.dat` | 7,683 | `9b5ba5988e245ea15eaee89e0e3d92bdd2847d406107e6049a452f4ad0a51209` |
| `li_flux_database.dat` | `particle_fluence_vs_energy_isotope_and_depth.dat` | 43,663,021 | `44f3b684feecbb5ea3218c7def237e9fda7b01b1133c5e3f47ffbf92a8785046` |
| `li_Flux_Point_1.dat` | `particle_fluence_vs_energy_and_isotope_point_1.dat` | 102,124 | `b443ed4e5820319dcedb7d4561d2aabd95bf9957aa4c49044b804c8ee41874c1` |

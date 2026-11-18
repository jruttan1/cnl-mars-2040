# AGENTS.md — CNL Mars 2040 Emergency Response Project

## 1. Project Overview

This repository contains our team's research, scientific modeling, and programmatic emergency-response simulator for the **Fall 2026 Western University–Canadian Nuclear Laboratories (CNL) Case Competition**.

**Case:** Nuclear Emergency During a Mars Mission (2040)

**Team:** Team 21, Western University

**Team members:** Angelo Cassasanta, Ethan Rajack, Isabella Hicks, and John Ruttan.

**Competition dates:** November 18–19, 2026.

The project investigates how astronauts aboard two differently powered spacecraft could recover from severe meteoroid damage while facing an impending Solar Particle Event (SPE), unreliable radiation monitoring, degraded communications, and potentially dangerous extravehicular activities (EVAs).

Our approach combines:

- Nuclear propulsion engineering and emergency-response planning.
- Solar energetic particle environment modeling.
- Anatomical radiation dosimetry.
- Historical solar storm observations.
- Biodosimetry and biological dose estimation.
- Bayesian estimation under uncertainty.
- Autonomous operational decision trees.
- Mission and EVA simulation.
- Monte Carlo comparisons of alternative emergency-response strategies.

The central research question is:

**How can mission crews make better emergency-recovery decisions when radiation exposure is uncertain, spacecraft systems are damaged, and delaying repairs may itself threaten mission survival?**

A related question is whether additional biological information meaningfully improves operational outcomes relative to conservative procedures and radiation forecasting alone.

The purpose of the simulator is to investigate these questions, not to reproduce every physical detail of a Mars spacecraft.

---

## 2. Official CNL Case Scenario

### Scenario facts

In 2040, two countries are competing to complete the first successful crewed mission to Mars.

Each country has launched a spacecraft using a different nuclear propulsion technology:

1. **Nuclear Thermal Propulsion (NTP).**
2. **Nuclear Electric Propulsion (NEP).**

After passing the midpoint of their journeys, both spacecraft encounter a severe meteoroid shower.

The impacts cause significant damage to propulsion, monitoring, and communications systems.

Initial assessments indicate that restoring critical systems will require **multiple EVAs lasting approximately seven hours each**.

During EVA preparations, Mission Control warns of an impending Solar Particle Event that could expose astronauts to dangerous levels of radiation.

Conventional radiation-monitoring equipment is unreliable or unavailable.

Communications and other systems may be degraded, limiting the information and assistance available from Mission Control.

The crew must determine how to stabilize its spacecraft, repair critical systems, manage radiation exposure, and decide whether the mission can safely continue.

### Important case limitations

The official case does **not** specify:

- Exact crew size or composition.
- The number of EVAs beyond requiring multiple.
- Exact SPE arrival time, duration, intensity, or energy spectrum.
- Specific reactor power outputs.
- Detailed spacecraft geometry.
- Actual spacesuit shielding thickness.
- Spacecraft cabin shielding distribution.
- Exact location of every damaged component.
- Numerical repair deadlines.
- Propellant reserves or thermal margins.
- Specific EVA worksite radiation levels.
- Complete astronaut medical histories.
- Specific onboard biodosimetry instruments or their performance.
- A guaranteed safe return trajectory.

These unknowns are intentionally part of the decision-making challenge.

The simulator may introduce reasonable assumptions, but it must distinguish them from facts supplied by CNL.

The case emphasizes **significant time pressure**, but does not specify an exact deadline by which every repair must be completed.

It also does not state that all repairs must happen before the SPE arrives, or that waiting until the SPE has ended is necessarily feasible.

---

## 3. Competition Presentation Requirements

The official pitch guidelines specify:

- **7 minutes:** Live team presentation.
- **5 minutes:** Questions from judges.

The judging criteria are:

1. Clarity of problem framing.
2. Communication of scientific and engineering reasoning.
3. Use of visuals and presentation design.
4. Communication of risk, uncertainty, and ethics.
5. Q&A mastery and technical defense.

The guidelines explicitly emphasize clear explanations and defensible reasoning over perfect calculations.

The presentation should address:

- How NTP and NEP change the emergency response.
- How crews assess radiation and plan EVAs.
- How biodosimetry informs medical and operational decisions.
- How uncertainty, competing risks, and ethical considerations are handled.
- How the spacecraft can recover, and when mission continuation is no longer justified.

Useful visual evidence includes decision trees, timelines, radiation charts, scenario comparisons, and simplified operational diagrams.

Our simulator and research are supporting evidence for the proposed recovery strategy. They are not themselves the entire solution.

An especially valuable presentation result would demonstrate how two strategies make different decisions under the **same underlying emergency**, and how those decisions affect repair completion, radiation exposure, or mission viability.

---

## 4. Original Team Abstract and Commitments

Our submitted abstract proposes an integrated, radiation-dose-governed mission recovery strategy informed by:

1. Reactor and spacecraft state.
2. An uncertain SPE forecast.
3. Continuously updated estimates of astronaut radiation exposure derived from biodosimetry.

It explicitly distinguishes NTP and NEP engineering risks.

### NTP considerations in the abstract

NTP propulsion uses relatively discrete engine burns separated by extended coast periods.

During the relevant coast phase, the NTP reactor is assumed to be shut down, although residual thermal and radiation hazards may remain.

The abstract emphasizes:

- Hydrogen propellant loss.
- Reactor restart readiness.
- Decay-heat management.
- Preservation of propellant needed for future maneuvers.
- The importance of a later Mars braking burn.

### NEP considerations in the abstract

NEP depends on reactor-generated electricity and substantial heat-rejection infrastructure.

The abstract emphasizes:

- Radiator integrity.
- Thermal management.
- Power availability.
- Reactor throttling or shutdown after cooling-system damage.
- Reactor shielding geometry and restricted EVA access.
- Restoration of propulsion capability.

### Repair and recovery approach

The abstract proposes remote inspection before exposing astronauts unnecessarily.

Its general repair priorities are:

1. Power and thermal control.
2. Communications and monitoring.
3. Propulsion recovery.

Actual priorities may differ according to propulsion technology, damage state, and urgency.

### Biodosimetry approach

The abstract proposes several biological indicators:

- Clinical symptom onset for immediate medical triage.
- γ-H2AX foci as a time-dependent indicator of DNA damage response.
- Serial lymphocyte counts compared against preflight baselines.

It also proposes a **transparent Bayesian estimator** that combines biological information into an estimated dose distribution with explicitly represented uncertainty.

The model should acknowledge uncertainties such as nonuniform exposure, individual variability, biomarker kinetics, measurement noise, and delayed observations.

### Monte Carlo commitment

The abstract proposes Monte Carlo modeling to investigate uncertain SPE occurrences and magnitudes and compare EVA strategies.

Possible operational decisions include:

- Proceed with EVA.
- Delay EVA.
- Segment repair work when feasible.
- Rotate crew.
- Shelter.
- Initiate medical assessment or treatment.
- Abort EVA.
- Abandon mission objectives when continuation is no longer feasible.

The abstract emphasizes informed consent, equitable exposure management, autonomy during communication loss, and conservative safety choices.

**Mission continuation requires stabilized critical systems, acceptable crew exposure risk, and sufficient propulsion capability or margin.**

This is the conceptual commitment in the abstract. The implementation may evolve as the research establishes what is scientifically defensible.

---

## 5. Overall Modeling Philosophy

The project is not intended to simulate a complete spacecraft or nuclear reactor from first principles.

Instead, it models the relationship between:

**Physical emergency → uncertain observations → operational decisions → changing mission state → outcomes.**

The radiation environment is comparatively quantitative, while spacecraft engineering, repair constraints, autonomy, and ethics may require more abstract models.

The project should not optimize radiation exposure in isolation.

A crew that never performs an EVA might minimize exposure while allowing its spacecraft to become unrecoverable.

Likewise, a strategy that completes every repair immediately might expose astronauts to unacceptable risk.

The interesting problem is the interaction between these competing requirements.

Some factors are:

- **Hard constraints:** Conditions that prohibit an action.
- **Operational trade-offs:** Risks that must be weighed against one another.
- **Mission objectives:** Desired outcomes subject to the constraints.

A core principle is that **crew survival and essential spacecraft safety take precedence over the competitive objective of reaching Mars first**.

The quantitative model should inform decisions without replacing engineering judgment or pretending that ethical choices are reducible to a single score.

---

## 6. Radiation Environment: Scientific Source Chain

The current radiation model combines several distinct source families.

These sources are not independent measurements of the same quantity.

Each contributes a different part of the synthetic radiation environment.

### 6.1 ESA SPENVIS and SAPPHIRE

SAPPHIRE provides event-integrated solar energetic proton fluence spectra.

We have modeled:

- **1-in-100-year SPE:** Main severity scenario.
- **1-in-1,000-year SPE:** Extreme stress-test scenario.

The return-period labels describe statistical source-model scenarios, not the probability that the specific Mars mission encounters such an event.

The exported spectra describe proton fluence as a function of energy over an entire modeled event.

They do not directly provide hourly intensity forecasts.

Our SPENVIS setup used a nominal interplanetary location near 1.25 AU, with outputs labeled approximately 1.2 AU.

The exported source magnitudes were not independently adjusted for heliocentric distance.

OLTARIS uses a free-space 1-AU environment designation.

Our interpretation is therefore:

**Reference proton spectra applied to a hypothetical Mars-transit emergency near 1.25 AU, without a separately validated distance correction.**

Do not describe these results as exact 1.25-AU radiation predictions.

### 6.2 Band-function approximation

To use the SAPPHIRE spectra with NASA OLTARIS, we fitted a rigidity-based Band function.

The initial Weibull approximation was superseded because it did not reproduce the original spectra sufficiently well.

The initial Band calculations also contained a normalization mistake involving rigidity units.

This was investigated using exported OLTARIS proton spectra and an independent numerical audit.

The corrected parameters are:

| Parameter | 100-year | 1,000-year |
|---|---:|---:|
| J0 | 1.00959834e11 | 2.06586789e11 |
| R0 (MV) | 65.90468 | 65.09875 |
| gamma1 | 0.263780 | 0.180525 |
| gamma2 | 4.674330 | 4.675966 |

The corrected fits reproduce the source integral fluence at the supplied energy points with maximum deviations of approximately:

- 100-year: 3.18%.
- 1,000-year: 3.01%.

This validates the numerical approximation of the **integral source spectra at those sample points**.

It does not establish an equivalent uncertainty bound on anatomical organ doses or all differential spectral contributions.

The original incorrect Band runs must not be substituted for the corrected results.

### 6.3 NASA OLTARIS anatomical transport

NASA OLTARIS was used to estimate radiation absorbed by human organs behind idealized aluminium shielding.

The corrected simulations use:

- User-defined Band SPE spectra.
- MAX male anatomical model.
- Aluminium sphere shielding geometry.
- Tissue absorbed dose.
- NASA quality-factor dose equivalents.
- Effective dose equivalent.
- Gray Equivalent.

The four corrected primary configurations are:

| SPE severity | Shielding | BFO absorbed dose | BFO Gray Equivalent |
|---|---:|---:|---:|
| 100-year | 0.4 g/cm² | 415.1 mGy | 623.3 mGy-Eq |
| 100-year | 20 g/cm² | 43.14 mGy | 63.99 mGy-Eq |
| 1,000-year | 0.4 g/cm² | 723.7 mGy | 1,087 mGy-Eq |
| 1,000-year | 20 g/cm² | 75.20 mGy | 111.6 mGy-Eq |

These are **full-event totals**, not hourly dose rates or automatic seven-hour EVA doses.

The 0.4 g/cm² configuration is a lightweight EVA shielding surrogate.

The 20 g/cm² configuration is a protected-cabin shielding surrogate.

Neither represents a detailed spacecraft or spacesuit geometry.

Additional suit shielding sensitivities, including approximately 2 and 5 g/cm², have been discussed as possibilities. They are not automatically part of the validated four-run anatomical baseline.

The anatomical model uses a male reference phantom. It does not directly produce personalized organ doses for each astronaut based on sex, body mass, or individual anatomy.

### 6.4 Radiation quantities must remain distinct

**Absorbed dose (mGy)** represents deposited radiation energy per unit mass.

**Gray Equivalent (mGy-Eq)** incorporates radiation-specific biological weighting for the relevant organ-protection quantity.

**Dose equivalent and effective dose equivalent (mSv)** are different radiation-protection quantities.

These are not interchangeable.

For our model:

- BFO absorbed dose is a relevant input to exploratory biological dose-response models.
- BFO Gray Equivalent is used in separate comparisons with NASA organ-exposure references.
- Effective dose equivalent and other organ metrics remain available for analysis.

The previously discussed NASA 30-day blood-forming-organ reference is **250 mGy-Eq**.

This is a radiation-protection reference, not a sudden threshold for symptoms, incapacitation, or death.

Exceeding it should not automatically produce a deterministic clinical outcome.

### 6.5 SHIELDOSE-2

SHIELDOSE-2 was used separately to calculate absorbed dose in an idealized tissue target at several aluminium shielding depths:

0.4, 1, 2, 5, 10, and 20 g/cm².

This dataset is preserved as an independent physical reference.

It should not be substituted directly for anatomical BFO dose.

The corrected OLTARIS point-dose results are broadly consistent with SHIELDOSE-2 for matched shielding conditions, which supports normalization consistency but does not independently validate detailed organ transport.

### 6.6 Historical August 1972 King event

An OLTARIS simulation of the August 1972 King SPE was also completed.

It provides a historical anatomical transport reference and served as an early exploratory bridge between point dose and organ dose.

However, the final SAPPHIRE anatomical calculations no longer depend on transferring a King-derived organ-to-point dose ratio.

The historical King model and earlier experimental conversions are retained as scientific context, not the primary simulator calibration.

---

## 7. Historical Storm Timing

SAPPHIRE provides the total severity and energy spectrum.

Historical spacecraft measurements provide examples of how solar proton intensity changes over time.

We currently use two timing templates.

### August 1972

Source: Historical proton observations, including IMP-5 data accessed through NASA OMNIWeb.

The processed timing record contains 264 hourly bins.

Eight observations are missing in the supplied channels.

The project considers several interpolation techniques, including log-linear, linear, and PCHIP.

Some high-intensity periods are affected by missing measurements.

In one previously examined seven-hour peak window, approximately 35.2% of the modeled dose was allocated to interpolated hours.

This is not a measured percentage error; it is the portion of allocated exposure corresponding to reconstructed data.

### October–November 2003 Halloween solar storms

Source: GOES-10 proton measurements, accessed through NASA-related historical data services.

The processed record contains 336 hourly bins.

The supplied greater-than-10, greater-than-30, and greater-than-60 MeV channels have complete hourly coverage.

The exact numerical match between the processed historical file and its official archive source has been identified as an outstanding provenance check.

### Combining spectra and timing

The current synthetic dose model distributes OLTARIS full-event organ doses according to normalized historical hourly proton intensity.

Conceptually:

`hourly_organ_dose = full_event_organ_dose × normalized_historical_hourly_weight`

The weights sum to one across the modeled event.

Consequently, the timing profiles change **when** the dose occurs without changing the selected event-total organ dose.

This is an important modeling approximation.

It assumes that the historical intensity profile is an appropriate proxy for the time variation of dose from the synthetic SAPPHIRE spectrum.

Real solar energetic particle spectra evolve over time, including changes in spectral hardness.

A single normalized proton channel does not reproduce a fully time-dependent, energy-resolved anatomical transport calculation.

The simulator therefore models **SAPPHIRE-derived organ-dose estimates distributed using historical solar particle event timing profiles**.

This is not an exact forecast of a future solar storm.

---

## 8. Existing Mission Simulation

The repository contains a Python simulator that advances an emergency mission through time.

It models:

- Spacecraft and mission state.
- Crew members and astronaut availability.
- EVA scheduling and execution.
- Repair progression.
- Cabin versus EVA radiation exposure.
- Accumulated astronaut exposure.
- Operational decision-making.
- Mission termination and recovery outcomes.

The radiation environment currently distinguishes between:

- BFO absorbed dose.
- BFO Gray Equivalent.
- Cabin shielding.
- EVA shielding.
- Historical storm timing.
- SPE severity.

Astronauts accumulate exposure inside the spacecraft as well as during EVAs.

An astronaut should not receive zero radiation simply because another crew member is outside.

The underlying physical environment represents simulator ground truth.

**The strategy should not automatically have access to this ground truth.**

There is an important difference between the true simulated dose and the dose information that the crew can estimate using forecasts, symptoms, or biodosimetry.

The existing repository, tests, README, and source inventory are authoritative for the code's actual implementation status.

Do not assume every feature described in this document has already been implemented.

---

## 9. Proposed Strategy Comparison

We intend to compare four emergency-response strategies.

All four must operate under the same underlying physics, mission constraints, and definitions of success.

They differ primarily in **what information is available to decision-makers and how that information changes operational decisions**.

### Strategy A — Conservative baseline

Uses established operational safety procedures without reliable physical radiation dosimetry or sophisticated biodosimetry.

Possible information includes:

- Spacecraft condition.
- Reactor and system status.
- Elapsed mission time.
- Generic SPE warning.
- Crew operational status.
- Observable symptoms.
- Preset safety requirements and procedural limits.

It should not have accurate knowledge of the future storm or the true accumulated organ dose.

Strategy A should remain reasonably conservative.

It must not be intentionally reckless just to create an easy baseline for the proposed solution to outperform.

### Strategy B — Forecast-informed operations

Adds an imperfect radiation forecast.

It can consider:

- Predicted storm onset.
- Expected intensity.
- Forecast uncertainty.
- Possible safer EVA windows.
- Projected exposure over a proposed repair interval.

A forecast must not reveal the true future trajectory with perfect accuracy.

This strategy isolates the value of radiation forecasting and scheduling before introducing biodosimetry.

### Strategy C — Conventional biodosimetry

Adds conventional onboard biological measurements for estimating previous exposure and astronaut fitness.

Potential observations include:

- Serial lymphocyte counts.
- Conventional cytogenetic biodosimetry where feasible.
- Periodic blood sampling.
- Clinical assessment.

The sampling process may introduce:

- Processing delays.
- Measurement uncertainty.
- Biological response delays.
- Operational costs.
- Crew availability constraints.

The idea of testing an astronaut periodically or after an EVA is being considered.

Hourly blood-test results should not be assumed to become clinically informative instantaneously.

Returning an astronaut from EVA solely for testing should have an explicit operational rationale and cost.

### Strategy D — Personalized multimodal biodosimetry

Adds a more advanced proposed 2040 measurement and estimation capability.

Potential inputs include:

- γ-H2AX foci.
- Radiation-responsive gene-expression markers, including FDXR, DDB2, and CDKN1A.
- Serial lymphocyte data.
- Individual preflight baselines.
- Repeated measurements over time.
- Clinical observations.
- Potentially more frequent or in-EVA measurements.

The idea of measuring meaningful biological radiation signals during EVA is an **exploratory future technology concept**, not an established continuously functioning 2040 instrument.

Its feasibility, biological response time, measurement latency, and reliability must be represented as assumptions.

The intended value of D is more timely, individualized, uncertainty-aware information.

It should not simply receive perfect measurements or guaranteed superior decisions.

---

## 10. Bayesian Biodosimetry Estimation

The team's abstract specifically commits to a **transparent Bayesian estimator**.

Its purpose is to infer an astronaut's likely accumulated radiation dose from uncertain biological observations.

This is not the same thing as Monte Carlo mission simulation.

### Concept

The estimator begins with a prior distribution over possible absorbed doses.

The prior might incorporate:

- Existing exposure estimates.
- Estimated previous EVA exposure.
- Mission radiation information available to the strategy.
- Astronaut-specific baseline information.

As biological measurements arrive, the estimator updates the distribution using dose-response likelihoods.

Conceptually:

`posterior dose distribution ∝ biomarker likelihood × prior dose distribution`

The outputs may include:

- Posterior median or mean absorbed dose.
- Credible interval.
- Probability of exceeding a selected exposure-management criterion, where the modeled quantities support that comparison.
- An indication that measurements are uninformative or inconsistent.

### Important scientific details

Biological markers do not all respond in the same way.

γ-H2AX is time-dependent and affected by both damage induction and repair.

Lymphocyte depletion evolves over time and is influenced by individual and clinical factors.

Gene-expression responses vary with dose, elapsed time, cell composition, and experimental conditions.

Different biological measurements may be correlated.

It would be incorrect to treat every biomarker as an independent, instantaneous, perfectly calibrated sensor of cumulative dose.

The model must also distinguish between absorbed-dose estimates and Gray Equivalent exposure-limit comparisons.

An absorbed-dose posterior cannot simply be compared numerically with a mGy-Eq threshold without a separately justified relationship.

### Relationship between C and D

A promising architecture is **one shared inference framework with different measurement models and observation schedules**.

Strategy C would use conventional measurements.

Strategy D would use additional multimodal signals and potentially faster or more personalized measurement capabilities.

This prevents the experiment from unfairly giving D a superior estimation algorithm solely because it is labeled the advanced strategy.

Any advantage should arise from the information quality, timing, calibration, and operational usefulness of its measurements.

The final observation models and likelihood functions remain research and implementation tasks.

The repository may contain partial implementations or scaffolding; inspect the current code to determine their actual state.

---

## 11. Hierarchical Mission and EVA Decision-Making

We have discussed a nested decision architecture.

### Outer loop — Mission recovery

This operates at the spacecraft and mission level.

Its responsibilities include:

- Assessing damaged systems.
- Establishing repair urgency.
- Determining required stabilization.
- Choosing repair priorities.
- Evaluating available crew and resources.
- Deciding whether another EVA is necessary.
- Deciding whether repairs can wait.
- Determining whether mission objectives remain feasible.
- Declaring mission recovery or failure.

A mission-objective failure is not identical to crew death or loss of the spacecraft.

### Inner loop — EVA operations

This governs individual EVA decisions.

Potential decisions include:

- Start.
- Continue.
- Pause or shelter when feasible.
- Abort.
- Return to spacecraft.
- Reassign or rotate crew.
- Schedule a later repair attempt.

The inner loop responds to updated observations and mission conditions.

### Shared decision structure

The four strategies may share a broad decision-tree structure while using different methods for evaluating radiation-related branches.

This allows differences in strategy performance to be attributed to available information and decision policies rather than entirely different physical simulation rules.

Decision-tree diagrams may be generated from structured Python definitions.

Ideally, the diagrams and the executable decision logic originate from the same representation.

The intended relationship is:

**Observation model → decision policy → action → shared mission-state transition.**

---

## 12. Engineering and Qualitative Mission Constraints

We recognized that radiation physics had been modeled much more deeply than the actual spacecraft emergency.

The simulator should therefore represent the qualitative considerations of the case in a way that has real operational consequences.

These include:

- Reactor safety.
- Spacecraft stabilization.
- Damage inspection.
- Repair prerequisites.
- Different repair priorities.
- System deterioration.
- Urgent versus deferrable repairs.
- Worksite accessibility.
- Life-support limitations.
- Crew eligibility.
- Communications failures.
- Operational autonomy.
- Ethical exposure management.
- Mission continuation feasibility.

These considerations should not exist solely as explanatory labels.

They should influence whether actions are permitted, which tasks are prioritized, how delays affect the spacecraft, and whether the mission can recover.

### Dedicated engineering model

An architectural preference discussed for this project is to keep qualitative engineering constraints in their **own dedicated Python module**, separate from radiation modeling and individual strategy implementations.

That module should integrate with the existing mission simulator.

It should **not become an independent emergency-response simulator** that duplicates mission time, EVA execution, astronaut state, or repair progression.

There should be one authoritative mission simulation engine.

The engineering module can supply constraints, transition rules, repair feasibility, and propulsion-specific behavior.

The existing simulator remains responsible for advancing mission state.

This distinction was clarified after an earlier implementation created a separate emergency-response simulator, which was not the intended architecture.

---

## 13. NTP and NEP Differences

The project must evaluate both propulsion technologies.

The current concept is to use a shared simulation framework with different spacecraft engineering configurations.

### NTP — Nuclear Thermal Propulsion

The coast-phase NTP reactor is assumed to be shut down.

Potential hazards and recovery concerns include:

- Hydrogen propellant leaks.
- Propellant isolation.
- Residual reactor radiation.
- Decay heat.
- Engine-bay access restrictions.
- Restart readiness.
- Preserving sufficient propellant for future burns.

An illustrative recovery sequence is:

1. Confirm reactor state and establish safe work conditions.
2. Inspect and isolate damaged hydrogen systems if necessary.
3. Restore other critical power, thermal, monitoring, or communications functions.
4. Repair propulsion-related damage.
5. Verify safe restart capability and remaining propellant margin.

A hydrogen leak should not be assumed in every randomized emergency unless the damage scenario specifies it.

### NEP — Nuclear Electric Propulsion

The NEP spacecraft relies on reactor-generated electricity and heat-rejection equipment.

Potential concerns include:

- Radiator damage.
- Coolant integrity.
- Inadequate heat rejection.
- Need to reduce reactor power or shut down.
- Reduced electrical availability.
- Lost thrust capability.
- Reactor worksite shielding.
- Restricted external access.

An illustrative recovery sequence is:

1. Stabilize reactor power and thermal conditions.
2. Assess and recover heat rejection.
3. Restore critical electrical, monitoring, and communications systems.
4. Repair or recover propulsion capability.
5. Verify sustainable operation.

### Specific claims that need care

An earlier slide discussed an approximately 10 MWt NEP reactor, an NTP engine-bay hazard of approximately 6 Sv/h, and a roughly 24-hour delay before NEP radiator work.

These must **not be treated as universally applicable technical facts**.

They may be source-specific examples or team assumptions, but their applicability depends on reactor configuration, geometry, operating history, shutdown conditions, and local shielding.

The existing solar proton model does not calculate reactor radiation fields.

Reactor-related EVA restrictions may need to be represented qualitatively unless a separate, justified reactor dose model is available.

### Engineering effects on simulation

NTP and NEP should create differences in:

- Stabilization requirements.
- Repair sequence and priority.
- Worksite accessibility.
- Repair urgency.
- Permissible reactor states.
- Mission feasibility.
- Potential ability to delay an EVA.

They should not automatically have different solar radiation physics unless corresponding physical conditions justify it.

Both spacecraft should remain subject to the same overarching crew-safety principles.

---

## 14. Repair Urgency, Mission Success, and Failure

The case creates an important conflict between waiting for safer radiation conditions and repairing systems before further deterioration.

A meaningful simulator should account for both.

For example:

- Waiting for a solar storm to subside may reduce EVA exposure.
- Waiting may also allow a leaking system or failing thermal subsystem to become unrecoverable.
- Repairing immediately may preserve the spacecraft but increase crew exposure.
- An unsuccessful EVA may consume resources without resolving the emergency.

The official case does not supply numerical repair deadlines.

Any deadlines, deterioration rates, or resource depletion models are assumptions or scenario variables.

They should be documented and, where feasible, examined through sensitivity analysis.

### Distinguish termination outcomes

Possible outcomes include:

- Critical repairs completed.
- Mission stabilized but unable to continue toward Mars.
- Mars mission objectives abandoned.
- EVA suspended or aborted.
- Crew sheltered while repairs remain pending.
- Spacecraft unrecoverable.
- Simulation timeout.
- Crew survival compromised.

Aborting an EVA is not automatically a mission failure.

Abandoning the goal of reaching Mars is not automatically the loss of the crew.

A strategy that protects the crew but cannot restore the spacecraft should be evaluated differently from a strategy that completes repairs while creating unacceptable radiation risk.

The mission success and failure definitions should be common to all strategies.

---

## 15. Ethical and Human Factors

The team's original abstract emphasizes that crew health cannot be treated merely as a cost paid to win the Mars race.

Relevant considerations include:

- Informed consent.
- Equitable allocation of risk.
- Crew rotation.
- Avoiding unnecessary repeated exposure of one individual.
- Preserving crew capability.
- Medical fitness and astronaut availability.
- Decisions under uncertain medical information.
- Autonomous operation during communications loss.
- Conservative responses when essential information is unavailable.

These considerations may be implemented as operational policy constraints rather than arbitrary numerical utilities.

For example, a crew-selection policy may consider both individual exposure histories and required skills.

However, a strategy should not be artificially penalized for selecting the same astronaut twice when the mission circumstances genuinely require that choice.

Ethical modeling assumptions should be explicit and consistent across strategies.

---

## 16. Monte Carlo Experiment: Intended Design

The eventual Monte Carlo simulation is intended to compare the four emergency-response strategies under many uncertain mission scenarios.

It is an experiment runner around the existing mission simulator, not a replacement radiation-physics engine.

### Basic procedure

1. Generate a hypothetical emergency scenario.
2. Establish the underlying true storm, spacecraft damage, crew, and mission constraints.
3. Run all four strategies on independent copies of the same underlying scenario.
4. Give each strategy only the observations it is permitted to receive.
5. Record decisions, accumulated exposure, repair progress, and terminal outcomes.
6. Repeat across many sampled scenarios.
7. Summarize strategy performance and uncertainty.

Using paired scenarios is essential for a fair comparison.

### Potential fixed assumptions

Depending on the experiment:

- Approximate seven-hour EVA repair duration.
- Shared physical radiation model.
- Common repair and safety rules.
- Shared spacecraft configurations.
- Comparable crew resources.
- Common mission-success criteria.

An earlier demonstration used five astronauts, one astronaut per EVA, sequential EVAs, and one-hour turnaround.

Those were team-defined assumptions, not official CNL facts.

### Potential scenario variables

- NTP versus NEP.
- 100-year versus 1,000-year SPE severity.
- August 1972 versus October 2003 timing template.
- Relative storm arrival time.
- Spacesuit shielding.
- Crew size.
- Damage severity and repair urgency.
- Repair duration uncertainty.
- Crew skills or availability.
- Communication quality.
- Forecast uncertainty.
- Biomarker measurement error and latency.
- Individual biological-response variability.

Not all variables need to be randomized simultaneously.

Some may be better treated as separate experimental conditions or sensitivity analyses.

SAPPHIRE return periods should not be converted into arbitrary mission encounter probabilities.

### Intended outcomes

Possible metrics include:

- Percentage of scenarios with successful mission recovery.
- Critical repair completion rate.
- Time to restore essential systems.
- Frequency of mission-objective abandonment.
- Maximum individual BFO absorbed dose.
- Maximum individual BFO Gray Equivalent.
- Frequency of exceeding defined operational reference thresholds.
- Crew exposure inequality.
- Unnecessary EVA aborts or delays.
- Radiation dose-estimation error.
- Crew availability.
- Sensitivity to forecast errors.
- Sensitivity to biomarker accuracy.
- Performance differences between NTP and NEP.

Statistical outcomes should be presented with uncertainty and the assumptions that produced them.

The advanced strategy should not be guaranteed to win.

A meaningful outcome might be identifying when multimodal biodosimetry adds value and when simpler forecast-informed scheduling is sufficient.

### Presentation outputs

The most valuable outputs are likely:

1. A strategy performance comparison showing mission recovery and exposure risk.
2. A representative mission timeline illustrating different decisions during the same solar event.
3. A concise NTP/NEP comparison.
4. Sensitivity analysis showing how assumptions affect the conclusions.

Detailed simulation logs, large tables, and additional charts can support technical Q&A.

---

## 17. Current and Proposed Biological-Response Modeling

The current simulator can estimate absorbed organ dose over time.

This is not equivalent to predicting clinical symptoms.

Biological effects depend on factors including:

- Dose.
- Dose rate.
- Radiation quality.
- Organ and tissue.
- Exposure geometry.
- Timing.
- Biological repair.
- Individual variability.

The model does not currently establish a validated mapping from the synthetic BFO exposure profiles to acute radiation syndrome, specific symptoms, or astronaut incapacitation.

Clinical references are primarily contextual unless an appropriate biological-response model is implemented.

Symptoms should not automatically appear at a particular BFO absorbed dose solely because a generic threshold was found in clinical guidance.

Similarly, biomarker observations must be generated using documented or explicitly assumed dose-response relationships and observation uncertainties.

This is especially important for the comparison of Strategies C and D.

---

## 18. Model Validation and Provenance

The repository contains multiple source-data families, archived experiments, processed outputs, audits, and tests.

These should not be interpreted as numerous independent experiments validating the same result.

Important source families include:

- SAPPHIRE / SPENVIS proton spectra.
- Corrected Band parameter fits.
- Corrected OLTARIS MAX anatomical runs.
- SHIELDOSE-2 shielding calculations.
- August 1972 historical proton observations.
- October–November 2003 GOES-10 observations.
- NASA radiation protection guidance.
- Official CNL scenario and competition guidelines.

### Historical / superseded experiments

Earlier versions include:

- Initial Weibull fits.
- Incorrectly normalized Band runs.
- Historical King OLTARIS anatomical modeling.
- Exploratory King-to-SAPPHIRE organ-dose scaling.
- Incomplete October 2003 OMNI2 data.
- Gap-heavy October 1989 timing data.
- Failed or unusable radiation-model outputs.
- Older pre-anatomical mission timelines and charts.

These can be useful for traceability, but should not silently become current simulator inputs.

### Validation status

Previous project audits checked:

- Source consistency.
- File provenance and checksums.
- Units.
- Spectral fits.
- Dose conservation.
- Timing integration.
- Agreement between anatomical summary and detailed organ-dose files.
- Preservation of frozen radiation datasets.
- Simulator behavior.

Passing software tests establishes computational and data consistency.

It does not independently validate all underlying transport physics or medical outcomes.

The native corrected OLTARIS export provenance and exact historical GOES source matching were previously identified as areas needing verification.

Consult the current repository documentation to determine whether these have since been resolved.

---

## 19. Repository Architecture and Context

The repository has included the following major components:

- `sim/models.py` — Shared mission and astronaut models.
- `sim/mission_simulator.py` — Mission state progression, EVA execution, and exposure accumulation.
- `sim/strategies.py` — Strategy behavior.
- `sim/assumptions.py` — Mission assumptions.
- `sim/defaults.py` — Operational defaults and configurations.
- `anatomical_environment.py` — Anatomical dose environment and exposure integration.
- `run_strategy_a.py` — Strategy A execution.
- `data/processed/oltaris/` — Processed anatomical environment.
- `data/raw/` — Primary scientific source records.
- `charts/` — Radiation and analysis visualizations.
- `tests/` — Computational and consistency tests.
- `outputs/` — Simulation results, charts, reports, and diagnostics.
- `README.md` — Project documentation.

The exact file structure may have changed as work progressed.

The live repository is authoritative for code and implementation details.

### Architectural context

The project has discussed:

- One shared mission simulator.
- A dedicated qualitative engineering model.
- Nested mission and EVA decision policies.
- Four strategy-specific observation and decision configurations.
- Shared Bayesian inference infrastructure for Strategies C and D.
- A Monte Carlo experiment runner.
- Programmatically generated decision-tree diagrams.

Some components may be implemented, others partially implemented, and others conceptual.

**Do not infer implementation status from this conceptual history alone.**

A previous coding iteration created an entirely separate emergency-response simulator when the intended change was to integrate qualitative engineering considerations into the existing mission engine.

The preferred architecture avoids competing simulation engines or duplicated authoritative mission state.

The engineering model should influence the existing simulation, while the existing simulation remains responsible for physical state progression.

---

## 20. Scientific Questions We Want the Project to Answer

Beyond the immediate case recommendation, our work is exploring several questions:

**Radiation-aware scheduling:** How much can EVA timing reduce organ exposure without threatening spacecraft recovery?

**Forecast value:** How much operational improvement results from imperfect radiation forecasts?

**Biodosimetry value:** Does estimating past exposure biologically meaningfully improve subsequent crew selection and EVA decisions?

**Measurement timing:** When do more frequent or faster biological measurements become worth their operational complexity?

**Multimodal estimation:** Can combining measurements reduce uncertainty enough to change meaningful decisions?

**Engineering constraints:** How do reactor state, repair access, and system deterioration change the optimal recovery response?

**Propulsion dependence:** Are forecast-guided delays more practical for some NTP emergencies than NEP emergencies involving urgent heat rejection?

**Shielding sensitivity:** How much could improved EVA shielding change the practical feasibility of emergency repairs?

**Robustness:** Which strategies remain effective when forecasts, biomarker estimates, arrival times, and repair conditions are uncertain?

These are research questions, not predetermined conclusions.

---

## 21. Supporting Literature and Source Organizations

Important references and resources include:

**Jiggens et al. (2018), SAPPHIRE solar energetic particle environment modeling**

https://doi.org/10.1051/swsc/2018010

Used for the underlying solar proton environment and extreme-event spectral modeling.

**ESA SPENVIS**

https://www.spenvis.oma.be/

Used to obtain SAPPHIRE solar proton spectra and SHIELDOSE-2 reference calculations.

**NASA OLTARIS**

https://oltaris.nasa.gov/

Used for anatomical radiation transport simulations.

**NASA OMNIWeb**

https://omniweb.gsfc.nasa.gov/

Historical proton measurements and solar-event timing data.

**NASA-STD-3001**

NASA human-spaceflight standards, including organ radiation exposure limits.

**NASA and peer-reviewed biodosimetry literature**

Relevant subjects include γ-H2AX, lymphocyte kinetics, gene-expression responses, dicentric chromosome assays, and uncertainty-aware dose reconstruction.

**Official Western–CNL case materials**

The original case overview, competition launch slides, submitted team abstract, and live pitch guidelines should remain authoritative for scenario interpretation and judging requirements.

Published references should support their specific claims. Do not imply that a source validates assumptions or simulation outcomes that it does not actually address.

---

## 22. How to Interpret This Document

This document is a **comprehensive project-context reference**, not a specification requiring every idea to be implemented.

It contains:

- Official case facts.
- Our submitted proposal.
- Completed scientific modeling.
- Prior modeling errors and corrections.
- Architectural decisions.
- Research hypotheses.
- Proposed future capabilities.
- Known scientific limitations.
- Presentation and evaluation priorities.

These categories should remain distinct.

When working in this repository, use the actual code and current documentation to establish implementation status, and use this document to understand the motivation and intended scientific direction.

Exercise independent judgment when an earlier idea conflicts with stronger evidence, a newer implementation, or a more defensible model.

The project should remain technically credible, scientifically transparent, and focused on answering the CNL emergency-response challenge.

**Our central idea is not simply that more advanced biodosimetry is better. It is that better information may enable better emergency decisions—and we want to investigate when, why, and by how much.**
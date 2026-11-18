# Qualitative recovery verification

65 existing tests passed before implementation. All 82 tests passed afterward, including 17 dedicated
recovery tests; no skips. Existing legacy-PDF and pandas deprecation warnings remain nonfatal.

`integration.json` records 72 unchanged legacy mission states (comparison excludes only the two new
null recovery fields), eight successful real-environment recovery runs and hashes for all 90 protected
radiation/source artifacts. Those artifacts were not regenerated or altered. Recovery mode changes
schedules and exposure accumulation intentionally; legacy mode preserves the former behavior.

Tests cover engine-specific sequencing, shared hard interlocks, fractional-time hazards, failed repairs,
consumable use, conservation decisions, consent/qualifications/rest/workload, ground review, checkout,
continuation authority, hold/abandonment, restricted observations, horizon boundaries, task-keyed realized
outcomes, reproducibility and step-size consistency. This is implementation verification, not empirical
validation of the hypothetical recovery assumptions. See `docs/mission_recovery.md` at the project root.

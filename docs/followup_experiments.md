# Follow-up experiments: pending execution

These experiments extend the frozen classifier study. Results, including timing and area, are pending CI execution and independent audit. The original RTL, fixtures and archived results remain the reference.

## Overlap

The added two-lane engine captures each completed score and its class. It compares that saved pair while executing the first MAC beat of the following class. The last score is drained in a separate cycle, before the result is exposed. The intended no-gap schedule is 64 accepted input cycles, 320 MAC cycles, and one final drain: 385 cycles from accepted command to valid result. This is a schedule expectation, not yet a measured result. `scripts/check_overlap.sh` runs both frozen baselines, the full 359-frame score and prediction replay, and an intentionally broken-tag negative control. `eda/overlap_study.json` reuses the pinned mapping and gate replay machinery; `.github/workflows/overlap-study.yml` preserves timing, source, and replay evidence.

## Adaptive area

`scripts/area_attribution.py` maps the existing adaptive engine twice using the same pinned library and ABC target: the standard flattened map and a hierarchy-preserved diagnostic map. It recursively counts each physical standard-cell instance in the latter and groups module-owned cells into arithmetic, model tables, residual tables, preprocessing, and remaining top-level logic. The remaining bucket includes feature storage, interval checking and control; it must not be split by guesswork. Its grouped totals exactly sum to the hierarchy-preserved total. This diagnostic total can differ from the flattened one because preserving boundaries limits optimization; buckets are not assignments of flattened cells. These are mapped cell areas, not physical memory macro areas or layout results. The data are pending; no numeric breakdown or reason for a measured difference is asserted here.

## Synthetic scaling

`eda/synthetic_study.json` defines three shapes and identical deterministic signed feature, weight and bias fixtures for all three schedules. Unlike the production raw-pixel classifier, the synthetic engine stores already quantized signed operands and fixture weights locally, performs no pixel preprocessing or model inference, and exposes score signals for verification. Its initialized arrays and read logic are part of each synthesis run. Synthesis may specialize constant fixture contents and optimization may differ by shape or schedule. Do not infer model accuracy, adaptive precision benefits, or general scalability from this bounded sweep.

`bash scripts/check_synthetic.sh` checks class scores against an independent integer scoreboard, exact cycle counts, result stalls, reset cancellation, signed extreme operands, ties and final-class winners. `python scripts/map_synthetic.py` maps and directly tests setup brackets and a shared passing clock for each shape using the existing constraints; timing is not estimated if tools are missing. `.github/workflows/synthetic-area-study.yml` records source bundle, logs, and artifacts. Full execution and review are pending.

# FlexMAC follow-up: overlap, cost attribution, and bounded scaling

Status: executed and audited. See `docs/followup_experiments.md` and the archived audit records for verified results and limits. Terra drafted the implementation; the parent corrected audit findings and completed execution after Terra reached its usage limit.

## Objective

Strengthen the existing design study by answering three specific questions:

1. Can completed-class comparison overlap the next class's arithmetic without
   reintroducing the original accumulation-to-argmax timing path?
2. Which structures account for the implemented adaptive engine's area cost?
3. Does the scheduling tradeoff persist beyond the frozen 64-feature, ten-class
   workload?

Keep the current classifier, fixtures, original RTL, and archived results intact.
This work adds an experiment, not a new claim of accelerator novelty. The
standalone project remains in `C:/Users/User/Documents/FlexMAC`.

## A. Overlapping completed-score comparison

Add a distinct two-lane INT8 engine. Capture the completed score and class tag,
compare the saved score independently while beginning the next class, and drain
the final comparison before publishing the result. Establish the exact cycle
contract from the implemented schedule; do not assume all ten cycles disappear.

Preserve raw-input preprocessing, frozen weights/biases, signed 32-bit wrap,
lowest-index tie breaking, invalid-input handling, reset cancellation, and
backpressure semantics. A pending comparison must neither be lost nor repeated.

Verification must include all 359 existing calibration frames and internal class
scores; directed signed extremes, ties, first/last-class winners, reset during
overlap/final drain, input gaps, output stalls, and invalid inputs; and a
deliberately broken tag/final-drain negative control that fails an assertion.
Add full two-state and four-state mapped replay for the new engine when mapping
is available. Reuse the current matched baselines and source-hash checks.

Compare mapped area, directly tested setup brackets, cycles, and latency at both
each design's passing period and a directly verified common feasible clock.
Use the same pinned library, mapping target, I/O constraints, and timing method.
Inspect the new critical path. A smaller cycle count alone is not success.

## B. Adaptive-engine area attribution

Start with the existing flattened mapped totals and register/combinational split.
Obtain defensible attribution for arithmetic, residual/certificate tables,
feature storage, interval/checking logic, and remaining control where possible.

ABC and flattening can merge logic across conceptual boundaries. Do not assign
flattened cells to functions using unsupported guesses. A separate
hierarchy-preserved diagnostic mapping is acceptable if its cell totals
reconcile exactly, its grouping method is documented, and its total is compared
with the normal flattened mapping. Standalone block maps or ablations must be
explicitly labeled non-additive diagnostic estimates. Keep unattributed costs
visible. Never present logical ROM bits as physical memory area.

The deliverable is an auditable CSV/JSON plus a concise explanation of measured
costs, attribution limits, and why the adaptive design loses in this instance.

## C. Bounded synthetic scaling study

Use a separate parameterized two-lane signed-INT8 score engine with three
schedules: original terminal compare, separate compare cycle, and overlapped
compare. Keep the production frozen-classifier RTL unchanged.

Start with (features, classes) = (32, 4), (64, 10), (128, 10). Use identical
deterministic signed operand/weight/bias fixtures and identical storage/read-port
assumptions for all schedules at a shape. Include their real implementation
costs. Document any differences from the raw-input production engines. Do not
interpret these synthetic cases as model accuracy or evidence that adaptive
precision improves other workloads.

Use an independent behavioral scoreboard and meaningful protocol/arithmetic
corner cases. Measure cycles and mapped area/timing if the toolchain permits.
Report any synthesis-specialization effects and the limited scope of this small
sweep. Do not silently substitute estimated timing for an executed analysis.

## Delivery and audit gates

1. Implement RTL, tests, experiment manifests, and reproducible runners.
2. Run the available local checks; obtain EDA evidence through a dedicated
   experiment branch/CI if local EDA is unavailable. Preserve logs and exact
   source/tool hashes. Never mark a blocked check as passed.
3. The implementation agent reports changed files, actual commands/results,
   limitations, and any proposed deviations. It does not publish to main.
4. The parent independently audits the code, test sensitivity, metrics,
   provenance, comparison fairness, and claims. Fix findings and rerun affected
   checks before integrating.
5. Update the README, experiment docs, diagrams/plots, and the native IEEEtran
   report only with verified findings. Rebuild and visually inspect the report
   if its content changes. Preserve historical results and the source archive.

No FPGA deployment, tapeout, power claim, new trained model, or physical design
flow is required. Python is limited to orchestration, evidence parsing, and
figures; hardware behavior and new testbenches stay in Verilog/SystemVerilog.

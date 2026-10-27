# Verified RTL classifier results

Historical classifier milestone. See the later [precision-agreement results](precision_results.md)
for complete fixed baselines, adaptive inference and current generic counts.

[CI run 40447266654](https://github.com/jrmywm/FlexMAC/actions/runs/40447266654)
passed at source `1cd283c2938b7d13cba5ac79f2f5237b6cc21055`.
The frozen model and arithmetic contract are documented in [classifier.md](classifier.md).

## Inference result

| Model | Correct / 360 | Accuracy | Drop from float | Accuracy budget |
| --- | ---: | ---: | ---: | --- |
| Floating reference | 345 | 95.83% | -- | Reference |
| RTL INT8, both implementations | 345 | 95.83% | 0.00 pp | Pass |
| RTL INT4, both implementations | 341 | 94.72% | 1.11 pp | **Fail** |

Both Verilog implementations reproduced every expected integer class score,
winning score and class prediction. Equal accuracy does not imply that INT8 and
float make exactly the same predictions. INT4 fails the predeclared maximum
one-percentage-point loss; its model is retained without tuning to this test set.
The 360-image project split is small, so these results do not establish general
accuracy or a statistically significant difference between precisions.

## Measured cycles

| Mode | Feature bytes | Evaluation cycles | Command to result, no gaps | With testbench input gaps |
| --- | ---: | ---: | ---: | ---: |
| INT8 | 64 | 640 | 704 | 714 |
| INT4 | 32 | 320 | 352 | 357 |

The two hardware implementations have identical cycle counts. The testbench
inserts one input gap every seven beats for every eleventh image. It also stalls
each output for three cycles; these stalls occur after result-valid and are not
included in command-to-valid latency. Host quantization and idle command/result
cycles are excluded. These are simulation cycle counts, not measured latency
in nanoseconds, sustained inferences per second or an energy result.

INT4 uses half as many compute and load cycles here. That potential benefit
comes with an accuracy-budget failure. A common feasible clock has not been
established, so a twofold cycle reduction is not a proven twofold speedup in time.

## Verification coverage

- 360 images x two precisions x two implementations: 1,440 inferences.
- Ten checked class scores per inference: 14,400 integer score comparisons.
- Both modes alternate on the same engine; command mode is captured despite
  later host changes. Input gaps, output stalls and invalid-result masking pass.
- Six reset cancellations per implementation: partial loading, active evaluation
  and pending output, each in both modes, followed by fresh inference.
- A controlled ROM verifies all-negative tied scores and signed ordering of a
  positive winner against negative scores. Lowest class index wins a tie.
- An unsigned-argmax mutation compiles, then fails the directed check as required.
- Existing exhaustive product, stream, overflow and sign-bug tests still pass.
- Nine standard-library Python tests pass, including fixture hashes and split
  integrity. Python does not execute the classifier during RTL replay.

These are exhaustive product checks and sampled sequential tests, not a formal
proof of all possible control sequences.

## Generic synthesis

Yosys 0.33, flattened `synth -noabc`, including both model ROM banks, feature
storage and controller:

| Classifier | Generic cells | Register cells |
| --- | ---: | ---: |
| Shared product implementation | 3,965 | 601 |
| Separate-unit mux implementation | 3,861 | 601 |

The shared implementation uses 104 more generic cells, about 2.7%. It does not
show a logic-count benefit. Generic gates have unequal physical costs, so this
does not establish the sign or magnitude of a mapped-area difference. Both
precision models exist simultaneously, and selecting INT4 does not remove the
INT8 ROM bank or halve total classifier area.

The archived CSV includes all eight experiments. Reading the added ROM source
also perturbed several older generic counts despite unchanged arithmetic RTL.
The synthesis script subsequently preserves the original source list for the
six arithmetic experiments; use each run's exact inputs and archived CSV rather
than mixing counts from different flows. Classifier source lists are unchanged.

## Evidence and next step

The compact snapshot in [data/classifier](data/classifier/) records CSVs, logs,
source hashes, tool versions and provenance. The raw CI artifact also contains
netlist JSONs and a credential-free source bundle. Text in the committed snapshot
is normalized to UTF-8/LF; `provenance.json` hashes those committed bytes.

Next: map both product cores and complete classifiers into the same standard-cell
library, constrain them identically, verify mapped arithmetic, and test a common
feasible clock. Only then compare physical area and elapsed inference latency.
Power and energy remain unmeasured.

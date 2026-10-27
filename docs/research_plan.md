# Goal and evaluation plan

## Useful question

Can a small classifier use lower-precision arithmetic to reduce hardware cost or
execution time while staying within a defined accuracy budget? How much extra
hardware does runtime support for both INT8 and INT4 require?

The project compares fixed INT8, fixed two-lane INT4, a duplicated-unit mux, and
a shared partial-product core. Arithmetic correctness is a prerequisite. Lower
area, shorter inference time, and adequate INT4 accuracy are hypotheses, not
promised outcomes. Precision is selected externally; this is configurable
arithmetic, not automatic adaptation.

## Milestones, completed as quickly as verification allows

| Milestone | Deliverable | Completion evidence |
| --- | --- | --- |
| 1. Arithmetic foundation | Four cores, framed accumulator, mathematical oracle, exhaustive/stream tests | Passing Icarus tests, negative control, generic synthesis logs |
| 2. Real workload | Small fixed classifier with float, INT8 and INT4 evaluation | Reproducible splits, quantization contract, held-out predictions, RTL dot products |
| 3. Implementation study | Library mapping and constrained timing for fair baselines | Library/tool hashes, identical assumptions, common-clock feasibility and mapped replay |
| 4. Explanation | Schematics, useful-work/cycle plots, accuracy-cost table, write-up | Regenerable artifacts and bounded claims |

Seven days is a planning estimate, not a waiting period. Each milestone advances
when its evidence passes. No result is marked complete because a script exists.

Milestone 1 passed in [CI run 40445230045](https://github.com/jrmywm/FlexMAC/actions/runs/40445230045).
The [initial report](initial_results.md) records the verification and the first
generic counts, which do not show a sharing benefit. Milestone 2 now has a frozen
model and classifier RTL awaiting CI replay; see [the workload contract](classifier.md).
INT4 misses the declared accuracy budget in the offline model evaluation.
Milestones 3-4 remain open.

## Workload contract to freeze before measuring accuracy

Frozen benchmark: the small 8x8 handwritten-digit dataset available through
scikit-learn, using a linear classifier so its arithmetic is a manageable set of
dot products. This is a kernel study, not a complete CNN accelerator.

- Keep a reproducible stratified training/calibration/test split with a recorded seed.
- Fit on training data and choose quantization settings using calibration data only.
- Evaluate the frozen float/INT8/INT4 models on the same held-out test samples.
- Target accuracy degradation of no more than one percentage point relative to
  the floating-point reference. Report a failure to meet this budget if it occurs.
- Specify scaling, clipping, rounding, bias handling, accumulator width, and padding.
- Distinguish arithmetic verification (bit-exact integer results) from the
  model's prediction accuracy after quantization.
- Host quantization is outside the RTL; bias addition and argmax are implemented
  in Verilog. Count only implemented hardware operations in accelerator measurements.

## Fair comparisons

Use the same operand encodings, accumulator width, input/output contract, clock
constraints, library corner, and loading. Separate product-core cost from engine
cost. Fixed cores support one mode; they are not runtime substitutes for a core
supporting both. The mux baseline measures duplication; the shared core may or
may not improve it after mapping and control overhead.

Report mapped area, feasible clock period, cycles, accepted operand bytes, useful
scalar products, and results per workload. Two INT4 products per cycle is an
arithmetic capability, not proof of twice the inference speed. Generic cells
are not physical area; uncharacterized VCD activity is not power.

## Prior art and limits

Precision-configurable computation is established. See
[Bit Fusion](https://arxiv.org/abs/1712.01507) and the
[NVDLA architecture](https://nvdla.org/hw/v1/hwarch.html).
The contribution is an independently explainable implementation and a measured
accuracy/implementation tradeoff. Initial verification is simulation, not formal
proof. Fabrication, FPGA deployment, full CNN support, automatic mode selection,
and measured power are outside the initial scope.

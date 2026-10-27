# Verified precision-agreement results

Historical adaptive milestone. The later [two-lane INT8 comparison](two_lane_int8.md)
finds fewer cycles and fewer generic cells with ordinary parallel INT8; follow
that report for the generic comparison. The later [mapped study](mapped_study.md)
confirms the two-lane engine's area and elapsed-latency advantage under one
pre-layout SKY130 corner and constraint set.

[CI run 40463259340](https://github.com/jrmywm/FlexMAC/actions/runs/40463259340)
passed at source `87025fa4b300500b79804eac226ea4d7e33ea256`.
The [adaptive RTL contract](adaptive.md) and [bound derivation](agreement_study.md)
define the experiment. The evidence snapshot is under [data/precision](data/precision/).

## Main finding

The input-conditioned certificate works in the RTL prototype: both configurable
product implementations accept 351 of 359 calibration inputs without an INT8
rerun, use INT8 for the other eight, and return the INT8 reference class on all
359. The models and their original splits are unchanged.

The price is substantial: about 9.4 times the generic logic of the matched
always-INT8 raw-input baseline. Average command-to-result cycles fall by about
42%, but the longest inference takes more cycles. Physical clock periods, mapped
area and power have not been measured. This is an explicit area/latency tradeoff,
not evidence that the adaptive engine is a better accelerator overall.

These are calibration results used during design development, not a new held-out
accuracy result. Agreement with INT8 is not correctness against digit labels.
No adaptive inference on the original test set was performed.

## Adaptive cycles and generic cost

Yosys 0.33, flattened `synth -noabc`, no remaining non-elementary cells or latches:

| Engine, same raw-input interface | Generic cells | Register cells | Mean cycles, no gaps | Worst cycles, no gaps |
| --- | ---: | ---: | ---: | ---: |
| Always-INT8 | 2,859 | 409 | 704.00 | 704 |
| Adaptive, shared product | 26,837 | 1,128 | 408.26 | 1,034 |
| Adaptive, mux product | 26,738 | 1,128 | 408.26 | 1,034 |

Both adaptive implementations have identical per-image decisions, fallback flags
and cycle counts. A certified image takes 394 cycles: 64 to load raw pixels,
320 for INT4 scores and simultaneous interval accumulation, and ten to check
the certificate. A fallback adds a 640-cycle INT8 pass using the retained input.
No host retransmission is needed. The common raw-input baseline includes the
same input range checks, preprocessing LUTs, buffering and result interface.

The no-gap mean is `(351*394 + 8*1034)/359 = 408.26`. The actual testbench adds
ten input-gap cycles to 33 of the 359 frames. Its measured CSV means are 409.18
for adaptive and 704.92 for always-INT8. The no-gap means remove exactly those
known injected gaps; each per-frame latency is checked by the Verilog bench.
Three output-stall cycles per frame occur after result-valid and are excluded.
Idle/command turnaround between frames is also outside this latency measure.

The worst-case adaptive path takes 46.875% more cycles than always-INT8. A common
feasible clock has not been established. The residual-ROM/adder path can reduce
clock frequency, so fewer cycles do not establish a proportional reduction in
elapsed time. Generic cells are not standard-cell area, and their unequal
physical costs prevent treating the 9.4x count ratio as a silicon-area ratio.

## Why the compact checker was insufficient

The separate constant pairwise-threshold checker uses 878 generic cells and 44
register cells. It certifies 456/1,078 training inputs and 134/359 calibration
inputs. On calibration, serial INT4-then-INT8 computation alone would average
721.11 cycles, exceeding 640 for INT8 before loading/checking overhead.
Its low cost therefore does not yield a useful serial speedup here.

The tighter conditioned method costs more because it looks up two residual
ranges per INT4 beat, accumulates both interval endpoints, stores ten lower/upper
score pairs, scales class scores, and checks the winning interval. The frozen
ROM has 9,600 used entries containing two signed 13-bit values. The complete
address table also includes conservative defaults. This implementation has not
been decomposed into exact ROM, arithmetic and control area contributions.

The case-table and constant-memory ROM representations both passed the full
adaptive regression. The constant-memory representation makes simulation much
faster. The exact frozen address contents are checked by the unit tests; generic
counts differ slightly across the representations, so use this run's CSV.

## Complete fixed classifiers

These use the earlier quantized-feature interface, which differs from the
raw-input adaptive interface above. Do not mix their cell counts into the raw
baseline comparison without accounting for that frontend difference.

| Quantized-feature classifier | Generic cells | Register cells | Existing test result |
| --- | ---: | ---: | --- |
| Fixed INT8 | 3,287 | 600 | 345/360 correct, 704 cycles without gaps |
| Fixed INT4 | 2,062 | 343 | 341/360 correct, 352 cycles without gaps |
| Runtime shared | 3,958 | 601 | Both models reproduced |
| Runtime mux | 3,854 | 601 | Both models reproduced |

The fixed INT4 design has a 32-byte feature bank and one model precision. Fixed
INT8 has a 64-byte bank. Runtime designs retain both model precisions and use
the same 32-bit accumulation contract. Their overhead includes storage and
control as well as arithmetic; it must not all be attributed to the MAC core.
The original INT4 model still misses the one-percentage-point accuracy budget.

## Verification evidence

- Twelve standard-library unit tests pass, including frozen hashes, exact bound
  reconstruction, minimum-attaining pixel vectors, and every residual-ROM entry
  including defaults.
- Existing exhaustive product and stream/overflow checks still pass.
- Four quantized-feature classifier variants check 21,600 class scores across
  the original frozen test frames, including input gaps, stalls and resets.
- The compact checker verifies 1,437 training/calibration score streams, 180
  threshold boundaries, invalid/mismatched candidates, full signed differences,
  stalls and resets. An off-by-one comparator mutation is rejected.
- Two adaptive variants and the matched raw INT8 baseline check all 359
  calibration images, every computed class score, interval containment where
  applicable, exact accept/rerun decisions, and cycle counts.
- The adaptive bench cancels loading, INT4 computation, certificate checking,
  INT8 fallback and pending output. It rejects invalid pixels at both the first
  and last input positions and checks output backpressure.
- All fourteen synthesis experiments pass structural checks. Gate-level replay
  and formal verification of all RTL control sequences have not been performed.

The bound is an analytical certificate for the stated raw-pixel domain, frozen
models and exact preprocessing. Simulation checks its hardware implementation
on these fixtures; this does not amount to a formal proof of the entire RTL.

## Next engineering decision

The working prototype exposes the cost of certification. The highest-value
next investigation is reducing its ROM/arithmetic overhead, followed by matched
library mapping and timing to establish whether any useful elapsed-time benefit
survives. Retain this verified version as the reference. Do not claim novelty
for adaptive precision or certification itself, or tune against the already
inspected original test set.

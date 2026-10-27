# Precision-fallback feasibility study

## Question and current conclusion

Can the hardware accept an INT4 decision only when a conservative check proves
agreement with the frozen INT8 classifier, then rerun uncertain inputs in INT8?

The compact pairwise check accepts 134/359 calibration inputs (37.33%). For a
serial INT4-then-INT8 design, this is too few: computation alone averages 721.11
cycles against 640 for always-INT8, before checking or loading overhead. It is
therefore a verified candidate block to evaluate, not a demonstrated accelerator.

An input-conditioned alternative accepts 351/359 calibration inputs (97.77%) in
the offline study. It now has an [adaptive RTL prototype](adaptive.md), pending
CI verification and cost measurement. The direct residual-table
representation has 19,200 scalar entries; that is a representation size, not a
lower bound on circuit area. The prototype deliberately makes the certificate's
cost explicit so it can be measured against an always-INT8 raw-input baseline.

The original floating/INT8/INT4 models, quantization settings and split remain
unchanged. This study uses training and calibration samples only. It does not
select test samples or use test labels. Because the original test set has already
been inspected, any later adaptive evaluation on it must be labeled reuse of
the existing benchmark, not fresh independent validation.

## Complete fixed-precision baselines

`flexmac_classifier` now has `FIXED_MODE=-1` for runtime selection, 0 for fixed
INT8 and 1 for fixed INT4. The fixed versions instantiate the corresponding fixed
product core. A constant ROM mode permits removal of the unused precision bank;
the fixed INT4 feature bank has 32 bytes instead of 64. Accumulators remain 32
bits so the precision comparison is not mixed with a width optimization.

`rtl/flexmac_classifier_fixed.v` provides fixed top modules with no mode input.
Tests run every existing held-out image through both fixed parameterizations,
checking all class scores, decisions, cycle counts, stalls and reset cancellation.
That is regression testing of the already-frozen models, not adaptive tuning.

## Exact pairwise derivation

The supported domain is 64 independent raw integer pixels in [0,16]. Define
`x8(p)=round_even((p-8)*127/8)` and `x4(p)=round_even((p-8)*7/8)` using the frozen
preprocessing. Let `S8[c]` and `S4[c]` be each class's integer scores including
their independently quantized biases. Both input encodings must originate from
the SAME raw pixel vector. Arbitrary unrelated INT4 and INT8 inputs are outside
the guarantee.

Choose positive integer K=366, the rounded ratio of the two frozen score scales.
This choice affects tightness; the algebra below is sound for any positive K.
For candidate c and competitor j:

```
R[c,j,i,p] = x8(p)*(w8[c,i]-w8[j,i]) - K*x4(p)*(w4[c,i]-w4[j,i])
L[c,j] = b8[c]-b8[j] - K*(b4[c]-b4[j]) + sum_i min_{p in 0..16} R[c,j,i,p]
S8[c]-S8[j] >= K*(S4[c]-S4[j]) + L[c,j]
T[c,j] = floor(-L[c,j]/K) + 1
```

If `S4[c]-S4[j] >= T[c,j]` for EVERY j != c, then `S8[c] > S8[j]`
for every competitor. Thus c is the unique INT8 winner. Strict superiority is
conservative and avoids tie ambiguity. The minima are separable across pixels,
so summing them gives a valid bound over the whole stated input domain; it
does not rely on calibration percentiles, labels or a confidence heuristic.

The affine residual absorbs all differences in input quantization, weight
clipping, weight quantization and bias scales. The hardware never directly
compares unscaled INT4 and INT8 scores, and it needs no floating-point arithmetic
or runtime multiplication by K.

Unit tests reconstruct the frozen bounds, check the threshold transformation at
both sides of its boundary, and construct a pixel vector attaining the exact
pairwise minimum for every class pair. This supports the mathematical derivation;
it is not a formal proof of the RTL's sequential behavior.

## Standalone RTL checker

`rtl/flexmac_agreement.v` captures a candidate class and its INT4 score, then
accepts ten INT4 scores in class order 0..9. For each competitor it reads the
threshold ROM and compares a signed 33-bit score difference. The candidate's
streamed score must match its captured score, and an invalid class is rejected.
The result remains stable under backpressure. Reset cancels partial and pending
checks, and invalid output is masked.

Ten accepted score beats are required after the command; gaps and output stalls
extend the transaction. The checker assumes scores were computed correctly by
the frozen model from supported inputs. It certifies a class decision, not
digit correctness or equality of logits, probabilities or scores.

The checker is tested independently by streaming frozen training/calibration
scores. It is not yet wired into an adaptive classifier. No full adaptive
inference latency, accuracy, mapped area or energy claim is made.

## Training/calibration screening

| Certificate | Training accepted / 1,078 | Calibration accepted / 359 | Implementation |
| --- | ---: | ---: | --- |
| Separate global class intervals | 84 (7.79%) | 31 (8.64%) | Offline screening only |
| Constant pairwise thresholds | 456 (42.30%) | 134 (37.33%) | Standalone RTL checker |
| Input-conditioned class intervals | 1,070 (99.26%) | 351 (97.77%) | Adaptive RTL prototype; CI pending |

No accepted decision disagrees with INT8 on these samples. This observed check
is separate from the domain-wide mathematical bound. Bounds are not a guarantee
against hardware faults, incorrect score generation or unsupported preprocessing.

Global intervals bound each class's residual independently. Pairwise thresholds
bound differences directly, retaining cancellation between classes. The tighter
conditioned method restricts each residual minimum/maximum to raw pixels with
the observed INT4 encoding. All alternatives were screened on the same frozen
training/calibration split without modifying the models or consulting test data.

## Cycle feasibility, not a measured adaptive implementation

For fallback fraction r, serial compute cycles are `320 + 640*r`.
The necessary compute-only break-even condition against 640 cycles is r < 0.5.
The pairwise calibration fallback fraction is 225/359 = 62.67%, which already
fails before extra hardware is considered.

An optimistic input-and-check projection is `64 + 320 + 10 + 640*r`, or 795.11
cycles on calibration, versus 704 for the existing INT8 classifier without
input gaps. This assumes one initial 64-byte input buffer, free conversion to
both precisions and no additional replay, command or controller-transition
costs. Those assumptions have not been implemented. Connecting the current
modules through separate load interfaces would cost more.

The conditioned method's calibration compute projection is 334.26 cycles before
all bound-hardware and loading costs. This is promising screening evidence,
not a measured latency or area result. Do not substitute the compact checker's
cost for the unimplemented conditioned method's cost.

## Reproduction and next decision

Normal verification needs no training libraries:

```bash
python -m unittest discover -s tests -v
bash scripts/check_classifier.sh
bash scripts/check_agreement.sh
python scripts/check_synthesis.py
```

The agreement bench checks 1,437 training/calibration score streams, all 90
class-pair thresholds on both sides of their exact boundary, invalid and
mismatched candidates, full-range signed differences, input gaps, output stalls
and reset cancellation. A compiled off-by-one threshold mutation must fail.
Fixed-classifier replay adds 720 inferences and 7,200 checked class scores to the
previous configurable-classifier regression.

To regenerate only the offline screening, use the pinned optional dependencies
from `model/requirements.txt` and run `python scripts/study_agreement.py`.
`model/agreement/feasibility.json` records source/fixture hashes and the exact
thresholds. Do not run `export_digits.py` to change or retrain the frozen models.

The next prototype uses input-conditioned bounds because the compact checker
does not justify serial fallback for speed. Measure its actual hardware cost
alongside its cycle behavior; see [adaptive.md](adaptive.md).
Library mapping is still required for physical
area and timing; generic cells alone cannot decide the final tradeoff.

Certified quantization and precision refinement have prior art; this is not a
claim of algorithmic novelty. See [quantization-robust inference](https://proceedings.mlr.press/v258/dang25a.html).

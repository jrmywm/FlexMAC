# Two-lane INT8 baseline

## Purpose

The adaptive engine spends substantial hardware on a certificate to avoid some
INT8 work. This baseline asks whether spending additional hardware on ordinary
INT8 parallelism is a better choice for the same frozen linear classifier.

It uses the same raw-pixel interface, 64-pixel buffer, preprocessing LUTs,
input-range checks, bias/accumulator widths, signed argmax, reset semantics and
result handshake as the single-lane raw INT8 baseline. The frozen model and
calibration fixtures are unchanged. No test-set evaluation or tuning is added.

## Implementation

`flexmac_adaptive` with `FORCE_INT8=1, INT8_LANES=2` evaluates two adjacent
features per clock. Two INT8 multipliers feed a signed 17-bit sum and the existing
32-bit accumulator. Both low/high pixel read ports and quantizers are used. A
second constant-model read supplies the adjacent INT8 weight; its logic cost is
included in full-engine synthesis. No residual ROM or certificate is instantiated.

```
term = signed8(feature[2*k]) * signed8(weight[2*k])
     + signed8(feature[2*k+1]) * signed8(weight[2*k+1])
score[class] = quantized_bias[class] + sum(term[k], k=0..31)
```

The product sum must represent +32768 for two (-128)*(-128) products. It is
therefore signed 17 bits, extended to 32 before accumulation. The model itself
does not use the full negative endpoint, but the arithmetic block supports it.
Integer regrouping preserves the original 32-bit score and wrap semantics.

There are 32 compute beats per class and ten classes. Expected command-to-valid
latency is 64 loading cycles plus 320 computation cycles = 384 cycles without
input gaps. This is an implementation target pending CI confirmation, not a
measured elapsed-time improvement. The extra sum may affect the critical path.

The parameter applies only to the always-INT8 baseline. Adaptive INT8 reruns
remain single-lane, preserving the existing experimental reference. Default
parameter values preserve the previous single-lane and adaptive behavior.

## Checks and measurement

Run `bash scripts/check_adaptive.sh`. The Verilog product bench checks 4,096
combinations of signed-boundary values against native integer arithmetic. This
is a boundary grid, not an exhaustive test of all four input bytes. A temporary
16-bit-intermediate mutation must compile and then fail the checker.

The classifier bench checks all ten INT8 scores and the final class on every
one of the same 359 calibration inputs. It verifies exact cycles, input gaps,
result stalls, first/last invalid pixels and reset during loading, computation
and pending output. The existing adaptive and single-lane regressions also run.
This is calibration replay for an implementation comparison; it is not fresh
held-out accuracy evidence or a formal proof of all control sequences.

`python scripts/check_synthesis.py` includes the new engine alongside all prior
designs in the same flow. The complete cost includes parallel arithmetic,
quantization, weight reads, storage and control. Use one run's generic CSV for
comparisons; do not mix it with historical numbers from different source sets.
Library mapping and a common feasible clock remain necessary before comparing
physical area and elapsed inference time. Results will be recorded after CI.

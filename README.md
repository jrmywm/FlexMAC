# FlexMAC

**Precision-configurable arithmetic for quantized AI inference.**

FlexMAC investigates when INT4 computation is useful compared with INT8 for a
small classifier: does it meet an accuracy budget, and what area/latency cost
comes with supporting both modes? The contribution is the verified implementation
and evaluation; configurable precision itself is an established technique.

## Current implementation

- A shared partial-product core: one signed INT8 product, or two signed INT4
  products summed per beat.
- Fixed INT8 and dual-INT4 reference cores, plus a separate-unit mux baseline.
- A streaming 32-bit dot-product accumulator with captured precision mode,
  input-valid gating, output backpressure, and reset cancellation.
- An independent Python arithmetic model, exhaustive product vectors, framed
  tests including signed overflow, and a deliberately rejected sign-bug control.
- A ten-class, 64-feature digit classifier: feature storage, frozen weight ROM,
  bias addition, accumulation and signed argmax in Verilog, in both precisions.
- Verilog classifier tests against frozen held-out scores, with reset/stall tests
  and a deliberately rejected unsigned-argmax control.

The [arithmetic specification](docs/specification.md) defines every width,
signed interpretation, handshake, and wrap behavior. The shared and mux engines
must return identical results for identical frames.

**Status:** the [first RTL verification run](https://github.com/jrmywm/FlexMAC/actions/runs/40445230045)
passed 131,072 product vectors, 172 frames per stream implementation, reset and
overflow checks, a rejected sign-bug control, and six generic synthesis checks.
The first generic result does **not** favor sharing: 732 cells for the shared
product versus 650 for the separate-unit mux. See the [initial results](docs/initial_results.md).
The frozen classifier model gives 345/360 correct in float and INT8, and 341/360
in INT4. The INT4 drop of 1.11 percentage points **misses** the one-point budget.
Both RTL implementations reproduced all 14,400 checked class scores in
[passing CI](https://github.com/jrmywm/FlexMAC/actions/runs/40447266654).
Without input gaps, INT8 takes 704 cycles per image and INT4 takes 352.
The current shared classifier uses 3,958 generic cells versus 3,854 for the mux
baseline, so sharing does not show a logic-count benefit here either.
See the [verified classifier results](docs/classifier_results.md) and
[classifier contract and methodology](docs/classifier.md).
Mapped area, constrained timing, and power results are not available yet.
Generic counts alone establish none of those claims.

## Precision-fallback investigation

Complete fixed-INT8 and fixed-INT4 classifier baselines and a standalone
conservative INT4/INT8 agreement checker passed CI. The frozen
training/calibration study finds a real limitation:
the compact checker accepts only 134/359 calibration inputs, so serial fallback
would be slower than always-INT8. Tighter input-dependent bounds accept 351/359
offline, and the adaptive RTL reproduces this result: 351 certified inputs,
eight INT8 reruns, and agreement with INT8 on all 359 calibration images.
Mean latency without input gaps is 408.26 cycles versus 704 for the matched
always-INT8 raw-input baseline. **The cost is about 9.4x the generic logic.**
The worst-case path takes 1,034 cycles. Neither mapped-area nor elapsed-time
improvement has been established. See the [verified precision results](docs/precision_results.md).
See [the agreement derivation and feasibility study](docs/agreement_study.md).
The [adaptive hardware contract](docs/adaptive.md) explains input preservation,
on-chip preprocessing, certification and fallback.

## Run the checks

Python 3.10+ is sufficient for the independent model:

```text
python -m unittest discover -s tests -v
```

With Icarus Verilog (`iverilog`, `vvp`) and Yosys on PATH:

```text
python scripts/check_rtl.py
python scripts/check_synthesis.py
bash scripts/check_classifier.sh
bash scripts/check_agreement.sh
bash scripts/check_adaptive.sh
```

The RTL script generates 65,536 operand pairs per mode, tests both stream
implementations against the oracle, and requires a temporary INT4 sign bug to
fail its decision check. Stream tests include real 32-bit overflow in both
directions. A missing tool produces BLOCKED, not a passing RTL result.
`--generate-only` generates vectors without running simulation.

CI runs on Ubuntu with lightweight open-source tools. Reports, source hashes,
logs and a credential-free source bundle are uploaded as `flexmac-verification`.
Build outputs are ignored under `build/`. No FPGA vendor suite is required.

## What we will measure

| Question | Required evidence |
| --- | --- |
| Is the integer arithmetic correct? | Exhaustive products and oracle-checked streamed sums |
| Does INT4 preserve enough accuracy? | Frozen quantization and a held-out classifier test set |
| Is useful work faster? | Measured frame cycles and feasible timing, including delivery/control overhead |
| Can adaptive precision preserve INT8 decisions? | Exact agreement bounds, RTL calibration replay and full checker cost |
| Does sharing save area? | Same-library mapping against fixed and duplicated-unit baselines |

The accuracy target is at most one percentage point below the floating-point
reference on the same test set. INT8 meets it; the frozen INT4 model misses it.
The [milestone plan](docs/research_plan.md) fixes the methodology and scope;
milestones can finish sooner than the original one-week estimate.

## Scope

This is a small linear-inference RTL project. The original classifier accepts
host-quantized features. The adaptive engine accepts raw pixels and implements
quantization, certification and INT8 fallback in Verilog. Training and frozen
model preparation remain offline. It has not demonstrated a fabricated chip,
FPGA execution, or measured energy savings. INT4 arithmetic sums two lanes into
one dot-product term. The adaptive controller selects precision internally;
the original interface accepts an external mode. Established work such
as [Bit Fusion](https://arxiv.org/abs/1712.01507) motivates the comparison.

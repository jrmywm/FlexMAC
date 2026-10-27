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

The [arithmetic specification](docs/specification.md) defines every width,
signed interpretation, handshake, and wrap behavior. The shared and mux engines
must return identical results for identical frames.

**Status:** initial implementation and verification flow. Check the completed
[Verify FlexMAC workflow](https://github.com/jrmywm/FlexMAC/actions/workflows/verify.yml)
for actual RTL results. Classifier accuracy, mapped area, constrained timing,
and power results are not available yet. Generic synthesis alone establishes
none of those claims.

## Run the checks

Python 3.10+ is sufficient for the independent model:

```text
python -m unittest discover -s tests -v
```

With Icarus Verilog (`iverilog`, `vvp`) and Yosys on PATH:

```text
python scripts/check_rtl.py
python scripts/check_synthesis.py
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
| Does sharing save area? | Same-library mapping against fixed and duplicated-unit baselines |

The accuracy target is at most one percentage point below the floating-point
reference on the same test set. It is a target, not an achieved result.
The [milestone plan](docs/research_plan.md) fixes the methodology and scope;
milestones can finish sooner than the original one-week estimate.

## Scope

This is an AI arithmetic-kernel project. It has not yet demonstrated a complete
classifier in hardware, a fabricated chip, FPGA execution, or measured energy
savings. INT4 mode is externally selected and sums two lanes into one dot
product; it does not return two independent accumulations. Established work such
as [Bit Fusion](https://arxiv.org/abs/1712.01507) motivates the comparison.

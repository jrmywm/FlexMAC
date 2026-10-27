# Library-mapped comparison: method

The RTL architectures and frozen models are unchanged. This flow maps the four
raw-input engines into one characterized standard-cell library and tests whether
the generic-cell/cycle conclusions survive technology mapping. The flow is
implemented; results are pending its first complete CI execution.

## Fixed tools and library

`eda/toolchain.json` pins OpenSTA, CUDD, the SKY130 HD typical-corner library and
all optimization/timing assumptions. The library is the OpenSTA example
`sky130hd_tt.lib.gz`: SKY130 `sky130_fd_sc_hd__tt_025C_1v80`, 25 C and 1.80 V.
Its compressed SHA-256 is
`210e56be3a3a0907b5241a34d277f664cf4b4d91dcb49a27ff813df4406a5889`.
The original and modified library hashes, source hashes and tool versions are
recorded with each run. CI builds timing tools on Linux; no local vendor FPGA
suite or full PDK installation is needed.

Library units are checked explicitly: ns and pF. Cells in the lpflow/probe
families are excluded from mapping. Liberty wire-load tables, selections and
default wire-load settings are removed from the analysis/mapping copy. Thus the
ideal-wire assumption is explicit, rather than relying on each tool's implicit
handling of library defaults. Cell timing and pin capacitance tables remain.
The original library is retained unchanged in the pinned tool checkout.

## Mapping

All four configurations use `synth -flatten -noabc`, `dfflibmap`, then one
Liberty-based ABC mapping with a 10 ns optimization target. ABC's constraint
uses `buf_2` input driving and 10 fF load. The target is optimization effort,
not evidence that a 10 ns clock is met. There is no RTL pipelining, retiming
request, arithmetic change or model retraining in this experiment.

Every mapped cell must be a known member of the pruned library. Area is the sum
of characterized cell areas, reported in the SKY130 library's square-micrometre
convention. Sequential and combinational contributions and cell counts are
separated. These are cell areas, not placed core/die area or routing utilization.

## Timing constraints

Each netlist is linked in OpenSTA with one clock and the same SDC template:

- Ideal clock, setup uncertainty 0.10 ns, hold uncertainty 0 ns.
- Input/output maximum external budgets: 20% of the tested clock period each.
- Input/output minimum delays: 0 ns.
- `sky130_fd_sc_hd__buf_2`, output pin X, for data-input driving.
- 0.010 pF (10 fF) output load. ABC uses 10.0 because its constraint load unit is fF.
- Reset is synchronous data and is timed. No false paths or multicycle paths.
- No extracted wires, placement, clock tree, package model or clock skew.

The script checks STA errors and incomplete-constraint diagnostics, requires
register-to-register paths, and cross-checks the four path classes against the
global worst setup slack. A deliberately tight 0.25 ns clock must fail.

The setup limit is bracketed by repeated COMPLETE STA runs with regenerated
I/O budgets. The bracket has a failing lower endpoint and directly tested
passing upper endpoint, at most 0.05 ns apart. It is not inferred by subtracting
one slack from a clock period. It is a setup-period bracket under these
assumptions, not a signoff maximum frequency.

A common clock is selected by rounding 110% of the largest passing bracket
endpoint up to the next 0.5 ns. Every SAME mapped netlist is then analyzed again
at that exact period, with direct setup and hold checks. Max-slew/capacitance
violators are reported too; positive setup/hold slack does not establish full
electrical closure if those constraints fail.

Both common-clock latency and each design's latency at its own tested passing
period are recorded. Cycles come from the same 359-image calibration replay;
known injected input gaps are removed from the no-gap latency statistic.
Result stalls after valid and idle command turnaround are excluded. Mean adaptive
latency is calibration-weighted and is not a new held-out performance estimate.

## Mapped functional replay

Liberty Boolean/flip-flop functions expand each mapped netlist into executable
zero-delay logic. A black-box mode of the existing Verilog bench drives the
same raw pixels, handshakes, gaps, stalls, invalid inputs and reset scenarios.
Every output class, fallback flag and exact cycle count must match the RTL CSV,
with 359 valid frames per design. Internal class scores/intervals are checked in
the RTL regression; they are not observable probes in the mapped replay.

This is a functional check of what mapping produced. It does not use SDF, prove
all possible inputs/control sequences, measure glitches or validate real-cell
timing. Hardware-initialization and layout effects remain outside this flow.

## Run and inspect

The `Mapped area, timing and replay` workflow installs the lightweight EDA/build
tools and caches the pinned timing-tool build. It runs independently of the
existing RTL/generic verification workflow. Both must pass before reporting the
study complete.

With those tools available, from the repository root:

```bash
bash scripts/build_timing_tools.sh  # once, if tools are not built
bash scripts/check_adaptive.sh    # golden RTL replay
export STA="$PWD/.tools/OpenSTA/build/sta"
python scripts/check_mapping.py
python scripts/check_mapped.py
```

The mapping manifest, library hashes, netlists, scripts/SDCs, search logs, common
clock reports, mapped replay results and CSV table are under `build/map/` and
`build/mapped_comparison.csv`. CI uploads them with a source-history bundle.
Missing tools or library inputs are reported as blocked, not a passing result.

Power/energy, multiple process/voltage/temperature corners, wire parasitics,
physical optimization, routed area and signoff are not measured. A better result
here supports a bounded pre-layout comparison, not a fabrication-ready chip.

Primary tool references: [OpenSTA](https://github.com/parallaxsw/OpenSTA),
[OpenSTA timing examples and units](https://github.com/The-OpenROAD-Project/OpenSTA/blob/master/doc/Examples.md),
[Yosys 0.33 ABC constraints](https://github.com/YosysHQ/yosys/blob/yosys-0.33/passes/techmap/abc.cc),
and [SKY130 library documentation](https://skywater-pdk.readthedocs.io/en/main/contents/libraries.html).

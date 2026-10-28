# Score-comparison pipeline experiment

The two-lane INT8 baseline computes the completed class score and compares it
with the stored best score in the same clock cycle. The saved mapped timing
path starts at `index[2]` and ends at `best_score[0]`, passing through accumulator
carry logic and best-score comparison. Its directly tested passing setup period
is 13.59375 ns, with 384 command-to-valid cycles and 5.220 microseconds latency.
See the historical [mapped study](mapped_study.md) for that measured baseline.

The new `flexmac_int8x2_scorepipe` variant stores a completed class score and
its class tag before comparing it against the previous best score. An explicit
comparison state adds one cycle per class. The accumulator still accepts one
pair of signed INT8 products per evaluation cycle, with no added register in
its feedback loop. The raw-pixel interface, frozen weights, quantization,
32-bit wrap semantics and lowest-index tie winner remain the same.

The expected no-gap schedule is 64 input cycles plus ten classes times
(32 accumulation cycles + one comparison cycle): **394 cycles per image**.
Invalid input still returns an error after input collection; result stalls
occur after valid and are excluded from command-to-valid latency.

This is a test of whether removing comparison from the accumulation path offsets
the extra cycles and registers. To beat 5.220 microseconds at 394 cycles, the new
design needs a tested passing period below 13.24873 ns. A 10% latency reduction
would require approximately 11.92386 ns. These are break-even calculations,
not predictions of the new timing result.

## Verification and measurement

`bash scripts/check_scorepipe.sh` replays the baseline and new engine on the same
359 calibration images and frozen INT8 scores. The new Verilog bench checks
class scores, pending class tags, exact cycles, invalid pixels, reset during
accumulation and comparison, final-class handling and output backpressure.
This is implementation verification on calibration inputs, not new held-out
accuracy evidence.

The independent `Score pipeline area, timing and replay` CI workflow uses the
same pinned SKY130 HD library, Yosys/ABC settings and OpenSTA constraints as the
original study. It remaps both designs in one run, directly tests their setup
period brackets and a common clock, and performs full 359-image two-state and
four-state mapped replay for both engines. The original four-design study and
its archived evidence remain the historical comparison.

```bash
bash scripts/check_scorepipe.sh
export STA="$PWD/.tools/OpenSTA/build/sta"
python scripts/check_mapping.py --study eda/scorepipe_study.json
python scripts/check_mapped.py --study eda/scorepipe_study.json
```

Results are pending execution. A faster clock alone is insufficient: the report
will compare cell area, registers, cycle count and complete latency at both a
common period and each design's tested passing period. The comparison remains
pre-layout, one typical corner, ideal wires and clock, without power or signoff.

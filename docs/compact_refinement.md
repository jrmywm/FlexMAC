# Compact certificates with selective exact refinement

## Research question and status

Can a compact certificate avoid both the large conditioned residual ROM and the
cost of recomputing all ten INT8 classes on every uncertain input?

This branch implements a candidate and compares it with unchanged two-lane INT8
and a new four-lane INT8 control. Until mapping and mapped replay pass, its
efficiency advantage is unverified. The original engine and historical results
remain reference measurements.

The existing bound construction is reused. This is a new experiment in this
repository, not an established claim of algorithmic novelty. Certified
quantization has prior art, including [Dang et al., AISTATS
2025](https://proceedings.mlr.press/v258/dang25a.html) and Kabaha and
Drachsler-Cohen's [guaranteed classifications and adaptive precision refinement,
OOPSLA 2025](https://doi.org/10.1145/3763118). The latter is particularly relevant:
it derives classification-consistency checks and refines precision when needed.
Our present question concerns the measured hardware cost of selectively
recomputing output classes for a small frozen INT8 reference. That distinction
does not establish novelty. A focused comparison of selective output refinement
is still needed before claiming a new algorithm.

```mermaid
flowchart LR
    R[64 raw pixels] --> B[Pixel buffer]
    B --> L[Four INT4 products per beat]
    L --> S[Ten low-precision scores]
    S --> C[Compact pairwise certificate]
    C -->|Every rival eliminated| O[Class decision]
    C -->|Uncertain rivals retained| M[Active-class mask]
    M --> E[Two INT8 products per beat]
    B --> E
    E --> W[Exact maximum over retained classes]
    W --> O
```

This conceptual diagram shows processing phases. The INT4 and INT8 phases
reuse the same two shared product circuits.

## Why a different fallback policy

The conditioned engine spends 320 MAC cycles on INT4, then 640 on full serial
INT8 fallback. Its checker uses a large feature-conditioned residual table.
Merely shrinking that table does not solve the scheduling problem: a two-lane
INT8 baseline already needs only 320 MAC cycles.

This candidate uses two instances of the existing shared product circuit. Each
cycle computes four INT4 products or two INT8 products. It stores the ten INT4
scores, then tests each rival against the existing global pairwise threshold.
An inconclusive test retains that class for exact evaluation; it does not force
all ten classes to be recomputed.

## Decision guarantee

Let c be the lowest-index INT4 winner and let T[c,j] be the frozen threshold
derived over all 17 possible raw pixel values for every feature. The existing
derivation gives:

```
S4[c] - S4[j] >= T[c,j]  implies  S8[c] > S8[j].
```

If all rivals pass, return c. Otherwise evaluate the exact INT8 scores for c
and every rival that did not pass, then return the lowest-index maximum.

Every eliminated rival is strictly worse than c in INT8. Because c is retained
whenever exact evaluation is needed, no eliminated rival can win. Strict
elimination preserves any possible INT8 tie for exact evaluation. This certifies
the class decision, not equality of approximate and exact scores.

The certificate remains conditional on correct frozen arithmetic and inputs in
[0,16]. The screening script checks domain-wide final score extrema: INT8
[-212584,223820], INT4 [-568,600]. Thus the mathematical scores do not wrap a
32-bit accumulator for this model. No guarantee covers changed weights,
preprocessing, unsupported inputs or hardware faults. This mathematical argument
is not a formal proof of the complete sequential RTL.

## Initial feasibility screen

No training or test data is opened. Existing training/calibration raw pixels and
integer score fixtures are reused. Every reference score is recomputed from the
frozen weights and raw pixels before evaluating the schedule.
Independent unit checks also cover 365 constructed raw vectors: all 17 uniform
pixel values, two alternating extremes, 256 seeded random vectors and 90
class-pair residual-minimum witnesses. These are mathematical-model tests;
they are not additional RTL replay frames.

| Split | Samples | No exact classes needed | Mean exact classes |
| --- | ---: | ---: | ---: |
| Training | 1078 | 456 | 2.038 |
| Calibration | 359 | 134 | 2.318 |

There are zero decision disagreements with frozen INT8 in the offline screen.
This is observed agreement plus a separate domain-wide bound argument, not
independent held-out accuracy evidence.

The explicit RTL schedule includes 64 input beats, 160 INT4 MAC beats, ten
comparison states, nine class-initialization states, and ten certificate states.
A certified transaction therefore takes 253 cycles. A transaction refining k
classes takes 263 + 33*k cycles, including ten class-selection states. On the
calibration distribution the projection is 335.747 mean cycles, compared with
394 for the two-lane score-comparison baseline. The earlier first-pass estimate
of about 320 cycles omitted initialization and selection states; this document
uses the actual intended controller schedule.

At those projected counts the candidate's clock period must be less than
1.1735 times the two-lane baseline period to improve mean elapsed time. Worst
case is 593 cycles if all ten classes require exact evaluation; observed
calibration maximum is nine classes, or 560 cycles. This is an average-latency
experiment with potentially worse tail latency.

The new four-lane INT8 control needs 234 cycles. It tests whether straightforward
parallelism gives a better area/latency tradeoff than adaptive control. A gain
over two lanes alone does not establish superiority over this stronger control.

The ten stored INT4 scores and the captured candidate use 11 signed bits each,
justified by the domain extrema above. Exact refinement retains a 32-bit score
and accumulator. This saves 231 stored bits compared with 32-bit low-score and
candidate registers; physical saving still requires mapping.

The 90 used pair thresholds fit eight unsigned bits each (720 logical bits).
The conservative generated ROM interface remains 32 bits. These logical payload
figures are not physical area or mapped-cell estimates.

## Reproduction and acceptance criteria

```
python -m unittest discover -s tests -v
python scripts/screen_compact_refinement.py
bash scripts/check_compact_refine.sh
bash scripts/check_scorepipe.sh
STA=.tools/OpenSTA/build/sta python scripts/map_compact_refine.py
```

The workflow `compact-refinement.yml` installs the existing lightweight EDA
tools and restores the pinned timing-library/tool cache. It archives source
history, scoreboards, cycle traces, mapped-cell counts, setup/hold reports and
gate-level replays. All calibration frames must match their RTL decisions, flags
and cycle counts in a compiled two-state simulator with randomized initialization.
A separate Icarus four-state replay selects one example of every observed
predicted class and exact-refinement count, plus the first/last calibration
frames. Selection uses existing calibration metadata. The exact selected indices
are archived; this is not full-calibration four-state coverage or SDF simulation.

Report whole-engine cell area, mean and worst latency at each directly tested
passing period, and latency at a common feasible clock. A useful efficiency
claim requires a meaningful Pareto tradeoff against both INT8 controls. Include
the cost of the extra model bank, stored scores, multipliers and control. If an
INT8 control is both smaller and faster, reject this candidate for this workload.
Power, energy, physical-layout and independent generalization claims remain
outside this experiment.

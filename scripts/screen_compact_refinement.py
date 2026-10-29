"""Screen compact exact-refinement schedules using frozen train/calibration data.

No training, test-set access, labels, or timing/area estimates. Pairwise bounds
eliminate only rivals proven strictly below the INT4 candidate in INT8. Exact
INT8 evaluation is needed for the candidate and all remaining rivals, unless
every rival was eliminated. This is a feasibility model, not an RTL result.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.certification import derive_bounds, read_models, quantized_pixels


def read_hex(path, bits=32):
    values = [int(x, 16) for x in path.read_text().split()]
    return [(v + (1 << (bits-1))) % (1 << bits) - (1 << (bits-1)) for v in values]


def refine(scores4, thresholds):
    candidate = max(range(len(scores4)), key=lambda c: scores4[c])
    rivals = [j for j in range(len(scores4)) if j != candidate
              and scores4[candidate] - scores4[j] < thresholds[candidate][j]]
    return candidate, ([candidate] + rivals if rivals else [])


def main():
    rom = ROOT/'rtl/digits_model_rom.v'
    model = read_models(rom.read_text())
    bounds, _, _ = derive_bounds(*model, 366)
    scores4 = read_hex(ROOT/'model/agreement/scores_int4.hex')
    scores8 = read_hex(ROOT/'model/agreement/scores_int8.hex')
    raw = read_hex(ROOT/'model/agreement/raw_pixels.hex', 8)
    assert len(scores4) == len(scores8) == 14370 and len(raw) == 1437*64
    # Domain-wide score ranges rule out wrapped arithmetic for this frozen model.
    extrema = {}
    for bits, weights, bias in ((8,model[0],model[2]),(4,model[1],model[3])):
        q = quantized_pixels(bits)
        lo = min(bias[c]+sum(min(v*w for v in q) for w in weights[c]) for c in range(10))
        hi = max(bias[c]+sum(max(v*w for v in q) for w in weights[c]) for c in range(10))
        assert -(1 << 31) <= lo <= hi < (1 << 31)
        if bits==4:assert -(1 << 10) <= lo <= hi < (1 << 10)
        extrema[str(bits)] = [lo,hi]
    report = {'status':'offline_screen_only', 'scope':'frozen training/calibration; no test access',
              'score_domain_extrema':extrema, 'splits':{},
              'bound_kind':'existing exact global pairwise thresholds, K=366',
              'threshold_payload_bits':90*max(t.bit_length() for row in bounds['thresholds'] for t in row),
              'limitations':['Not synthesized, timed, or RTL verified.',
                             'Cycle projections assume dedicated compare/check states and paired INT8 refinement.',
                             'No new algorithmic novelty is established.'],
              'source_sha256':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (rom,ROOT/'model/certification.py',Path(__file__),
                            ROOT/'model/agreement/scores_int4.hex',ROOT/'model/agreement/scores_int8.hex',
                            ROOT/'model/agreement/raw_pixels.hex')}}
    masks=[]
    for split, first, last in (('train',0,1078),('calibration',1078,1437)):
        histogram = [0]*11
        for n in range(first,last):
            s4,s8 = scores4[n*10:(n+1)*10],scores8[n*10:(n+1)*10]
            candidate, active = refine(s4,bounds['thresholds'])
            masks.append(sum(1 << c for c in active))
            result = min(active,key=lambda c:(-s8[c],c)) if active else candidate
            assert result == max(range(10),key=lambda c:s8[c])
            histogram[len(active)] += 1
            # Independently recompute frozen score references from raw pixels.
            for bits,weights,bias,reference in ((4,model[1],model[3],s4),(8,model[0],model[2],s8)):
                q=quantized_pixels(bits)
                assert [bias[c]+sum(q[p]*w for p,w in zip(raw[n*64:(n+1)*64],weights[c]))
                        for c in range(10)] == reference
        count=last-first
        mean_classes=sum(c*n for c,n in enumerate(histogram))/count
        # 64 load + INT4 class MACs/comparison + ten threshold comparisons.
        # Each exact class: 32 paired MAC cycles + one comparison.
        fallback_fraction=1-histogram[0]/count
        projections={str(lanes):64+640//lanes+10+9+10+10*fallback_fraction+33*mean_classes
                     for lanes in (2,4,8)}
        report['splits'][split]={'samples':count,'exact_classes_histogram':histogram,
            'mean_exact_classes':mean_classes,'decision_mismatches':0,
            'projected_mean_cycles_by_int4_lanes':projections,
            'baseline_scorepipe_cycles':394,
            'required_period_ratio_to_scorepipe':{k:394/v for k,v in projections.items()}}
    out=ROOT/'docs/data/compact_refinement'
    out.mkdir(parents=True,exist_ok=True)
    (out/'screen.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    fixture=ROOT/'build/compact_refinement'
    fixture.mkdir(parents=True,exist_ok=True)
    (fixture/'active_masks.hex').write_text(''.join(f'{m:03x}\n' for m in masks),encoding='ascii',newline='\n')
    print(json.dumps(report['splits'],indent=2))


if __name__=='__main__':
    main()

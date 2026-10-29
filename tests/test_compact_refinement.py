"""Independent adversarial-domain checks of selective exact refinement."""
import random
import unittest
from pathlib import Path
from model.certification import derive_bounds,quantized_pixels,read_models
from scripts.screen_compact_refinement import refine

ROOT=Path(__file__).resolve().parents[1]


class CompactRefinementTests(unittest.TestCase):
    def test_supported_domain_and_attaining_pairwise_witnesses(self):
        w8,w4,b8,b4=read_models((ROOT/'rtl/digits_model_rom.v').read_text())
        bounds,residual,_=derive_bounds(w8,w4,b8,b4,366)
        rng=random.Random(20261029)
        vectors=[[p]*64 for p in range(17)]
        vectors += [[0 if (i+parity)%2 else 16 for i in range(64)] for parity in range(2)]
        vectors += [[rng.randrange(17) for _ in range(64)] for _ in range(256)]
        # Each witness attains an exact global pairwise residual lower bound.
        vectors += [[min(range(17),key=lambda p:residual[c][i][p]-residual[j][i][p])
                     for i in range(64)] for c in range(10) for j in range(10) if c!=j]
        q8,q4=quantized_pixels(8),quantized_pixels(4)
        for raw in vectors:
            s8=[b8[c]+sum(q8[p]*w for p,w in zip(raw,w8[c])) for c in range(10)]
            s4=[b4[c]+sum(q4[p]*w for p,w in zip(raw,w4[c])) for c in range(10)]
            candidate,active=refine(s4,bounds['thresholds'])
            for j in range(10):
                if j!=candidate and j not in active:self.assertGreater(s8[candidate],s8[j])
            result=min(active,key=lambda c:(-s8[c],c)) if active else candidate
            self.assertEqual(result,max(range(10),key=lambda c:s8[c]))

    def test_threshold_boundary_retains_equal_and_uncertain_rivals(self):
        # Strict INT8 superiority is required for elimination. At an INT4 tie,
        # both candidates must survive a conservative positive threshold.
        _,active=refine([0,0],[[1,1],[1,1]])
        self.assertEqual(set(active),{0,1})
        candidate,active=refine([1,0],[[1,1],[1,1]])
        self.assertEqual((candidate,active),(0,[]))


if __name__=='__main__':unittest.main()

"""Data-integrity checks only; inference verification is in tb_classifier.v."""
from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TestFrozenModel(unittest.TestCase):
    def test_manifest(self):
        metadata = json.loads((ROOT / 'model/digits/metadata.json').read_text(encoding='utf-8'))
        for filename, digest in metadata['sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT / filename).read_bytes()).hexdigest(), digest, filename)
        splits = metadata['split_indices']
        self.assertEqual(len(set(sum(splits.values(), []))), 1797)
        self.assertEqual(sum(map(len, splits.values())), 1797)
        self.assertEqual(len(splits['test']), 360)
        for bits, terms in ((8, 64), (4, 32)):
            for kind, count in ((f'features_int{bits}', 360*terms), (f'scores_int{bits}', 360*10),
                                (f'predictions_int{bits}', 360)):
                self.assertEqual(len((ROOT / f'model/digits/{kind}.hex').read_text().splitlines()), count)
            self.assertLess(metadata['modes'][str(bits)]['maximum_accumulator_bound'], 2**31)


if __name__ == '__main__':
    unittest.main()

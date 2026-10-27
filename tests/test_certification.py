"""Check bound construction and the exact integer threshold transformation."""
from pathlib import Path
import hashlib
import json
import unittest
from model.certification import derive_bounds, quantized_pixels, read_models

ROOT = Path(__file__).resolve().parents[1]


class CertificationTests(unittest.TestCase):
    def test_conditioned_rom_exact(self):
        import re
        from model.certification import signed
        models = read_models((ROOT/'rtl/digits_model_rom.v').read_text(encoding='utf-8'))
        _, residual, offset = derive_bounds(*models, 366)
        rom = (ROOT/'rtl/digits_residual_rom.v').read_text(encoding='utf-8')
        entries = [int(v,16) for v in (ROOT/'model/agreement/residual_ranges.hex').read_text().splitlines()]
        self.assertEqual(len(entries),16384)
        self.assertIn('$readmemh("model/agreement/residual_ranges.hex", ranges)',rom)
        q4 = quantized_pixels(4)
        for c in range(10):
            for i in range(64):
                for v in range(-7,8):
                    value=entries[c*1024+i*16+(v&15)]
                    possible=[residual[c][i][p] for p in range(17) if q4[p]==v]
                    self.assertEqual((signed(value>>13,13),signed(value&8191,13)),(min(possible),max(possible)))
        biases={int(k):signed(int(v,16),32) for k,v in re.findall(r"4'd(\d+): bias = 32'h([0-9a-f]+)",rom)}
        self.assertEqual([biases[c] for c in range(10)],offset)
        legal={c*1024+i*16+(v&15) for c in range(10) for i in range(64) for v in range(-7,8)}
        for address in set(range(16384))-legal:
            self.assertEqual(entries[address],(4096<<13)|4095)
        self.assertLess(max(map(abs,offset))+64*4096+366*600,2**31)

    def test_frozen_derivation_and_integrity(self):
        report = json.loads((ROOT / 'model/agreement/feasibility.json').read_text(encoding='utf-8'))
        for group in ('source_sha256', 'fixture_sha256'):
            for path, digest in report[group].items():
                self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(), digest, path)
        models = read_models((ROOT/'rtl/digits_model_rom.v').read_text(encoding='utf-8'))
        bounds, _, _ = derive_bounds(*models, report['bounds']['multiplier'])
        self.assertEqual(bounds, report['bounds'])
        k = bounds['multiplier']
        for c in range(10):
            for j in range(10):
                threshold = bounds['thresholds'][c][j]
                for margin in (threshold-1, threshold, threshold+1):
                    self.assertEqual(margin >= threshold, k*margin+bounds['pair_lower'][c][j] > 0)
        train = report['splits']['train']['samples']
        calibration = report['splits']['calibration']['samples']
        self.assertEqual((train, calibration), (1078, 359))
        self.assertEqual(len((ROOT/'model/agreement/scores_int4.hex').read_text().splitlines()), (train+calibration)*10)

    def test_separable_pair_bound_is_sound(self):
        # Attain the per-coordinate minima simultaneously. This checks the
        # construction, including signed rounding and bias, at its exact boundary.
        models = read_models((ROOT/'rtl/digits_model_rom.v').read_text(encoding='utf-8'))
        bounds, residual, offset = derive_bounds(*models, 366)
        q8, q4 = quantized_pixels(8), quantized_pixels(4)
        w8, w4, b8, b4 = models
        for c in range(10):
            for j in range(10):
                pixels = [min(range(17), key=lambda p: residual[c][i][p]-residual[j][i][p]) for i in range(64)]
                diff8 = b8[c]-b8[j]+sum(q8[p]*(w8[c][i]-w8[j][i]) for i,p in enumerate(pixels))
                diff4 = b4[c]-b4[j]+sum(q4[p]*(w4[c][i]-w4[j][i]) for i,p in enumerate(pixels))
                self.assertEqual(diff8-366*diff4, bounds['pair_lower'][c][j])


if __name__ == '__main__':
    unittest.main()

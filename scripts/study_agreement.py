"""Offline feasibility study. Never opens the held-out test split or retrains."""
from pathlib import Path
import csv
import hashlib
import json
import sys
import numpy as np
from sklearn.datasets import load_digits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.certification import derive_bounds, pair_certified, quantized_pixels, read_models

OUT = ROOT / 'model' / 'agreement'


def write_text(path, body):
    path.write_text(body, encoding='utf-8', newline='\n')


def hex_file(name, values, width):
    write_text(OUT / name, ''.join(f'{int(v) & ((1 << width)-1):0{width//4}x}\n' for v in values))


def main():
    OUT.mkdir(exist_ok=True)
    metadata = json.loads((ROOT / 'model/digits/metadata.json').read_text(encoding='utf-8'))
    rom = ROOT / 'rtl/digits_model_rom.v'
    w8, w4, b8, b4 = read_models(rom.read_text(encoding='utf-8'))
    s8, s4 = metadata['modes']['8'], metadata['modes']['4']
    multiplier = round(s4['input_scale']*s4['weight_scale']/(s8['input_scale']*s8['weight_scale']))
    bounds, residual, offset = derive_bounds(w8, w4, b8, b4, multiplier)
    q8, q4 = np.array(quantized_pixels(8)), np.array(quantized_pixels(4))
    residual = np.array(residual)
    # The proof uses all 17 possible values for every pixel, not empirical extrema.
    # These tighter bounds condition each residual on its observed INT4 value.
    condition_low = np.array([[[min(residual[c, i, q4 == v]) for v in range(-7, 8)]
                              for i in range(64)] for c in range(10)])
    condition_high = np.array([[[max(residual[c, i, q4 == v]) for v in range(-7, 8)]
                               for i in range(64)] for c in range(10)])
    raw = load_digits().data.astype(np.int64)
    report = {'scope': 'training and calibration only; no held-out test evaluation',
              'domain': '64 independent raw integer pixels in [0,16], exact frozen preprocessing',
              'bounds': bounds, 'splits': {}, 'checker_cycles_assumption': 10,
              'source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (rom, ROOT / 'model/digits/metadata.json')},
              'conditioned_residual_table_entries': int(condition_low.size + condition_high.size),
              'conditioned_conservative_signed_bits_per_entry':
                  int(max(abs(condition_low).max(), abs(condition_high).max())).bit_length()+1}
    fixtures, expected, winners, reference = [], [], [], []
    rows = []
    for split in ('train', 'calibration'):
        indices = metadata['split_indices'][split]
        pixels = raw[indices]  # No test-index access or test-label use.
        scores8 = q8[pixels] @ np.array(w8).T + np.array(b8)
        scores4 = q4[pixels] @ np.array(w4).T + np.array(b4)
        counts = {'global': 0, 'pairwise': 0, 'conditioned': 0}
        false_accepts = dict.fromkeys(counts, 0)
        for n, sample in enumerate(indices):
            score = scores4[n].tolist()
            winner = int(scores4[n].argmax())
            exact_winner = int(scores8[n].argmax())
            low = multiplier*scores4[n] + bounds['class_lower']
            high = multiplier*scores4[n] + bounds['class_upper']
            values4 = q4[pixels[n]]
            conditioned_lo = np.array(offset) + condition_low[:, np.arange(64), values4+7].sum(axis=1)
            conditioned_hi = np.array(offset) + condition_high[:, np.arange(64), values4+7].sum(axis=1)
            actual_residual = scores8[n] - multiplier*scores4[n]
            assert np.all(conditioned_lo <= actual_residual) and np.all(actual_residual <= conditioned_hi)
            checks = {
                'global': all(low[winner] > high[j] for j in range(10) if j != winner),
                'pairwise': pair_certified(score, bounds['thresholds']),
                'conditioned': all(multiplier*score[winner]+conditioned_lo[winner] >
                                   multiplier*score[j]+conditioned_hi[j] for j in range(10) if j != winner)}
            for name, accepted in checks.items():
                counts[name] += int(accepted)
                false_accepts[name] += int(accepted and winner != exact_winner)
            fixtures.extend(score); expected.append(int(checks['pairwise']))
            winners.append(winner); reference.append(exact_winner)
            rows.append({'split': split, 'dataset_index': sample, 'int4_class': winner, 'int8_class': exact_winner,
                         **{name: int(value) for name, value in checks.items()}})
        assert not any(false_accepts.values())
        report['splits'][split] = {'samples': len(indices), 'accepted': counts, 'false_accepts': false_accepts,
            'pairwise_mean_compute_cycles_before_checker': 320+640*(1-counts['pairwise']/len(indices)),
            'pairwise_optimistic_mean_cycles': 64+320+10+640*(1-counts['pairwise']/len(indices)),
            'conditioned_mean_compute_cycles_excluding_bound_hardware': 320+640*(1-counts['conditioned']/len(indices))}
    hex_file('scores_int4.hex', fixtures, 32)
    hex_file('expected_pairwise.hex', expected, 8)
    hex_file('winner_int4.hex', winners, 8)
    hex_file('reference_int8.hex', reference, 8)
    hex_file('thresholds.hex', [v for row in bounds['thresholds'] for v in row], 32)
    cases = [f"            8'h{c*16+j:02x}: threshold = 32'h{bounds['thresholds'][c][j] & 0xffffffff:08x};"
             for c in range(10) for j in range(10)]
    write_text(ROOT / 'rtl/digits_agreement_bounds.v', '''// Generated from exact raw-pixel-domain bounds by scripts/study_agreement.py.
module digits_agreement_bounds(input wire [3:0] winner, competitor,
    output reg signed [31:0] threshold);
    always @* begin
        threshold = 32'sh7fffffff;
        case ({winner, competitor})
'''+'\n'.join(cases)+'''
            default: threshold = 32'sh7fffffff;
        endcase
    end
endmodule
''')
    with (OUT / 'feasibility.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    report['fixture_sha256'] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(OUT.glob('*.hex')) + [ROOT / 'rtl/digits_agreement_bounds.v', OUT / 'feasibility.csv']}
    write_text(OUT / 'feasibility.json', json.dumps(report, indent=2) + '\n')
    print(json.dumps({'multiplier': multiplier, 'splits': report['splits'],
                      'conditioned_table_entries': report['conditioned_residual_table_entries']}, indent=2))


if __name__ == '__main__':
    main()

"""Exact, offline agreement-bound construction for the frozen linear models."""
import re


def signed(value, bits):
    return (value + (1 << (bits - 1))) % (1 << bits) - (1 << (bits - 1))


def read_models(rom_text):
    packed = {int(k): int(v, 16) for k, v in re.findall(r"11'd(\d+): weight = 8'h([0-9a-f]+)", rom_text)}
    bias = {int(k): signed(int(v, 16), 32) for k, v in re.findall(r"5'd(\d+): bias = 32'h([0-9a-f]+)", rom_text)}
    w8 = [[signed(packed[c*64+i], 8) for i in range(64)] for c in range(10)]
    w4 = [[signed((packed[1024+c*32+i//2] >> (4*(i % 2))) & 15, 4)
           for i in range(64)] for c in range(10)]
    return w8, w4, [bias[c] for c in range(10)], [bias[16+c] for c in range(10)]


def quantized_pixels(bits):
    # Fractions with denominator eight are represented exactly; round ties even.
    return [round((p-8)*((1 << (bits-1))-1)/8) for p in range(17)]


def derive_bounds(w8, w4, b8, b4, multiplier):
    if multiplier <= 0:
        raise ValueError('A positive multiplier is required')
    q8, q4 = quantized_pixels(8), quantized_pixels(4)
    residual = [[[q8[p]*w8[c][i] - multiplier*q4[p]*w4[c][i] for p in range(17)]
                 for i in range(64)] for c in range(10)]
    offset = [b8[c] - multiplier*b4[c] for c in range(10)]
    lower = [offset[c] + sum(min(v) for v in residual[c]) for c in range(10)]
    upper = [offset[c] + sum(max(v) for v in residual[c]) for c in range(10)]
    pair_lower = [[offset[c]-offset[j]+sum(min(a-b for a, b in zip(residual[c][i], residual[j][i]))
                   for i in range(64)) for j in range(10)] for c in range(10)]
    # K*(score4[c]-score4[j])+pair_lower[c][j] > 0, exactly in integers.
    thresholds = [[(-value)//multiplier + 1 for value in row] for row in pair_lower]
    return {'multiplier': multiplier, 'class_lower': lower, 'class_upper': upper,
            'pair_lower': pair_lower, 'thresholds': thresholds}, residual, offset


def pair_certified(scores, thresholds):
    winner = max(range(10), key=lambda c: scores[c])
    return all(scores[winner]-scores[j] >= thresholds[winner][j] for j in range(10) if j != winner)

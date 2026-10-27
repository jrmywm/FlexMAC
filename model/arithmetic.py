"""Mathematical reference: signed conversion and Python integer arithmetic.

No partial-product decomposition from the implementation is copied here.
"""


def signed(value: int, bits: int) -> int:
    if not isinstance(value, int) or not 0 <= value < (1 << bits):
        raise ValueError(f'value must fit an unsigned {bits}-bit encoding')
    return value-(1 << bits) if value & (1 << (bits-1)) else value


def product_sum(a: int, b: int, mode4: bool) -> int:
    signed(a, 8)
    signed(b, 8)
    if mode4:
        return (signed(a & 15, 4)*signed(b & 15, 4)
                + signed(a >> 4, 4)*signed(b >> 4, 4))
    return signed(a, 8)*signed(b, 8)


def dot(beats: list[tuple[int, int]], mode4: bool) -> int:
    if not beats:
        raise ValueError('a frame must contain at least one accepted beat')
    value = sum(product_sum(a, b, mode4) for a, b in beats)
    encoded = value & 0xffffffff
    return encoded-(1 << 32) if encoded & 0x80000000 else encoded

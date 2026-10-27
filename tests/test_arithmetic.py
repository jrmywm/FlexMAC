import unittest
from model.arithmetic import signed, product_sum, dot


class ArithmeticTests(unittest.TestCase):
    def test_signed_boundaries(self):
        self.assertEqual([signed(v,8) for v in (0,127,128,255)], [0,127,-128,-1])

    def test_int8_extremes(self):
        self.assertEqual(product_sum(128,128,False),16384)
        self.assertEqual(product_sum(128,127,False),-16256)
        self.assertEqual(product_sum(255,255,False),1)

    def test_int4_extremes(self):
        self.assertEqual(product_sum(0x88,0x88,True),128)
        self.assertEqual(product_sum(0x88,0x77,True),-112)

    def test_independent_lanes(self):
        self.assertEqual(product_sum(0x2f,0x3e,True),8)  # (-1)*(-2) + 2*3
        self.assertEqual(product_sum(0x2f,0x3e,False),2914)

    def test_dot_mixed_sign(self):
        self.assertEqual(dot([(128,1),(127,1),(255,2)],False),-3)

    def test_accumulator_wrap(self):
        self.assertEqual(dot([(128,128)]*131072,False),-2147483648)
        self.assertEqual(dot([(128,128)]*262144,False),0)

    def test_invalid_encoding(self):
        for v in (-1,256):
            with self.assertRaises(ValueError):
                product_sum(v,0,False)

    def test_empty_frame_rejected(self):
        with self.assertRaises(ValueError):
            dot([],False)

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
sources=(rtl/flexmac_product.v rtl/flexmac_baselines.v rtl/flexmac_int8x2.v rtl/digits_model_rom.v
    rtl/digits_residual_rom.v rtl/digits_pixel_quantizer.v rtl/flexmac_adaptive.v)
sha256sum "${sources[@]}" tests/tb_adaptive.v tests/tb_int8x2.v model/agreement/*.hex > build/adaptive_sources.log
for impl in 0 1; do
    iverilog -g2012 -s tb_adaptive -Ptb_adaptive.PRODUCT_IMPL="$impl" \
        -o "build/adaptive_$impl.vvp" "${sources[@]}" tests/tb_adaptive.v
    vvp "build/adaptive_$impl.vvp" | tee "build/adaptive_$impl.log"
done
iverilog -g2012 -s tb_adaptive -Ptb_adaptive.FORCE_INT8=1 \
    -o build/adaptive_always_int8.vvp "${sources[@]}" tests/tb_adaptive.v
vvp build/adaptive_always_int8.vvp | tee build/adaptive_always_int8.log
iverilog -g2012 -s tb_int8x2 -o build/int8x2_product.vvp \
    rtl/flexmac_baselines.v rtl/flexmac_int8x2.v tests/tb_int8x2.v
vvp build/int8x2_product.vvp | tee build/int8x2_product.log
# A 16-bit intermediate silently corrupts +32768. Require this realistic fault
# to compile, then fail the independent boundary-grid checker.
sed 's/assign product = .*/wire signed [15:0] truncated = p0 + p1; assign product = {truncated[15], truncated};/' \
    rtl/flexmac_int8x2.v > build/int8x2_truncated.v
iverilog -g2012 -s tb_int8x2 -o build/int8x2_negative.vvp \
    rtl/flexmac_baselines.v build/int8x2_truncated.v tests/tb_int8x2.v
if vvp build/int8x2_negative.vvp > build/int8x2_negative.log 2>&1; then
    echo 'FAIL: truncated pair sum was not rejected' >&2
    exit 1
fi
grep -q 'two-lane product mismatch' build/int8x2_negative.log
echo 'PASS negative control: 16-bit pair-sum overflow rejected'
iverilog -g2012 -s tb_adaptive -Ptb_adaptive.FORCE_INT8=1 -Ptb_adaptive.INT8_LANES=2 \
    -o build/int8_two_lane.vvp "${sources[@]}" tests/tb_adaptive.v
vvp build/int8_two_lane.vvp | tee build/int8_two_lane.log

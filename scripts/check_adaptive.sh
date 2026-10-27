#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
sources=(rtl/flexmac_product.v rtl/flexmac_baselines.v rtl/digits_model_rom.v
    rtl/digits_residual_rom.v rtl/digits_pixel_quantizer.v rtl/flexmac_adaptive.v)
sha256sum "${sources[@]}" tests/tb_adaptive.v model/agreement/*.hex > build/adaptive_sources.log
for impl in 0 1; do
    iverilog -g2012 -s tb_adaptive -Ptb_adaptive.PRODUCT_IMPL="$impl" \
        -o "build/adaptive_$impl.vvp" "${sources[@]}" tests/tb_adaptive.v
    vvp "build/adaptive_$impl.vvp" | tee "build/adaptive_$impl.log"
done
iverilog -g2012 -s tb_adaptive -Ptb_adaptive.FORCE_INT8=1 \
    -o build/adaptive_always_int8.vvp "${sources[@]}" tests/tb_adaptive.v
vvp build/adaptive_always_int8.vvp | tee build/adaptive_always_int8.log

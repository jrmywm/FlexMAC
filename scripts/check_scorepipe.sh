#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
sources=(rtl/flexmac_baselines.v rtl/flexmac_int8x2.v rtl/digits_model_rom.v
    rtl/digits_pixel_quantizer.v rtl/flexmac_int8x2_scorepipe.v)
sha256sum "${sources[@]}" tests/tb_scorepipe.v scripts/check_scorepipe.sh \
    rtl/flexmac_product.v rtl/digits_residual_rom.v rtl/flexmac_adaptive.v \
    tests/tb_adaptive.v model/agreement/*.hex > build/scorepipe_sources.log
iverilog -g2012 -s tb_scorepipe -o build/scorepipe.vvp "${sources[@]}" tests/tb_scorepipe.v
vvp build/scorepipe.vvp | tee build/scorepipe.log
# Same-run unchanged two-lane baseline for the isolated experiment.
iverilog -g2012 -s tb_adaptive -Ptb_adaptive.FORCE_INT8=1 -Ptb_adaptive.INT8_LANES=2 \
    -o build/int8_two_lane.vvp rtl/flexmac_product.v rtl/digits_residual_rom.v \
    rtl/flexmac_adaptive.v "${sources[@]}" tests/tb_adaptive.v
vvp build/int8_two_lane.vvp | tee build/int8_two_lane.log

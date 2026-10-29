#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/check_scorepipe.sh
sources=(rtl/flexmac_baselines.v rtl/flexmac_int8x2.v rtl/digits_model_rom.v
    rtl/digits_pixel_quantizer.v rtl/flexmac_int8x2_overlap.v)
sha256sum "${sources[@]}" tests/tb_overlap.v scripts/check_overlap.sh > build/overlap_sources.log
iverilog -g2012 -s tb_overlap -o build/overlap.vvp "${sources[@]}" tests/tb_overlap.v
vvp build/overlap.vvp | tee build/overlap.log
iverilog -g2012 -DBROKEN_OVERLAP_TAG -s tb_overlap -o build/overlap_broken.vvp "${sources[@]}" tests/tb_overlap.v
if vvp build/overlap_broken.vvp +negative_tag +report=build/overlap_negative.csv > build/overlap_negative.log 2>&1; then
    echo 'FAIL broken tag was not detected' >&2; exit 1
fi
grep -q 'pending score/class/last tag mismatch' build/overlap_negative.log

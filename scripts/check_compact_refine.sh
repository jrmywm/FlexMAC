#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/compact_refinement
python scripts/screen_compact_refinement.py
sources=(rtl/flexmac_product.v rtl/digits_model_rom.v rtl/digits_pixel_quantizer.v
    rtl/digits_agreement_bounds.v rtl/flexmac_compact_refine.v)
sha256sum "${sources[@]}" tests/tb_compact_refine.v scripts/check_compact_refine.sh \
    model/agreement/*.hex > build/compact_refinement/sources.log
iverilog -g2012 -s tb_compact_refine -Ptb_compact_refine.FIRST=0 -Ptb_compact_refine.COUNT=1437 \
    -o build/compact_refinement/rtl.vvp "${sources[@]}" tests/tb_compact_refine.v
vvp build/compact_refinement/rtl.vvp | tee build/compact_refinement/rtl.log
mv build/compact_refinement/rtl.csv build/compact_refinement/all_rtl.csv
iverilog -g2012 -s tb_compact_refine -o build/compact_refinement/cal.vvp "${sources[@]}" tests/tb_compact_refine.v
vvp build/compact_refinement/cal.vvp | tee build/compact_refinement/cal.log
iverilog -g2012 -DBASELINE4 -s tb_compact_refine -Ptb_compact_refine.FIRST=0 -Ptb_compact_refine.COUNT=1437 \
    -o build/compact_refinement/baseline4.vvp rtl/flexmac_baselines.v rtl/digits_model_rom.v \
    rtl/digits_pixel_quantizer.v rtl/flexmac_int8x4_scorepipe.v tests/tb_compact_refine.v
vvp build/compact_refinement/baseline4.vvp +report=build/compact_refinement/baseline4_all.csv | tee build/compact_refinement/baseline4.log
# Deliberately discard every rival, even when the certificate is inconclusive.
sed 's/wire safe_rival=.*/wire safe_rival=1\x27b1;/' rtl/flexmac_compact_refine.v > build/compact_refinement/broken.v
iverilog -g2012 -s tb_compact_refine -o build/compact_refinement/negative.vvp \
    "${sources[@]:0:4}" build/compact_refinement/broken.v tests/tb_compact_refine.v
if vvp build/compact_refinement/negative.vvp +report=build/compact_refinement/negative.csv > build/compact_refinement/negative.log 2>&1; then
    echo 'FAIL compact negative control passed' >&2;exit 1
fi
grep -Eq 'compact (decision mismatch|cycles)' build/compact_refinement/negative.log
echo 'PASS compact negative control: unsafe rival elimination rejected'

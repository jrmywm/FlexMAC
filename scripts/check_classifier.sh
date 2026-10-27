#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
git rev-parse HEAD > build/classifier_source_commit.log
sha256sum rtl/flexmac_classifier.v rtl/flexmac_classifier_fixed.v rtl/digits_model_rom.v tests/tb_classifier*.v \
    model/digits/*.hex model/digits/metadata.json scripts/check_classifier.sh > build/classifier_sources.log
for impl in 0 1; do
    iverilog -g2012 -s tb_classifier -Ptb_classifier.PRODUCT_IMPL="$impl" \
        -o "build/classifier_$impl.vvp" rtl/flexmac_product.v rtl/flexmac_baselines.v \
        rtl/digits_model_rom.v rtl/flexmac_classifier.v tests/tb_classifier.v
    vvp "build/classifier_$impl.vvp" | tee "build/classifier_$impl.log"
    iverilog -g2012 -s tb_classifier_directed -Ptb_classifier_directed.PRODUCT_IMPL="$impl" \
        -o "build/classifier_directed_$impl.vvp" rtl/flexmac_product.v rtl/flexmac_baselines.v \
        rtl/flexmac_classifier.v tests/tb_classifier_directed.v
    vvp "build/classifier_directed_$impl.vvp" | tee "build/classifier_directed_$impl.log"
done
for mode in 0 1; do
    iverilog -g2012 -s tb_classifier -Ptb_classifier.FIXED_MODE="$mode" \
        -o "build/classifier_fixed_$mode.vvp" rtl/flexmac_product.v rtl/flexmac_baselines.v \
        rtl/digits_model_rom.v rtl/flexmac_classifier.v tests/tb_classifier.v
    vvp "build/classifier_fixed_$mode.vvp" | tee "build/classifier_fixed_$mode.log"
done
# The directed checker must reject unsigned argmax ordering. Compile success is
# required first; a syntax error is not a successful negative control.
sed 's/completed_score > best_score/$unsigned(completed_score) > $unsigned(best_score)/' \
    rtl/flexmac_classifier.v > build/classifier_unsigned_bug.v
iverilog -g2012 -s tb_classifier_directed -o build/classifier_negative.vvp \
    rtl/flexmac_product.v rtl/flexmac_baselines.v build/classifier_unsigned_bug.v tests/tb_classifier_directed.v
if vvp build/classifier_negative.vvp > build/classifier_negative.log 2>&1; then
    echo 'FAIL: unsigned argmax bug was not rejected' >&2
    exit 1
fi
grep -q 'negative-score/tie selection failed' build/classifier_negative.log
echo 'PASS negative control: unsigned argmax bug rejected'

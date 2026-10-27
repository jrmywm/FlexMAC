#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
sha256sum rtl/flexmac_agreement.v rtl/digits_agreement_bounds.v tests/tb_agreement.v \
    model/agreement/*.hex model/agreement/feasibility.json > build/agreement_sources.log
iverilog -g2012 -s tb_agreement -o build/agreement.vvp \
    rtl/flexmac_agreement.v rtl/digits_agreement_bounds.v tests/tb_agreement.v
vvp build/agreement.vvp | tee build/agreement.log
sed 's/difference >= extended_threshold/difference > extended_threshold/' \
    rtl/flexmac_agreement.v > build/agreement_boundary_bug.v
iverilog -g2012 -s tb_agreement -o build/agreement_boundary_bug.vvp \
    build/agreement_boundary_bug.v rtl/digits_agreement_bounds.v tests/tb_agreement.v
if vvp build/agreement_boundary_bug.vvp > build/agreement_negative.log 2>&1; then
    echo 'FAIL: certificate boundary bug was not rejected' >&2
    exit 1
fi
grep -q 'certificate mismatch' build/agreement_negative.log
echo 'PASS negative control: certificate boundary bug rejected'

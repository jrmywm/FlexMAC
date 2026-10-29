#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build/synthetic
sha256sum rtl/flexmac_synthetic.v tests/tb_synthetic.v scripts/check_synthetic.sh > build/synthetic/sources.log
for shape in 32:4 64:10 128:10; do
  IFS=: read -r features classes <<< "$shape"
  for schedule in 0 1 2; do
    iverilog -g2012 -s tb_synthetic -Ptb_synthetic.FEATURES="$features" -Ptb_synthetic.CLASSES="$classes" -Ptb_synthetic.SCHEDULE="$schedule" -o build/synthetic/run.vvp rtl/flexmac_synthetic.v tests/tb_synthetic.v
    vvp build/synthetic/run.vvp +report="build/synthetic/${features}_${classes}_${schedule}.csv" | tee "build/synthetic/${features}_${classes}_${schedule}.log"
  done
done
sed 's/pending>best/$unsigned(pending)>$unsigned(best)/g' rtl/flexmac_synthetic.v > build/synthetic/mutant.v
iverilog -g2012 -s tb_synthetic -Ptb_synthetic.SCHEDULE=2 -o build/synthetic/mutant.vvp build/synthetic/mutant.v tests/tb_synthetic.v
if vvp build/synthetic/mutant.vvp +report=build/synthetic/negative.csv > build/synthetic/negative.log 2>&1; then
  echo 'FAIL unsigned comparison mutant was not detected' >&2;exit 1
fi
grep -Eq 'wrong winner/missing score|signed final winner' build/synthetic/negative.log

"""Generic synthesis only. Counts are not standard-cell area or timing."""
from pathlib import Path
import csv
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT/'build'


def main():
    if not shutil.which('yosys'):
        print('BLOCKED: yosys is required.',file=sys.stderr)
        return 2
    BUILD.mkdir(exist_ok=True)
    version = subprocess.check_output(['yosys','-V'],text=True).strip()
    designs = [('shared_product','flexmac_product',None),
               ('mux_product','flexmac_product_mux',None),
               ('fixed_int8','flexmac_product_int8',None),
               ('fixed_int4x2','flexmac_product_int4x2',None),
               ('stream_shared','flexmac_stream',0),
               ('stream_mux','flexmac_stream',1),
               ('classifier_shared','flexmac_classifier',0),
               ('classifier_mux','flexmac_classifier',1),
               ('classifier_fixed_int8','flexmac_classifier_int8',None),
               ('classifier_fixed_int4','flexmac_classifier_int4',None),
               ('agreement_pairwise','flexmac_agreement',None),
               ('adaptive_shared','flexmac_adaptive',0),
               ('adaptive_mux','flexmac_adaptive',1),
               ('adaptive_always_int8','flexmac_adaptive',2),
               ('int8_two_lane','flexmac_adaptive',3)]
    rows = []
    for name,top,impl in designs:
        # Preserve the original source set for the six arithmetic experiments.
        # Reading unrelated modules can perturb generic optimization ordering;
        # classifier additions must not silently redefine those comparisons.
        sources = 'rtl/flexmac_product.v rtl/flexmac_baselines.v rtl/flexmac_stream.v'
        if top == 'flexmac_agreement':
            sources = 'rtl/flexmac_agreement.v rtl/digits_agreement_bounds.v'
        if top == 'flexmac_adaptive':
            sources = ('rtl/flexmac_product.v rtl/flexmac_baselines.v rtl/flexmac_int8x2.v rtl/digits_model_rom.v '
                       'rtl/digits_residual_rom.v rtl/digits_pixel_quantizer.v rtl/flexmac_adaptive.v')
        if top.startswith('flexmac_classifier'):
            sources += ' rtl/digits_model_rom.v rtl/flexmac_classifier.v'
        if top in ('flexmac_classifier_int8', 'flexmac_classifier_int4'):
            sources += ' rtl/flexmac_classifier_fixed.v'
        commands = f'read_verilog {sources}; '
        if impl is not None:
            if top == 'flexmac_adaptive' and impl in (2,3):
                commands += f'chparam -set FORCE_INT8 1 -set INT8_LANES {2 if impl == 3 else 1} {top}; '
            else:
                commands += f'chparam -set PRODUCT_IMPL {impl} {top}; '
        commands += f'synth -top {top} -flatten -noabc; check -assert; write_json build/{name}.json'
        subprocess.run(['yosys','-Q','-l',str(BUILD/f'synthesis_{name}.log'),'-p',commands],
                       cwd=ROOT,check=True,stdout=subprocess.DEVNULL,timeout=240 if top == 'flexmac_adaptive' else 120)
        module = json.loads((BUILD/f'{name}.json').read_text())[ 'modules'][top]
        types = [c['type'] for c in module['cells'].values()]
        assert all(t.startswith('$_') for t in types), (name,'Unmapped cells')
        assert not any('LATCH' in t.upper() for t in types), (name,'Latch inferred')
        rows.append({'design':name,'generic_cells':len(types),
                     'register_cells':sum('DFF' in t.upper() for t in types),'yosys':version})
        print(f'PASS synthesis {name}: {len(types)} generic cells')
    with (BUILD/'generic_synthesis.csv').open('w',newline='',encoding='utf-8') as f:
        writer = csv.DictWriter(f,fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    print('Generic counts are not mapped area, clock frequency, power, or classifier accuracy.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

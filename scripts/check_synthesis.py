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
               ('classifier_mux','flexmac_classifier',1)]
    rows = []
    for name,top,impl in designs:
        commands = ('read_verilog rtl/flexmac_product.v rtl/flexmac_baselines.v '
                    'rtl/flexmac_stream.v rtl/digits_model_rom.v rtl/flexmac_classifier.v; ')
        if impl is not None:
            commands += f'chparam -set PRODUCT_IMPL {impl} {top}; '
        commands += f'synth -top {top} -flatten -noabc; check -assert; write_json build/{name}.json'
        subprocess.run(['yosys','-Q','-l',str(BUILD/f'synthesis_{name}.log'),'-p',commands],
                       cwd=ROOT,check=True,stdout=subprocess.DEVNULL,timeout=120)
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

"""Zero-delay black-box replay of all mapped raw-input classifiers."""
from pathlib import Path
import csv
import hashlib
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from check_mapping import DESIGNS,REFERENCE_CSV,MAP,digest,save


def main():
    metadata=json.loads((MAP/'metadata.json').read_text())
    if metadata.get('status')!='complete': raise ValueError('Mapping/timing did not finish')
    manifest=json.loads((MAP/'manifest.json').read_text())
    if {r['design'] for r in manifest}!=set(DESIGNS): raise ValueError('Wrong mapped netlist set')
    lib=MAP/'library_pruned.lib'
    if digest(lib)!=metadata['library_pruned_sha256']: raise ValueError('Library changed after mapping')
    for path,sha in metadata['rtl_sha256'].items():
        if digest(ROOT/path)!=sha: raise ValueError('RTL changed after mapping')
    for path,sha in metadata['fixture_sha256'].items():
        if digest(ROOT/path)!=sha: raise ValueError('Fixture changed after mapping')
    reports=[]
    for row in manifest:
        name=row['design'];netlist=ROOT/row['netlist'];params=row['params']
        if params!=DESIGNS[name] or digest(netlist)!=row['netlist_sha256']:
            raise ValueError(f'{name}: mapped source/config changed')
        flat=MAP/f'{name}.gates.v'
        commands=(f'read_liberty -overwrite -ignore_miss_func -ignore_miss_dir {lib}; '
            f'read_verilog -defer {netlist}; hierarchy -check -top flexmac_mapped; '
            f'flatten; opt_clean; check -assert; write_verilog -noattr {flat}')
        subprocess.run(['yosys','-Q','-l',str(MAP/f'{name}.replay_yosys.log'),'-p',commands],
            cwd=ROOT,check=True,stdout=subprocess.DEVNULL,timeout=300)
        if 'sky130_fd_sc_hd__' in flat.read_text(): raise ValueError('Library cells remain after expansion')
        binary=MAP/f'{name}.vvp'
        compile_args=['iverilog','-g2012','-DGATE_LEVEL','-s','tb_adaptive']
        compile_args += [f'-Ptb_adaptive.{k}={v}' for k,v in params.items()]
        subprocess.run(compile_args+['-o',str(binary),str(flat),str(ROOT/'tests/tb_adaptive.v')],
                       cwd=ROOT,check=True,timeout=120)
        replay=MAP/f'{name}.replay.csv'
        result=subprocess.run(['vvp',str(binary),f'+report={replay}'],cwd=ROOT,check=True,
                              capture_output=True,text=True,timeout=600)
        save(MAP/f'{name}.replay.log',result.stdout+result.stderr)
        original=ROOT/'build'/REFERENCE_CSV[name]
        if digest(original)!=row['rtl_reference_sha256']: raise ValueError('RTL reference changed after timing analysis')
        expected=list(csv.DictReader(original.open()));actual=list(csv.DictReader(replay.open()))
        if len(actual)!=359 or actual!=expected: raise ValueError(f'{name}: mapped replay differs from RTL')
        reports.append({'design':name,'frames':len(actual),'rtl_csv_sha256':digest(original),
                        'mapped_csv_sha256':digest(replay),'netlist_sha256':digest(netlist),
                        'gate_model_sha256':digest(flat),'passed':True})
        print(f'PASS mapped replay {name}: 359 decisions, flags and exact cycle counts; reset, invalid-input and stall checks',flush=True)
    save(MAP/'gate_replay.json',json.dumps({'source_commit':metadata['source_commit'],
        'mapping_manifest_sha256':digest(MAP/'manifest.json'),
        'scope':'zero-delay functional replay; no internal score probes or SDF timing',
        'designs':reports},indent=2)+'\n')
    return 0


if __name__=='__main__':
    raise SystemExit(main())

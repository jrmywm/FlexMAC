"""Zero-delay mapped replay: full compiled two-state and separate four-state checks."""
from pathlib import Path
import argparse
import csv
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from check_mapping import DESIGNS,REFERENCE_CSV,MAP,digest,save


def run(args, log, timeout):
    with Path(log).open('w') as out:
        subprocess.run(args,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,
                       check=True,timeout=timeout)


def read_csv(path):
    with Path(path).open() as source:
        return list(csv.DictReader(source))


def four_state_selection():
    """All calibration fallbacks plus one certified example per predicted class."""
    def hexes(name):
        return [int(x,16) for x in (ROOT/'model/agreement'/name).read_text().split()]
    accepted=hexes('expected_conditioned.hex')
    winners=hexes('reference_int8.hex')
    calibration=range(1078,1437)
    selected={i for i in calibration if not accepted[i]}
    for label in range(10):
        selected.add(next(i for i in calibration if accepted[i] and winners[i]==label))
    return sorted(selected)


def validate_inputs():
    metadata=json.loads((MAP/'metadata.json').read_text())
    if metadata.get('status')!='complete':
        raise ValueError('Mapping/timing did not finish')
    manifest=json.loads((MAP/'manifest.json').read_text())
    if len(manifest)!=len(DESIGNS) or {r['design'] for r in manifest}!=set(DESIGNS):
        raise ValueError('Wrong mapped netlist set')
    if digest(MAP/'library_pruned.lib')!=metadata['library_pruned_sha256']:
        raise ValueError('Library changed after mapping')
    for kind in ('rtl_sha256','fixture_sha256','verification_sha256'):
        for path,sha in metadata.get(kind,{}).items():
            if digest(ROOT/path)!=sha: raise ValueError(f'Source changed: {path}')
    for row in manifest:
        name=row['design']
        if row['params']!=DESIGNS[name] or digest(ROOT/row['netlist'])!=row['netlist_sha256']:
            raise ValueError(f'{name}: mapped source/config changed')
        if digest(ROOT/'build'/REFERENCE_CSV[name])!=row['rtl_reference_sha256']:
            raise ValueError(f'{name}: RTL reference changed')
    return metadata,manifest


def replay(row, metadata):
    name=row['design'];params=row['params']
    bench=ROOT/row.get('testbench','tests/tb_adaptive.v')
    top=row.get('testbench_top','tb_adaptive')
    flat=MAP/f'{name}.gates.v'
    commands=(f'read_liberty -overwrite -ignore_miss_func -ignore_miss_dir {MAP/"library_pruned.lib"}; '
        f'read_verilog -defer {ROOT/row["netlist"]}; hierarchy -check -top flexmac_mapped; '
        f'flatten; opt_clean; check -assert; write_verilog -noattr {flat}')
    run(['yosys','-Q','-p',commands],MAP/f'{name}.conversion.log',300)
    if 'sky130_fd_sc_hd__' in flat.read_text():
        raise ValueError('Library cells remain after expansion')
    expected=read_csv(ROOT/'build'/REFERENCE_CSV[name])
    if len(expected)!=359: raise ValueError('Expected full calibration RTL reference')
    obj=MAP/f'{name}.obj'
    run(['verilator','--binary','--timing','--assert','-Wno-fatal','-O3',
         '--output-split','15000','--output-split-cfuncs','100','-j','2',
         '-DGATE_LEVEL','--top-module',top,'--Mdir',str(obj),'-o','replay']
        +[f'-G{k}={v}' for k,v in params.items()]
        +[str(flat),str(bench)],
        MAP/f'{name}.verilator.log',900)
    full_csv=MAP/f'{name}.replay.csv'
    run([str(obj/'replay'),f'+report={full_csv}','+progress',
         '+verilator+rand+reset+2','+verilator+seed+20261027'],
        MAP/f'{name}.replay.log',600)
    if read_csv(full_csv)!=expected:
        raise ValueError(f'{name}: compiled replay differs from RTL')
    # Four-state execution is full for smaller baselines and stratified for adaptive.
    indices=list(range(1078,1437)) if params.get('FORCE_INT8',1) else four_state_selection()
    selection=MAP/f'{name}.indices.hex'
    save(selection,''.join(f'{i:08x}\n' for i in indices))
    binary=MAP/f'{name}.vvp'
    run(['iverilog','-g2012','-DGATE_LEVEL','-s',top]
        +[f'-P{top}.{k}={v}' for k,v in params.items()]
        +['-o',str(binary),str(flat),str(bench)],
        MAP/f'{name}.icarus_compile.log',180)
    four_csv=MAP/f'{name}.icarus.csv'
    run(['vvp',str(binary),f'+report={four_csv}',f'+indices={selection}',
         f'+count={len(indices)}','+progress'],MAP/f'{name}.icarus.log',900)
    wanted=[r for r in expected if int(r['sample']) in set(indices)]
    if read_csv(four_csv)!=wanted:
        raise ValueError(f'{name}: four-state replay differs from RTL')
    versions={}
    for tool,args in [('verilator',['--version']),('iverilog',['-V']),('yosys',['-V'])]:
        result=subprocess.run([tool]+args,cwd=ROOT,capture_output=True,text=True,check=True)
        versions[tool]=(result.stdout+result.stderr).splitlines()[0]
    report={'design':name,'source_commit':metadata['source_commit'],'frames':359,
        'full_backend':'Verilator two-state, randomized initialization seed 20261027',
        'four_state_backend':'Icarus Verilog','four_state_frames':len(indices),
        'four_state_indices':indices,'four_state_scope':
            'all calibration frames' if params.get('FORCE_INT8',1) else
            'all calibration fallbacks plus one certified example per INT8 predicted class',
        'rtl_csv_sha256':row['rtl_reference_sha256'],
        'mapped_csv_sha256':digest(full_csv),'four_state_csv_sha256':digest(four_csv),
        'netlist_sha256':row['netlist_sha256'],'gate_model_sha256':digest(flat),
        'versions':versions,'passed':True}
    save(MAP/f'{name}.replay.json',json.dumps(report,indent=2)+'\n')
    print(f'PASS {name}: 359 compiled frames and {len(indices)} four-state frames; exact decisions, flags, cycles and interface checks',flush=True)


def aggregate(metadata, manifest):
    reports=[]
    for row in manifest:
        name=row['design']
        report=json.loads((MAP/f'{name}.replay.json').read_text())
        expected_indices=list(range(1078,1437)) if row['params'].get('FORCE_INT8',1) else four_state_selection()
        if (report['design']!=name or report['source_commit']!=metadata['source_commit']
                or report['netlist_sha256']!=row['netlist_sha256']
                or report['rtl_csv_sha256']!=row['rtl_reference_sha256']
                or report['frames']!=359 or report['four_state_indices']!=expected_indices
                or report['four_state_frames']!=len(expected_indices) or report['passed'] is not True):
            raise ValueError(f'{name}: incomplete or stale replay report')
        for filename,key in [('replay.csv','mapped_csv_sha256'),
                             ('icarus.csv','four_state_csv_sha256'),('gates.v','gate_model_sha256')]:
            if digest(MAP/f'{name}.{filename}')!=report[key]:
                raise ValueError(f'{name}: changed replay artifact')
        expected=read_csv(ROOT/'build'/REFERENCE_CSV[name])
        if read_csv(MAP/f'{name}.replay.csv')!=expected:
            raise ValueError(f'{name}: full replay mismatch during aggregation')
        if read_csv(MAP/f'{name}.icarus.csv')!=[r for r in expected if int(r['sample']) in set(expected_indices)]:
            raise ValueError(f'{name}: four-state mismatch during aggregation')
        reports.append(report)
    save(MAP/'gate_replay.json',json.dumps({'source_commit':metadata['source_commit'],
        'mapping_manifest_sha256':digest(MAP/'manifest.json'),
        'scope':'zero-delay functional replay; full two-state plus separate four-state coverage; no internal score probes or SDF',
        'designs':reports},indent=2)+'\n')
    print(f'PASS all {len(reports)} mapped configurations and replay artifact hashes',flush=True)


def main():
    global MAP,DESIGNS,REFERENCE_CSV
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path)
    parser.add_argument('--design')
    parser.add_argument('--aggregate-only',action='store_true')
    args=parser.parse_args()
    if args.study:
        study=json.loads((ROOT/args.study).read_text())
        MAP=ROOT/study['map_directory'];DESIGNS=study['designs'];REFERENCE_CSV=study['reference_csv']
    if args.design is not None and args.design not in DESIGNS: parser.error('Unknown mapped design')
    if args.design and args.aggregate_only: parser.error('Choose replay or aggregation')
    metadata,manifest=validate_inputs()
    if not args.aggregate_only:
        for row in manifest:
            if args.design is None or row['design']==args.design: replay(row,metadata)
    if args.design is None: aggregate(metadata,manifest)
    return 0


if __name__=='__main__':
    raise SystemExit(main())

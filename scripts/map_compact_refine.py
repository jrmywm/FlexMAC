"""Same-library area/timing, full compiled and selected four-state mapped replay."""
import csv,gzip,hashlib,json,math,os,shutil,subprocess
from pathlib import Path
import check_mapping as m

root=m.ROOT; out=root/'build/compact_refinement/map';out.mkdir(parents=True,exist_ok=True);m.MAP=out
cfg=json.loads(m.CONFIG.read_text());src=root/cfg['library_path'];sta=os.environ.get('STA') or shutil.which('sta')
if not sta or not shutil.which('yosys') or not src.exists():raise SystemExit('BLOCKED: pinned EDA tools required')
if m.digest(src)!=cfg['library_sha256']:raise ValueError('library hash mismatch')
for key,path in (('opensta_commit','.tools/OpenSTA'),('cudd_commit','.tools/cudd')):
    if subprocess.check_output(['git','-C',str(root/path),'rev-parse','HEAD'],text=True).strip()!=cfg[key]:raise ValueError('tool revision mismatch')
libtext,areas,seq=m.prepare_library(gzip.decompress(src.read_bytes()).decode());lib=out/'library_pruned.lib';m.save(lib,libtext)
common_sources=['rtl/digits_model_rom.v','rtl/digits_pixel_quantizer.v']
specs=[('compact','flexmac_compact_refine',common_sources+['rtl/flexmac_product.v','rtl/digits_agreement_bounds.v','rtl/flexmac_compact_refine.v'],'tests/tb_compact_refine.v',[],root/'build/compact_refinement/rtl.csv'),
       ('int8x4','flexmac_int8x4_scorepipe',common_sources+['rtl/flexmac_baselines.v','rtl/flexmac_int8x4_scorepipe.v'],'tests/tb_compact_refine.v',['-DBASELINE4'],root/'build/compact_refinement/baseline4_all.csv'),
       ('int8x2','flexmac_int8x2_scorepipe',common_sources+['rtl/flexmac_baselines.v','rtl/flexmac_int8x2.v','rtl/flexmac_int8x2_scorepipe.v'],'tests/tb_scorepipe.v',[],root/'build/scorepipe.csv')]
rows=[]
def read(path):
    with path.open() as f:return list(csv.DictReader(f))
for name,top,sources,bench,defines,reference in specs:
    row=m.map_design(name,{},lib,areas,seq,cfg,top=top,sources=sources)
    low=.25;test=m.sta_design(name,low,'negative',sta,lib,cfg)
    if test['setup_met']:raise ValueError('negative timing control passed')
    high=cfg['mapping_target_ns'];test=m.sta_design(name,high,'target',sta,lib,cfg)
    while not test['setup_met']:
        low=high;high*=2
        if high>320:raise ValueError('no passing period')
        test=m.sta_design(name,high,f'expand{high}',sta,lib,cfg)
    n=0
    while high-low>cfg['period_resolution_ns']:
        mid=(low+high)/2;n+=1;test=m.sta_design(name,mid,f'search{n}',sta,lib,cfg)
        if test['setup_met']:high=mid
        else:low=mid
    passed=m.sta_design(name,high,'pass',sta,lib,cfg,details=True)
    if not passed['setup_met'] or not passed['hold_met']:raise ValueError('endpoint setup/hold failure')
    traces=[r for r in read(reference) if 1078<=int(r['sample'])<1437]
    if len(traces)!=359:raise ValueError('missing calibration traces')
    cycles=[int(r.get('cycles',r.get('command_to_valid_cycles')))-int(r.get('input_gaps',10 if int(r['sample'])%11==0 else 0)) for r in traces]
    row.update(setup_period_fail_ns=low,setup_period_pass_ns=high,setup_wns_at_pass_ns=passed['setup_wns_ns'],hold_wns_at_pass_ns=passed['hold_wns_ns'],mean_cycles=sum(cycles)/359,worst_cycles=max(cycles),mean_latency_ns=sum(cycles)/359*high,reference_sha256=m.digest(reference))
    # Expand the same Liberty cell functions used for mapping. Replay all
    # calibration frames compiled; separately check four-state initialization.
    gates=out/f'{name}.gates.v'
    commands=f'read_liberty -overwrite -ignore_miss_func -ignore_miss_dir {lib}; read_verilog -defer {root/row["netlist"]}; hierarchy -check -top flexmac_mapped; flatten; opt_clean; check -assert; write_verilog -noattr {gates}'
    with (out/f'{name}.conversion.log').open('w') as f:subprocess.run(['yosys','-Q','-p',commands],cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
    if 'sky130_fd_sc_hd__' in gates.read_text():raise ValueError('unexpanded cells')
    tbtop=Path(bench).stem;binary=out/f'{name}.vvp';replay=out/f'{name}.replay.csv'
    obj=out/f'{name}.obj'
    with (out/f'{name}.verilator.log').open('w') as f:
        subprocess.run(['verilator','--binary','--timing','--assert','-Wno-fatal','-O3','--output-split','15000','--output-split-cfuncs','100','-j','2','-DGATE_LEVEL',*defines,'--top-module',tbtop,'--Mdir',str(obj),'-o','replay',str(gates),str(root/bench)],cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=900)
    with (out/f'{name}.replay.log').open('w') as f:
        subprocess.run([str(obj/'replay'),f'+report={replay}','+verilator+rand+reset+2','+verilator+seed+20261029'],cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
    if read(replay)!=traces:raise ValueError('compiled mapped replay mismatch')
    compact_traces=read(root/'build/compact_refinement/rtl.csv')
    selected={1078,1436}
    for key in ('prediction','exact_classes'):
        for value in {r[key] for r in compact_traces}:
            selected.add(next(int(r['sample']) for r in compact_traces if r[key]==value))
    selected=sorted(selected);selection=out/f'{name}.indices.hex'
    m.save(selection,''.join(f'{i:08x}\n' for i in selected));four_csv=out/f'{name}.icarus.csv'
    with (out/f'{name}.compile.log').open('w') as f:subprocess.run(['iverilog','-g2012','-DGATE_LEVEL',*defines,'-s',tbtop,'-o',str(binary),str(gates),bench],cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    with (out/f'{name}.icarus.log').open('w') as f:subprocess.run(['vvp',str(binary),f'+report={four_csv}',f'+indices={selection}',f'+count={len(selected)}'],cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=900)
    if read(four_csv)!=[r for r in traces if int(r['sample']) in selected]:raise ValueError('four-state mapped replay mismatch')
    row.update(mapped_replay_frames=359,mapped_replay_sha256=m.digest(replay),four_state_frames=len(selected),four_state_indices=selected,four_state_sha256=m.digest(four_csv),gate_model_sha256=m.digest(gates))
    rows.append(row);print(f'PASS {name}: {row["area_um2"]:.1f}um2, {high:.4f}ns, {row["mean_latency_ns"]:.1f}ns mean, full compiled and {len(selected)} four-state frames',flush=True)
common=math.ceil(max(r['setup_period_pass_ns'] for r in rows)*1.1*2)/2
for r in rows:
    t=m.sta_design(r['design'],common,'common',sta,lib,cfg,details=True)
    if not t['setup_met'] or not t['hold_met'] or t['electrical_violations_reported']:raise ValueError('common clock failed')
    r.update(common_period_ns=common,common_mean_latency_ns=r['mean_cycles']*common,common_setup_wns_ns=t['setup_wns_ns'],common_hold_wns_ns=t['hold_wns_ns'])
provenance={p:m.digest(root/p) for p in dict.fromkeys([p for _,_,s,b,_,_ in specs for p in s+[b]]+['scripts/map_compact_refine.py','scripts/screen_compact_refinement.py','scripts/check_compact_refine.sh','model/certification.py','eda/toolchain.json']+[p.relative_to(root).as_posix() for p in (root/'model/agreement').glob('*.hex')])}
report={'status':'complete','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=root).strip(),'scope':'frozen calibration, pre-layout typical corner, ideal clock and wires; full zero-delay compiled replay plus selected four-state replay; no power claim','source_sha256':provenance,'library_sha256':m.digest(src),'sta_binary_sha256':m.digest(sta),'yosys_version':subprocess.check_output(['yosys','-V'],text=True).strip(),'config':cfg,'rows':rows}
m.save(out/'results.json',json.dumps(report,indent=2)+'\n')

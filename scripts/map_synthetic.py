"""Map and time three synthetic schedules under identical pinned constraints."""
from pathlib import Path
import csv,gzip,json,math,os,shutil,subprocess,hashlib
import check_mapping as m
root=m.ROOT; out=root/'build/synthetic/map';out.mkdir(parents=True,exist_ok=True);m.MAP=out
cfg=json.loads(m.CONFIG.read_text()); src=root/cfg['library_path']
sta=os.environ.get('STA') or shutil.which('sta')
if not sta or not shutil.which('yosys') or not src.exists(): raise SystemExit('BLOCKED: pinned EDA tools and library required')
if m.digest(src)!=cfg['library_sha256']: raise ValueError('library hash mismatch')
for key,path in (('opensta_commit','.tools/OpenSTA'),('cudd_commit','.tools/cudd')):
    if subprocess.check_output(['git','-C',str(root/path),'rev-parse','HEAD'],text=True).strip()!=cfg[key]: raise ValueError('tool revision mismatch')
libtext,areas,seq=m.prepare_library(gzip.decompress(src.read_bytes()).decode());lib=out/'library_pruned.lib';m.save(lib,libtext)
rows=[]
spec=json.loads((root/'eda/synthetic_study.json').read_text())
m.save(out/'status.json',json.dumps({'status':'in_progress'})+'\n')
for features,classes in spec['shapes']:
    group=[]
    for schedule in range(3):
        name=f'synthetic_{features}_{classes}_{schedule}'
        row=m.map_design(name,{'FEATURES':features,'CLASSES':classes,'SCHEDULE':schedule},lib,areas,seq,cfg,top='flexmac_synthetic',sources=['rtl/flexmac_synthetic.v'])
        low=.25; test=m.sta_design(name,low,'tight',sta,lib,cfg)
        if test['setup_met']: raise ValueError('negative timing control unexpectedly passed')
        high=cfg['mapping_target_ns'];test=m.sta_design(name,high,'target',sta,lib,cfg)
        while not test['setup_met']:
            low=high;high*=2
            if high>320: raise ValueError('no passing period')
            test=m.sta_design(name,high,f'expand_{high}',sta,lib,cfg)
        count=0
        while high-low>cfg['period_resolution_ns']:
            mid=(high+low)/2;count+=1;test=m.sta_design(name,mid,f'search_{count}',sta,lib,cfg)
            if test['setup_met']: high=mid
            else: low=mid
        reference=root/f'build/synthetic/{features}_{classes}_{schedule}.csv'
        with reference.open() as f: traces=list(csv.DictReader(f))
        measured={int(r['cycles'])-int(r['input_gaps']) for r in traces}
        expected=features+features//2*classes+(classes if schedule==1 else 1 if schedule==2 else 0)
        if len(traces)!=24 or measured!={expected}: raise ValueError('Missing or inconsistent RTL cycle evidence')
        cycles=measured.pop()
        passed=m.sta_design(name,high,'pass',sta,lib,cfg,details=True)
        if not passed['setup_met'] or not passed['hold_met']: raise ValueError('Passing endpoint setup/hold failed')
        row.update(features=features,classes=classes,schedule=schedule,cycles=cycles,rtl_frames=len(traces),rtl_reference_sha256=m.digest(reference),setup_period_fail_ns=low,setup_period_pass_ns=high,setup_wns_at_pass_ns=passed['setup_wns_ns'],hold_wns_at_pass_ns=passed['hold_wns_ns'],latency_at_pass_ns=cycles*high)
        group.append(row)
    common=math.ceil(max(r['setup_period_pass_ns'] for r in group)*1.1*2)/2
    for row in group:
        check=m.sta_design(row['design'],common,'common',sta,lib,cfg,details=True)
        if not check['setup_met'] or not check['hold_met']: raise ValueError('common setup/hold fails')
        if check['electrical_violations_reported']: raise ValueError('Common-clock electrical violation')
        row.update(common_period_ns=common,common_setup_wns_ns=check['setup_wns_ns'],common_hold_wns_ns=check['hold_wns_ns'],electrical_violations_reported=check['electrical_violations_reported'],latency_at_common_ns=row['cycles']*common)
    rows.extend(group)
metadata={'status':'complete','scope':'synthetic runtime features and fixed weights; RTL verification only; pre-layout typical corner; ideal wires and clock',
 'tool_config':cfg,'library_sha256':m.digest(src),'sta_binary_sha256':m.digest(sta),
 'yosys_version':subprocess.check_output(['yosys','-V'],text=True).strip(),
 'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
 'source_sha256':{p:m.digest(root/p) for p in ['rtl/flexmac_synthetic.v','tests/tb_synthetic.v','scripts/check_synthetic.sh','scripts/map_synthetic.py','scripts/check_mapping.py','eda/synthetic_study.json']},'rows':rows}
m.save(out/'results.json',json.dumps(metadata,indent=2)+'\n')
with (out/'results.csv').open('w',newline='') as f:
    flat=[{k:v for k,v in r.items() if k!='params'} for r in rows];w=csv.DictWriter(f,fieldnames=flat[0]);w.writeheader();w.writerows(flat)
print('PASS synthetic mapped setup brackets and common setup/hold')
m.save(out/'status.json',json.dumps({'status':'complete'})+'\n')

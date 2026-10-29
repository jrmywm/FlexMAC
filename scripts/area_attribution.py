"""Diagnostic hierarchy-preserved adaptive map; categories are not flattened attribution."""
from pathlib import Path
import collections, csv, gzip, json, subprocess
import check_mapping as m

root=m.ROOT
out=root/'build/area_attribution'
out.mkdir(parents=True,exist_ok=True)
cfg=json.loads(m.CONFIG.read_text())
source=root/cfg['library_path']
if not source.exists() or m.digest(source)!=cfg['library_sha256']:
    raise SystemExit('BLOCKED: pinned Liberty library missing or mismatched')
libtext,areas,seq=m.prepare_library(gzip.decompress(source.read_bytes()).decode())
lib=out/'library_pruned.lib';m.save(lib,libtext)
m.MAP=out
flat=m.map_design('adaptive_flat',{'FORCE_INT8':0,'INT8_LANES':1,'PRODUCT_IMPL':0},lib,areas,seq,cfg)
constr=out/'abc.constr'
script=out/'adaptive_hierarchy.ys'
commands=[f'read_liberty -lib -overwrite {lib}',f'read_verilog {" ".join(m.SOURCES)}',
          'chparam -set FORCE_INT8 0 -set INT8_LANES 1 -set PRODUCT_IMPL 0 flexmac_adaptive',
          'synth -top flexmac_adaptive -noabc',f'dfflibmap -liberty {lib}',
          f"abc -liberty {lib} -D {round(cfg['mapping_target_ns']*1000)} -constr {constr}",
          'opt_clean -purge','check -assert',f'write_json {out}/adaptive_hierarchy.json',
          'flatten',f'write_json {out}/adaptive_hierarchy_flattened.json']
m.save(script,';\n'.join(commands)+'\n')
subprocess.run(['yosys','-Q','-l',str(out/'adaptive_hierarchy.yosys.log'),'-s',str(script)],cwd=root,check=True,timeout=900)
modules=json.loads((out/'adaptive_hierarchy.json').read_text())['modules']
counts=collections.Counter()
def walk(name,bucket='remaining_top'):
    for cell in modules[name]['cells'].values():
        typ=cell['type']
        if typ in areas:
            counts[bucket,typ]+=1
        elif typ in modules:
            low=typ.lower()
            group=('residual_tables' if 'digits_residual' in low else
                   'model_tables' if 'digits_model_rom' in low else
                   'preprocessing' if 'digits_pixel_quantizer' in low else
                   'arithmetic' if 'flexmac_product' in low else bucket)
            walk(typ,group)
        else: raise ValueError(f'Unmapped cell {typ} in {name}')
walk('flexmac_adaptive')
rows=[]
for bucket in sorted({b for b,_ in counts}):
    n=sum(v for (b,c),v in counts.items() if b==bucket)
    a=sum(areas[c]*v for (b,c),v in counts.items() if b==bucket)
    q=sum(areas[c]*v for (b,c),v in counts.items() if b==bucket and c in seq)
    rows.append(dict(bucket=bucket,cells=n,area_um2=a,sequential_area_um2=q,combinational_area_um2=a-q))
total=sum(r['area_um2'] for r in rows)
flat_diagnostic=json.loads((out/'adaptive_hierarchy_flattened.json').read_text())['modules']['flexmac_adaptive']
direct=collections.Counter(c['type'] for c in flat_diagnostic['cells'].values())
recursive=collections.Counter()
for (bucket,typ),number in counts.items(): recursive[typ]+=number
if direct!=recursive: raise ValueError('Hierarchical count differs from flattened diagnostic instance count')
direct_area=sum(areas[c]*n for c,n in direct.items())
if abs(direct_area-total)>1e-6: raise ValueError('Area buckets do not reconcile')
result={'scope':'hierarchy-preserved diagnostic mapping; not an attribution of flattened cells',
        'hierarchical_area_um2':total,'hierarchical_cells':sum(r['cells'] for r in rows),
        'flattened':flat,'rows':rows,'library_sha256':m.digest(source),
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'yosys_version':subprocess.check_output(['yosys','-V'],text=True).strip(),
        'independent_flattened_diagnostic_area_um2':direct_area,
        'source_sha256':{p:m.digest(root/p) for p in m.SOURCES+['scripts/area_attribution.py','scripts/check_mapping.py','eda/toolchain.json']},
        'limitation':'remaining_top includes feature storage, interval checking and control; ABC cannot optimize across preserved boundaries'}
m.save(out/'attribution.json',json.dumps(result,indent=2)+'\n')
with (out/'attribution.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
print('PASS hierarchy counts reconciled to diagnostic total; flattened total is separately reported')

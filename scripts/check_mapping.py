"""Pinned-library mapping and directly tested setup-period brackets; no RTL changes."""
from pathlib import Path
import collections
import csv
import fnmatch
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT/'build/map'
CONFIG = ROOT/'eda/toolchain.json'
SOURCES = ['rtl/flexmac_product.v','rtl/flexmac_baselines.v','rtl/flexmac_int8x2.v',
           'rtl/digits_model_rom.v','rtl/digits_residual_rom.v',
           'rtl/digits_pixel_quantizer.v','rtl/flexmac_adaptive.v']
DESIGNS = {
    'int8_single': {'FORCE_INT8':1,'INT8_LANES':1,'PRODUCT_IMPL':0},
    'int8_two_lane': {'FORCE_INT8':1,'INT8_LANES':2,'PRODUCT_IMPL':0},
    'adaptive_shared': {'FORCE_INT8':0,'INT8_LANES':1,'PRODUCT_IMPL':0},
    'adaptive_mux': {'FORCE_INT8':0,'INT8_LANES':1,'PRODUCT_IMPL':1}}
REFERENCE_CSV = {'int8_single':'adaptive_always_int8.csv','int8_two_lane':'int8_two_lane.csv',
                 'adaptive_shared':'adaptive_shared.csv','adaptive_mux':'adaptive_mux.csv'}
DONT_USE = ('sky130_fd_sc_hd__probe_p_8','sky130_fd_sc_hd__probec_p_8','sky130_fd_sc_hd__lpflow_*')
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, text):
    Path(path).write_text(text,encoding='utf-8',newline='\n')


def blocks(text, kind):
    """Named Liberty groups with balanced braces (including nested timing tables)."""
    pattern=re.compile(r'(?m)^[ \t]*'+kind+r'\s*\(\s*"?([^"\s)]+)"?\s*\)\s*\{')
    for match in pattern.finditer(text):
        depth=1; pos=match.end(); quoted=False; escaped=False
        while depth:
            ch=text[pos]
            if escaped: escaped=False
            elif ch=='\\' and quoted: escaped=True
            elif ch=='"': quoted=not quoted
            elif not quoted: depth+=(ch=='{')-(ch=='}')
            pos+=1
        yield match.group(1),match.start(),pos,text[match.start():pos]


def prepare_library(text):
    if not re.search(r'time_unit\s*:\s*"1ns"',text):
        raise ValueError('Expected Liberty time unit 1ns')
    if not re.search(r'capacitive_load_unit\s*\(\s*1(?:\.0+)?\s*,\s*"?pf"?\s*\)',text,re.I):
        raise ValueError('Expected Liberty capacitance unit 1pF')
    removals=[]
    for kind in ('wire_load','wire_load_selection'):
        removals.extend((a,b) for _,a,b,_ in blocks(text,kind))
    for name,a,b,_ in blocks(text,'cell'):
        if any(fnmatch.fnmatch(name,pattern) for pattern in DONT_USE): removals.append((a,b))
    for a,b in sorted(removals,reverse=True): text=text[:a]+text[b:]
    text=re.sub(r'(?m)^[ \t]*default_wire_load[^;]*;\s*\n','',text)
    areas={}; sequential=set()
    for name,_,_,body in blocks(text,'cell'):
        value=re.search(r'\barea\s*:\s*([0-9.eE+-]+)\s*;',body)
        if not value: raise ValueError(f'Missing cell area: {name}')
        areas[name]=float(value.group(1))
        if re.search(r'\b(?:ff|latch)\s*\(',body): sequential.add(name)
    if not areas: raise ValueError('No cells parsed')
    return text,areas,sequential


def map_design(name, params, lib, areas, sequential, cfg):
    netlist=MAP/f'{name}.v'; stats=MAP/f'{name}.json'
    constr=MAP/'abc.constr'
    save(constr,f"set_driving_cell {cfg['input_driving_cell']}\nset_load {cfg['output_load_ff']}\n")
    commands=[f'read_liberty -lib -overwrite {lib}',f'read_verilog {" ".join(SOURCES)}',
              'chparam '+ ' '.join(f'-set {k} {v}' for k,v in params.items())+' flexmac_adaptive',
              'synth -top flexmac_adaptive -flatten -noabc',f'dfflibmap -liberty {lib}',
              f"abc -liberty {lib} -D {round(cfg['mapping_target_ns']*1000)} -constr {constr}",
              'opt_clean -purge','check -assert','rename flexmac_adaptive flexmac_mapped',
              f'write_json {stats}',f'write_verilog -noattr -noexpr {netlist}']
    script=MAP/f'{name}.ys';save(script,';\n'.join(commands)+'\n')
    subprocess.run(['yosys','-Q','-l',str(MAP/f'{name}.yosys.log'),'-s',str(script)],
                   cwd=ROOT,check=True,stdout=subprocess.DEVNULL,timeout=900)
    module=json.loads(stats.read_text())['modules']['flexmac_mapped']
    counts=collections.Counter(c['type'] for c in module['cells'].values())
    unknown=set(counts)-areas.keys()
    if unknown: raise ValueError(f'{name}: unmapped/unknown cells: {unknown}')
    if not counts: raise ValueError('Empty mapped design')
    area=sum(areas[c]*n for c,n in counts.items())
    sequential_area=sum(areas[c]*n for c,n in counts.items() if c in sequential)
    save(MAP/f'{name}.cells.json',json.dumps(dict(sorted(counts.items())),indent=2)+'\n')
    return {'design':name,'params':params,'netlist':netlist.relative_to(ROOT).as_posix(),
            'netlist_sha256':digest(netlist),'mapped_cells':sum(counts.values()),
            'area_um2':area,'sequential_area_um2':sequential_area,
            'combinational_area_um2':area-sequential_area,
            'sequential_cells':sum(n for c,n in counts.items() if c in sequential)}


def sdc_text(period,cfg):
    return (f'create_clock -name clk -period {period:.6f} [get_ports clk]\n'
        f"set_clock_transition {cfg['clock_transition_ns']} [get_clocks clk]\n"
        f"set_clock_uncertainty -setup {cfg['setup_uncertainty_ns']} [get_clocks clk]\n"
        f"set_clock_uncertainty -hold {cfg['hold_uncertainty_ns']} [get_clocks clk]\n"
        'set data_inputs [lsearch -all -inline -not -exact [all_inputs] [get_ports clk]]\n'
        f"set_input_delay -max {period*cfg['io_max_fraction']:.6f} -clock clk $data_inputs\n"
        f"set_input_delay -min {cfg['io_min_ns']} -clock clk $data_inputs\n"
        f"set_output_delay -max {period*cfg['io_max_fraction']:.6f} -clock clk [all_outputs]\n"
        f"set_output_delay -min {cfg['io_min_ns']} -clock clk [all_outputs]\n"
        f"set_driving_cell -lib_cell {cfg['input_driving_cell']} -pin {cfg['input_driving_pin']} $data_inputs\n"
        f"set_load {cfg['output_load_pf']} [all_outputs]\n")


def parse_sta(text):
    if re.search(r'(?im)^\s*Error[: ]',text): raise ValueError('OpenSTA error; inspect log')
    # stderr may be appended after stdout, outside the check_setup marker block.
    if re.search(r'(?im)^.*Warning.*(?:unconstrained|no.clock|missing.*delay|combinational.loop)',text):
        raise ValueError('Timing-constraint warning outside check_setup block')
    check=text.split('CHECK_BEGIN\n',1)[1].split('CHECK_END',1)[0]
    if re.search(r'(?i)warning|unconstrained|no.clock|combinational.loop',check):
        raise ValueError(f'Incomplete/invalid timing constraints: {check}')
    result={}
    for kind,flag in (('setup','max'),('hold','min')):
        match=re.search(r'worst slack '+flag+r'\s+('+NUMBER+r')',text)
        if not match: raise ValueError(f'Missing {kind} slack')
        value=float(match.group(1))
        if not math.isfinite(value): raise ValueError('Non-finite slack')
        result[f'{kind}_wns_ns']=value
        result[f'{kind}_met']=value>=0
    groups={}
    for match in re.finditer(r'(?m)^GROUP (\w+) ('+NUMBER+r') (\S+) (\S+)',text):
        groups[match.group(1)]={'slack_ns':float(match.group(2)),
                              'startpoint':match.group(3),'endpoint':match.group(4)}
    if 'reg2reg' not in groups: raise ValueError('No register-to-register timing paths')
    if abs(min(p['slack_ns'] for p in groups.values())-result['setup_wns_ns'])>0.002:
        raise ValueError('Path groups do not cover global worst setup slack')
    result['groups']=groups
    return result


def sta_design(name, period, tag, sta,lib,cfg,details=False):
    sdc=MAP/f'{name}_{tag}.sdc';save(sdc,sdc_text(period,cfg))
    lines=[f'read_liberty {lib}',f'read_verilog {MAP/name}.v','link_design flexmac_mapped',
           f'read_sdc {sdc}','report_units','puts "CHECK_BEGIN"','check_setup -verbose','puts "CHECK_END"']
    groups={'reg2reg':('[all_registers -clock_pins]','[all_registers -data_pins]'),
            'in2reg':('$data_inputs','[all_registers -data_pins]'),
            'reg2out':('[all_registers -clock_pins]','[all_outputs]'),
            'in2out':('$data_inputs','[all_outputs]')}
    for group,(start,end) in groups.items():
        lines.extend([f'set paths [find_timing_paths -from {start} -to {end} -path_delay max -group_path_count 1]',
            'foreach p $paths { puts "GROUP '+group+' [get_property $p slack] [get_full_name [get_property $p startpoint]] [get_full_name [get_property $p endpoint]]" }'])
    lines+=['report_worst_slack -max -digits 6','report_worst_slack -min -digits 6']
    if details:
        for group,(start,end) in groups.items():
            lines.append(f'puts "REPORT {group}"; report_checks -from {start} -to {end} -path_delay max -group_path_count 1 -format full -digits 4')
        lines+=['puts "ELECTRICAL_BEGIN"',
                'report_check_types -max_slew -max_capacitance -violators -digits 4',
                'puts "ELECTRICAL_END"']
    script=MAP/f'{name}_{tag}.tcl';save(script,'\n'.join(lines)+'\n')
    result=subprocess.run([sta,'-no_init','-exit',str(script)],cwd=ROOT,capture_output=True,text=True,check=True,timeout=180)
    transcript=result.stdout+result.stderr;save(MAP/f'{name}_{tag}.sta.log',transcript)
    metrics=parse_sta(transcript);metrics.update({'period_ns':period,'tag':tag})
    if details:
        electrical=transcript.split('ELECTRICAL_BEGIN\n',1)[1].split('ELECTRICAL_END',1)[0]
        metrics['electrical_violations_reported']=len(re.findall(r'(?i)VIOLATED',electrical))
    return metrics


def run():
    cfg=json.loads(CONFIG.read_text()); MAP.mkdir(parents=True,exist_ok=True)
    sta=os.environ.get('STA') or shutil.which('sta')
    if not sta or not shutil.which('yosys'):
        print('BLOCKED: yosys and STA/OpenSTA are required',file=sys.stderr);return 2
    source=ROOT/cfg['library_path']
    if not source.exists(): print('BLOCKED: build the pinned timing tools first',file=sys.stderr);return 2
    if digest(source)!=cfg['library_sha256']: raise ValueError('Pinned library checksum mismatch')
    original=gzip.decompress(source.read_bytes()).decode('utf-8')
    libtext,areas,sequential=prepare_library(original)
    lib=MAP/'library_pruned.lib';save(lib,libtext)
    metadata={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'config':cfg,'library_source_sha256':digest(source),'library_pruned_sha256':digest(lib),
        'liberty_cells':len(areas),'yosys_version':subprocess.check_output(['yosys','-V'],text=True).strip(),
        'sta_binary_sha256':digest(sta),'rtl_sha256':{p:digest(ROOT/p) for p in SOURCES},
        'fixture_sha256':{p.relative_to(ROOT).as_posix():digest(p) for p in (ROOT/'model/agreement').glob('*.hex')},
        'residual_rom_sha256':digest(ROOT/'model/agreement/residual_ranges.hex'),
        'scope':'pre-layout, one typical corner, ideal wires and clock; not signoff'}
    for key,path in (('opensta_commit','.tools/OpenSTA'),('cudd_commit','.tools/cudd')):
        actual=subprocess.check_output(['git','-C',str(ROOT/path),'rev-parse','HEAD'],text=True).strip()
        if actual!=cfg[key]: raise ValueError(f'{key}: wrong timing tool checkout')
    metadata['status']='in_progress'
    save(MAP/'metadata.json',json.dumps(metadata,indent=2)+'\n')
    rows=[];probes=[]
    for name,params in DESIGNS.items():
        row=map_design(name,params,lib,areas,sequential,cfg)
        target=sta_design(name,cfg['mapping_target_ns'],'target',sta,lib,cfg)
        row['setup_wns_at_mapping_target_ns']=target['setup_wns_ns'];row['mapping_target_met']=target['setup_met']
        lower=0.25
        fail=sta_design(name,lower,'tight_negative_control',sta,lib,cfg)
        if fail['setup_met']: raise ValueError('Unrealistically tight clock did not fail')
        upper=cfg['mapping_target_ns'];passed=target;iteration=0
        while not passed['setup_met']:
            lower=upper;upper*=2;iteration+=1
            if upper>320: raise ValueError('No passing setup clock found up to 320ns')
            passed=sta_design(name,upper,f'expand{iteration}',sta,lib,cfg);probes.append({'design':name,**passed})
        while upper-lower>cfg['period_resolution_ns']:
            mid=(upper+lower)/2;iteration+=1
            test=sta_design(name,mid,f'search{iteration}',sta,lib,cfg);probes.append({'design':name,**test})
            if test['setup_met']: upper=mid;passed=test
            else: lower=mid
        row.update({'setup_period_fail_ns':lower,'setup_period_pass_ns':upper,
                    'setup_wns_at_pass_ns':passed['setup_wns_ns'],'hold_wns_at_pass_ns':passed['hold_wns_ns']})
        rows.append(row)
        print(f"MAPPED {name}: {row['area_um2']:.2f}um2; setup bracket ({lower:.4f}, {upper:.4f}]ns",flush=True)
    common=math.ceil(max(r['setup_period_pass_ns'] for r in rows)*1.10*2)/2
    metadata['common_period_ns']=common
    for row in rows:
        name=row['design'];check=sta_design(name,common,'common',sta,lib,cfg,details=True)
        if not check['setup_met'] or not check['hold_met']:
            raise ValueError(f'{name}: common-clock setup/hold failed; inspect reports')
        row.update({'common_period_ns':common,'common_setup_wns_ns':check['setup_wns_ns'],
                    'common_hold_wns_ns':check['hold_wns_ns'],
                    'electrical_violations_reported':check['electrical_violations_reported']})
        refs=list(csv.DictReader((ROOT/'build'/REFERENCE_CSV[name]).open()))
        row['rtl_reference_sha256']=digest(ROOT/'build'/REFERENCE_CSV[name])
        if len(refs)!=359: raise ValueError('Missing 359-frame RTL reference replay')
        no_gap=[int(r['command_to_valid_cycles'])-(10 if int(r['sample'])%11==0 else 0) for r in refs]
        row['mean_no_gap_cycles']=sum(no_gap)/359;row['worst_no_gap_cycles']=max(no_gap)
        row['mean_latency_at_common_ns']=row['mean_no_gap_cycles']*common
        row['worst_latency_at_common_ns']=row['worst_no_gap_cycles']*common
        row['mean_latency_at_tested_pass_ns']=row['mean_no_gap_cycles']*row['setup_period_pass_ns']
        row['critical_path']=min(check['groups'].items(),key=lambda item:item[1]['slack_ns'])[0]
        print(f"COMMON {name}: {common:g}ns, setup {check['setup_wns_ns']:.4f}ns, hold {check['hold_wns_ns']:.4f}ns",flush=True)
    metadata['status']='complete'
    save(MAP/'metadata.json',json.dumps(metadata,indent=2)+'\n')
    save(MAP/'manifest.json',json.dumps(rows,indent=2)+'\n')
    save(MAP/'period_search.json',json.dumps(probes,indent=2)+'\n')
    flat=[{k:v for k,v in r.items() if k!='params'} for r in rows]
    with (ROOT/'build/mapped_comparison.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=flat[0].keys(),lineterminator='\n');writer.writeheader();writer.writerows(flat)
    print('PASS directly tested setup brackets and common-clock setup/hold. Pre-layout estimates only.')
    return 0


if __name__=='__main__':
    raise SystemExit(run())

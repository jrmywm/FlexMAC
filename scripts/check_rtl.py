"""Exhaustive arithmetic, oracle-checked frames, and an RTL negative control."""
from pathlib import Path
import csv
import hashlib
import json
import random
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from model.arithmetic import product_sum, dot
BUILD = ROOT/'build'
SOURCES = ['rtl/flexmac_product.v','rtl/flexmac_baselines.v','rtl/flexmac_stream.v']


def run(args, log):
    result = subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=180)
    (BUILD/log).write_text(result.stdout+result.stderr,encoding='utf-8',newline='\n')
    if result.returncode:
        print(result.stdout+result.stderr,file=sys.stderr)
    result.check_returncode()
    print(result.stdout,end='')
    return result


def main():
    BUILD.mkdir(exist_ok=True)
    with (BUILD/'products.txt').open('w',encoding='ascii',newline='\n') as f:
        for mode in (False,True):
            for a in range(256):
                for b in range(256):
                    f.write(f'{int(mode)} {a:02x} {b:02x} {product_sum(a,b,mode)}\n')
    rng = random.Random(20261027)
    frames = []
    for mode in (False,True):
        for beats in ([(0,0)],[(128,128)],[(255,255)],[(0x88,0x88)],[(0x2f,0x3e)]):
            frames.append((mode,beats,3))
    for i in range(160):
        length = rng.choice([1,2,3,7,16,31,64,127])
        frames.append((bool(i%2),[(rng.randrange(256),rng.randrange(256)) for _ in range(length)],rng.randrange(5)))
    # Exercise real 32-bit RTL overflow in both directions, not just model wrap.
    frames += [(False,[(128,128)]*131073,0),(False,[(128,127)]*132105,0)]
    expected = [dot(beats,mode) & 0xffffffff for mode,beats,_ in frames]
    with (BUILD/'frames.txt').open('w',encoding='ascii',newline='\n') as f:
        for (mode,beats,stalls),value in zip(frames,expected):
            f.write(f'{int(mode)} {len(beats)} {stalls} {value:08x}\n')
            for a,b in beats:
                f.write(f'{a:02x} {b:02x}\n')
    print(f'Generated 131072 product vectors and {len(frames)} frames per implementation.',flush=True)
    if '--generate-only' in sys.argv:
        print('Generation only; RTL was NOT simulated.')
        return 0
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        print('BLOCKED: iverilog and vvp are required.',file=sys.stderr)
        return 2
    run(['iverilog','-g2012','-Wall','-s','tb_product','-o',str(BUILD/'product.vvp'),
         *SOURCES,'tests/tb_product.v'],'compile_product.log')
    run(['vvp',str(BUILD/'product.vvp'),f'+vectors={BUILD/"products.txt"}'],'product.log')
    streams = []
    for impl in (0,1):
        binary = BUILD/f'stream_{impl}.vvp'
        run(['iverilog','-g2012','-Wall','-s','tb_stream',f'-Ptb_stream.PRODUCT_IMPL={impl}',
             '-o',str(binary),*SOURCES,'tests/tb_stream.v'],f'compile_stream_{impl}.log')
        run(['vvp',str(binary),f'+frames={BUILD/"frames.txt"}',
             f'+results={BUILD/f"stream_{impl}.csv"}'],f'stream_{impl}.log')
        with (BUILD/f'stream_{impl}.csv').open(newline='') as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == len(frames)
        for i,(row,(mode,beats,stalls),value) in enumerate(zip(rows,frames,expected)):
            assert int(row['frame']) == i and int(row['mode4']) == int(mode)
            assert int(row['beats']) == len(beats) and int(row['result_hex'],16) == value
            gaps = (len(beats)+6)//7 if len(beats) < 1000 else 0
            # Command-to-first-beat setup includes one full cycle in this bench.
            assert int(row['command_to_production_cycles']) == len(beats)+gaps
            assert int(row['held_cycles']) == stalls+1
        streams.append(rows)
    assert streams[0] == streams[1], 'Implementations differ in decisions or cycle behavior'
    source = (ROOT/SOURCES[0]).read_text(encoding='utf-8')
    assert source.count('mode4 && a[3]') == 1
    mutant = BUILD/'mutant_product.v'
    mutant.write_text(source.replace('mode4 && a[3]',"1'b0"),encoding='utf-8',newline='\n')
    run(['iverilog','-g2012','-s','tb_product','-o',str(BUILD/'mutant.vvp'),
         str(mutant),*SOURCES[1:],'tests/tb_product.v'],'compile_mutant.log')
    rejected = subprocess.run(['vvp',str(BUILD/'mutant.vvp'),f'+vectors={BUILD/"products.txt"}'],
                              cwd=ROOT,capture_output=True,text=True,timeout=180)
    (BUILD/'negative_control.log').write_text(rejected.stdout+rejected.stderr,encoding='utf-8',newline='\n')
    assert rejected.returncode != 0 and 'shared product mismatch' in rejected.stdout, 'INT4 sign bug was not rejected'
    summary = {'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
               'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES+['tests/tb_product.v','tests/tb_stream.v','model/arithmetic.py']},
               'product_vectors':131072,'frames_per_implementation':len(frames),
               'reset_cancellations_per_implementation':2,'negative_control_rejected':True,
               'scope':'Exhaustive combinational products; sampled stream simulation including wrap, not formal proof.'}
    (BUILD/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS both stream implementations, both overflow directions, and negative control.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

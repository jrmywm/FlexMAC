"""Optional scientific figure from a completed, gate-replayed mapping snapshot."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'docs/data/mapping/mapped_comparison.csv')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/figures/mapped_comparison')
    args=parser.parse_args()
    if not args.input.exists(): parser.error('A completed mapping snapshot is required')
    metadata=json.loads((args.input.parent/'metadata.json').read_text(encoding='utf-8'))
    replay=json.loads((args.input.parent/'gate_replay.json').read_text(encoding='utf-8'))
    if metadata.get('status')!='complete' or len(replay['designs'])!=4 or not all(d['passed'] for d in replay['designs']):
        parser.error('Mapping and all four gate-level replays must pass before plotting')
    names=['int8_single','int8_two_lane','adaptive_shared','adaptive_mux']
    records={r['design']:r for r in csv.DictReader(args.input.open())}
    rows=[records[n] for n in names]
    clocks={float(r['common_period_ns']) for r in rows}
    if len(clocks)!=1: parser.error('The common-clock comparison must use one period')
    period=clocks.pop()
    colors=['#76808f','#2166ac','#d49b34','#a96d27']
    labels=['INT8\none lane','INT8\ntwo lanes','Adaptive\nshared','Adaptive\nmux']
    area=[float(r['area_um2'])/1000 for r in rows]
    mean=[float(r['mean_latency_at_common_ns'])/1000 for r in rows]
    worst=[float(r['worst_latency_at_common_ns'])/1000 for r in rows]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
                         'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axes=plt.subplots(1,2,figsize=(12,5.4))
    for ax in axes:
        ax.set_axisbelow(True);ax.grid(axis='y',alpha=.16);ax.set_xticks(range(4),labels)
    axes[0].bar(range(4),area,color=colors,width=.64)
    axes[0].set_ylabel('Mapped cell area (10³ µm²)');axes[0].set_title('Characterized cell-area sum',loc='left',fontweight='bold')
    axes[0].set_ylim(0,max(area)*1.20)
    for i,value in enumerate(area): axes[0].text(i,value+max(area)*.025,f'{value:.1f}',ha='center')
    axes[1].bar(range(4),mean,color=colors,width=.64,label='Calibration mean')
    axes[1].scatter(range(4),worst,marker='D',facecolors='white',edgecolors='#30343b',s=45,zorder=4,label='Worst case')
    axes[1].set_ylabel('Command-to-valid latency (µs)');axes[1].set_title(f'Common clock: {period:g} ns',loc='left',fontweight='bold')
    axes[1].set_ylim(0,max(worst)*1.25)
    for i,value in enumerate(mean): axes[1].text(i,value+max(worst)*.025,f'{value:.2f}',ha='center')
    axes[1].legend(frameon=False,loc='upper left')
    violations=sum(int(r['electrical_violations_reported']) for r in rows)
    note=f'SKY130 HD TT, 1.80 V / 25°C · ideal wires and clock · pre-layout estimate, not signoff\n359 calibration images; input gaps and result stalls excluded. Electrical violators reported: {violations}.'
    fig.suptitle('FlexMAC: mapped area and scheduled inference latency',x=.07,ha='left',fontweight='bold',fontsize=15)
    fig.text(.07,.02,note,fontsize=9,color='#505864',va='bottom')
    fig.tight_layout(rect=[.02,.12,.99,.91])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for suffix in ('.png','.svg'): fig.savefig(args.output.with_suffix(suffix),dpi=160,facecolor='white')
    provenance={'mapping_source_commit':metadata['source_commit'],
        'csv_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(),'matplotlib':matplotlib.__version__}
    args.output.with_suffix('.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'Wrote {args.output}.png and .svg from verified mapping data')


if __name__=='__main__': main()

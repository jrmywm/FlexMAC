"""Plot the completed baseline versus score-comparison pipeline experiment."""
from pathlib import Path
import csv,hashlib,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/'docs/data/scorepipe'
    metadata=json.loads((source/'metadata.json').read_text())
    replay=json.loads((source/'gate_replay.json').read_text())
    names=['int8_two_lane','int8_two_lane_scorepipe']
    assert metadata['status']=='complete' and replay['source_commit']==metadata['source_commit']
    assert {r['design'] for r in replay['designs']}==set(names)
    assert all(r['passed'] and r['frames']==359 and r['four_state_frames']==359 for r in replay['designs'])
    csv_path=source/'mapped_comparison.csv'
    records={r['design']:r for r in csv.DictReader(csv_path.open())}
    rows=[records[n] for n in names]
    common={float(r['common_period_ns']) for r in rows}
    assert len(common)==1
    period=common.pop()
    panels=[('Mapped cell area','Area (10³ µm²)','area_um2',1000),
            ('Directly tested passing setup period','Period (ns)','setup_period_pass_ns',1),
            ('Each design at its own passing period','Inference latency (µs)','mean_latency_at_tested_pass_ns',1000),
            (f'Both designs at {period:g} ns','Inference latency (µs)','mean_latency_at_common_ns',1000)]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,
        'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    fig,axes=plt.subplots(2,2,figsize=(10,8))
    for ax,(title,unit,key,scale) in zip(axes.ravel(),panels):
        values=[float(r[key])/scale for r in rows]
        ax.set_axisbelow(True);ax.grid(axis='y',alpha=.16)
        ax.bar(range(2),values,color=['#76808f','#2166ac'],width=.55)
        ax.set_xticks(range(2),['Two-lane INT8','Score pipeline'])
        ax.set_ylabel(unit);ax.set_title(title,loc='left',fontsize=11,fontweight='bold')
        ax.set_ylim(0,max(values)*1.22)
        for i,value in enumerate(values):ax.text(i,value+max(values)*.03,f'{value:.3f}',ha='center')
    fig.suptitle('FlexMAC: separating score calculation from class comparison',fontsize=14,fontweight='bold')
    fig.text(.07,.025,'SKY130 HD TT, 1.80 V / 25°C · ideal wires and clock · pre-layout, not signoff\n359 calibration images; input gaps and result stalls excluded. Power is unmeasured.',fontsize=9,color='#505864')
    fig.tight_layout(rect=[.02,.10,.99,.95],h_pad=2.5)
    output=ROOT/'docs/figures/scorepipe_comparison';output.parent.mkdir(parents=True,exist_ok=True)
    for suffix in ('.png','.svg'):fig.savefig(output.with_suffix(suffix),dpi=160,facecolor='white')
    svg=output.with_suffix('.svg')
    svg.write_text('\n'.join(x.rstrip() for x in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')
    output.with_suffix('.json').write_text(json.dumps({'mapping_source_commit':metadata['source_commit'],
        'csv_sha256':hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        'matplotlib':matplotlib.__version__},indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Wrote verified score-pipeline comparison figure')


if __name__=='__main__':main()

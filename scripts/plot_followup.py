"""Plot only archived measured follow-up results; no EDA execution."""
from pathlib import Path
import csv, hashlib, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/figures'
FILES=['docs/data/overlap/mapped_comparison.csv','docs/data/synthetic/results.csv',
       'docs/data/area_attribution/attribution.json']

def read_csv(path):
    with (ROOT/path).open() as f:return list(csv.DictReader(f))

def main():
    plt.rcParams.update({'font.size':9,'svg.fonttype':'none','svg.hashsalt':'flexmac-followup-v1'})
    colors=['#65758b','#2166ac','#bd7b18']
    fig,axes=plt.subplots(1,3,figsize=(12,3.7))
    rows=read_csv(FILES[0]);ax=axes[0]
    vals=[float(r['mean_latency_at_tested_pass_ns'])/1000 for r in rows]
    ax.bar(['Original','Separate','Overlap'],vals,color=colors)
    for i,v in enumerate(vals):ax.text(i,v+.04,f'{v:.3f}',ha='center')
    ax.set_ylim(0,6);ax.set_ylabel('Latency at own tested period (us)')
    ax.set_title('Frozen classifier: overlap does not win')
    diagnostic=json.loads((ROOT/FILES[2]).read_text());ax=axes[1]
    buckets=sorted(diagnostic['rows'],key=lambda r:r['area_um2'])
    ax.barh([r['bucket'].replace('_',' ') for r in buckets],
            [r['area_um2']/1000 for r in buckets],color='#2166ac')
    ax.set_xlabel('Diagnostic mapped cell area (1000 um2)')
    ax.set_title('Preserved hierarchy only')
    ax.text(.98,.05,'Not flattened-area attribution',transform=ax.transAxes,ha='right',fontsize=8)
    synthetic=read_csv(FILES[1]);ax=axes[2]
    for schedule,label in enumerate(['Original','Separate','Overlap']):
        vals=[]
        for f,c in ((32,4),(64,10),(128,10)):
            group=[r for r in synthetic if int(r['features'])==f and int(r['classes'])==c]
            base=next(float(r['latency_at_pass_ns']) for r in group if int(r['schedule'])==0)
            vals.append(next(float(r['latency_at_pass_ns']) for r in group if int(r['schedule'])==schedule)/base)
        ax.plot(range(3),vals,'o-',label=label,color=colors[schedule])
    ax.set_xticks(range(3),['32 x 4','64 x 10','128 x 10'])
    ax.set_xlabel('Synthetic features x classes')
    ax.set_ylabel('Own-period latency / original')
    ax.set_ylim(.8,1.04);ax.legend(frameon=False,fontsize=8)
    ax.set_title('Scheduling gain depends on shape')
    fig.suptitle('FlexMAC follow-up: executed measurements, including negative results',fontsize=12)
    fig.tight_layout(rect=(0,0,1,.94))
    OUT.mkdir(parents=True,exist_ok=True)
    for ext in ('png','svg'):fig.savefig(OUT/f'followup_comparison.{ext}',dpi=180)
    svg=OUT/'followup_comparison.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n',encoding='utf-8',newline='\n')
    plt.close(fig)
    (OUT/'followup_comparison.json').write_text(json.dumps({
        'scope':'pre-layout SKY130 typical corner, ideal wires/clock; synthetic RTL verification only',
        'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}},indent=2)+'\n')

if __name__=='__main__':main()

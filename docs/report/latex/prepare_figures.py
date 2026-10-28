"""Regenerate vector PDF figures from the archived FlexMAC measurements."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent/'images'
BLUE='#2166ac';INK='#183047';GRAY='#5e6b78';AMBER='#bd7b18'
plt.rcParams['pdf.fonttype']=42
HERE.mkdir(parents=True,exist_ok=True)

def records(path):
    with path.open() as f:return {r['design']:r for r in csv.DictReader(f)}


def make_figures():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8.5,
        'svg.fonttype':'none','svg.hashsalt':'flexmac-technical-report-v1'})
    fig,ax=plt.subplots(figsize=(7,2.55));ax.set_xlim(0,100);ax.set_ylim(0,100);ax.axis('off')
    def box(x,y,label,new=False):
        ax.add_patch(FancyBboxPatch((x,y),21,22,boxstyle='round,pad=.3,rounding_size=1.5',
            facecolor='#fff3da' if new else '#edf4fb',edgecolor=AMBER if new else BLUE,lw=1.2))
        ax.text(x+10.5,y+11,label,ha='center',va='center',fontsize=8.5,color=INK)
    def arr(x,y):ax.add_patch(FancyArrowPatch((x,y),(x+4,y),arrowstyle='-|>',mutation_scale=10,color=GRAY))
    ax.text(1,96,'Baseline: terminal accumulation and winner comparison in one cycle',weight='bold',color=INK)
    for x,label in [(1,'Two INT8 products\n+ signed 17-bit sum'),(26,'32-bit accumulate\ncompleted_score'),(51,'Signed comparison\n+ winner selection'),(76,'Best score / class\nregisters')]:box(x,64,label)
    for x in (22,47,72):arr(x,75)
    ax.text(1,47,'Score pipeline: capture terminal score, then compare in the next cycle',weight='bold',color=INK)
    for x,label,new in [(1,'Two INT8 products\n+ signed 17-bit sum',False),(26,'32-bit accumulate\ncompleted_score',False),(51,'NEW pending score\n+ class / last registers',True),(76,'COMPARE: update\nwinner next cycle',False)]:box(x,13,label,new)
    for x in (22,47,72):arr(x,24)
    ax.text(1,1,'Conceptual grouping. Accumulator feedback remains unpipelined; one score is staged per class.',fontsize=7.6,color=GRAY)
    fig.subplots_adjust(left=.01,right=.99,top=.98,bottom=.04)
    export(fig,'report_datapath')
    raw=records(ROOT/'docs/data/mapping/mapped_comparison.csv')
    pair=records(ROOT/'docs/data/scorepipe/mapped_comparison.csv')
    rows=[raw[n] for n in ('int8_single','int8_two_lane','adaptive_shared','adaptive_mux')]+[pair['int8_two_lane_scorepipe']]
    labels=['INT8\n1 lane','INT8\n2 lanes','Adaptive\nshared','Adaptive\nmux','Score\npipeline']
    fig,axes=plt.subplots(1,2,figsize=(7,2.38))
    for ax,key,scale,title,ylabel in [(axes[0],'area_um2',1000,'Whole-engine mapped area','Cell area (10³ µm²)'),
        (axes[1],'mean_latency_at_tested_pass_ns',1000,'Mean latency at own tested clock','Latency (µs)')]:
        vals=[float(r[key])/scale for r in rows]
        ax.bar(range(5),vals,color=['#7b8795',BLUE,'#d49b34','#a96d27','#277f8e'],width=.7)
        ax.set_xticks(range(5),labels);ax.tick_params(labelsize=7.2)
        ax.set_ylabel(ylabel,fontsize=8);ax.set_title(title,fontsize=9,loc='left',weight='bold')
        ax.spines[['top','right']].set_visible(False);ax.set_axisbelow(True);ax.grid(axis='y',alpha=.14)
        ax.set_ylim(0,max(vals)*1.25)
        for i,v in enumerate(vals):ax.text(i,v+max(vals)*.035,f'{v:.1f}' if key=='area_um2' else f'{v:.2f}',ha='center',fontsize=7)
    fig.tight_layout(pad=.8,w_pad=1.5);export(fig,'report_results')


def export(fig,name):
    for suffix in ('.pdf',):
        path=HERE/(name+suffix)
        fig.savefig(path,dpi=200,facecolor='white',metadata={'CreationDate':None,'ModDate':None})
        if suffix=='.svg':path.write_text('\n'.join(s.rstrip() for s in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')
    plt.close(fig)



if __name__=='__main__':
    make_figures()
    print('Prepared vector PDF figures')

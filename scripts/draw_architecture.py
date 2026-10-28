"""Render conceptual RTL diagrams; these are not netlist schematics or waveforms."""
from pathlib import Path
import hashlib,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch,Rectangle

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/figures'
BLUE='#2166ac';PALE='#edf4fb';AMBER='#bd7b18';GOLD='#fff3da';INK='#263445';GRAY='#64748b'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none',
                     'svg.hashsalt':'flexmac-architecture-v1'})


def canvas(title,height=8):
    fig,ax=plt.subplots(figsize=(13,height));ax.set_xlim(0,1200);ax.set_ylim(0,700)
    ax.axis('off');fig.suptitle(title,fontsize=17,fontweight='bold',x=.06,ha='left',y=.98)
    fig.subplots_adjust(left=.025,right=.98,top=.92,bottom=.08)
    return fig,ax


def text(ax,x,y,label,size=10,color=INK,ha='center',weight='normal'):
    ax.text(x,y,label,ha=ha,va='center',fontsize=size,color=color,fontweight=weight)


def box(ax,x,y,w,h,label,fill=PALE,color=BLUE,register=False,size=10):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02,rounding_size=7',
        facecolor=fill,edgecolor=color,linewidth=1.6))
    if register:ax.plot([x+7,x+7],[y+8,y+h-8],color=color,lw=1)
    text(ax,x+w/2,y+h/2,label,size)


def arrow(ax,points,label=None,label_at=None,color=GRAY,size=9):
    for a,b in zip(points[:-2],points[1:-1]):ax.plot([a[0],b[0]],[a[1],b[1]],color=color,lw=1.5)
    ax.add_patch(FancyArrowPatch(points[-2],points[-1],arrowstyle='-|>',mutation_scale=13,
                                linewidth=1.5,color=color))
    if label:text(ax,*label_at,label,size,color)


def save(fig,name,note):
    fig.text(.06,.025,note,fontsize=9,color=GRAY)
    OUT.mkdir(parents=True,exist_ok=True)
    for suffix in ('.png','.svg'):
        path=OUT/(name+suffix)
        fig.savefig(path,dpi=160,facecolor='white',metadata={'Date':None} if suffix=='.svg' else None)
        if suffix=='.svg':path.write_text('\n'.join(s.rstrip() for s in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')
    plt.close(fig)


def datapath():
    fig,ax=canvas('FlexMAC: where the score-comparison register changes the datapath',9)
    for base,new in [(375,False),(35,True)]:
        text(ax,25,base+265,'AFTER: terminal score is registered before comparison' if new else
             'BEFORE: terminal addition and winner comparison share one cycle',12,ha='left',weight='bold')
        y=base+125
        box(ax,25,y,190,85,'Pixel buffer + quantizers\nFrozen weight ROMs\nTwo features per beat')
        box(ax,255,y,180,85,'Two signed 8 × 8 products\n16-bit products\n17-bit pair sum',size=9)
        box(ax,485,y,145,85,'32-bit wrap add\ncompleted_score')
        arrow(ax,[(215,y+42),(255,y+42)])
        arrow(ax,[(435,y+42),(485,y+42)],'sign extend\n17 → 32',(460,y+101),size=8)
        box(ax,475,base+12,165,65,'32-bit accumulator\nBias at class start',register=True)
        arrow(ax,[(557,y),(557,base+77)])
        arrow(ax,[(475,base+44),(453,base+44),(453,y+16),(485,y+16)])
        text(ax,557,base-13,'Nonterminal beats update the accumulator.\nIts feedback loop is not pipelined.',8)
        if new:
            box(ax,675,y,185,85,'NEW pending registers\nscore: signed 32 bits\nclass: 4 bits · last: 1 bit',GOLD,AMBER,True,9)
            box(ax,905,y,130,85,'Signed compare\nFirst class or\nscore > best',size=9)
            box(ax,1070,y,110,85,'Best-score /\nbest-class\nregisters',register=True,size=9)
            arrow(ax,[(630,y+42),(675,y+42)],'last beat',(651,y+100),size=8)
            arrow(ax,[(860,y+42),(905,y+42)],color=AMBER)
            arrow(ax,[(1035,y+42),(1070,y+42)])
            arrow(ax,[(1125,y+85),(1125,y+110),(970,y+110),(970,y+85)])
            ax.plot([882,882],[y-8,y+105],ls='--',color=AMBER,lw=1.4)
            text(ax,770,y+125,'EVAL8 captures terminal score',9)
            text(ax,1030,y+125,'COMPARE: following cycle',9,color=AMBER)
            text(ax,905,base+38,'Previous best score feeds comparison;\nstrict > keeps the lower class on ties.',8,ha='left')
        else:
            box(ax,740,y,180,85,'Signed class comparison\ncompleted_score > best\n(or first class)',size=9)
            box(ax,1000,y,175,85,'Best-score: signed 32 bits\nBest-class: 4 bits\nregisters',register=True,size=9)
            arrow(ax,[(630,y+42),(740,y+42)],'last beat',(685,y+100),size=8)
            arrow(ax,[(920,y+42),(1000,y+42)])
            arrow(ax,[(1087,y+85),(1087,y+110),(830,y+110),(830,y+85)])
            text(ax,945,base+38,'Prior best score feeds comparison.\nWinner update uses the same terminal score.',8)
    save(fig,'scorepipe_datapath','Conceptual RTL datapath: logical groupings and selected data/control connections. Not a synthesized gate schematic.\nThe terminal score is staged once per class; this is not a continuously filled multiplier pipeline.')


def controller():
    fig,ax=canvas('FlexMAC: controller for registered score comparison',8.7)
    box(ax,25,590,1145,70,'Reset: state goes to IDLE on a rising edge with rst=1. Interface signals are masked while rst=1.\nIllegal state also returns to IDLE on the next rising edge.',fill='#f3f5f8',color=GRAY,size=11)
    box(ax,35,340,170,90,'IDLE\nstart_ready = 1',size=11)
    box(ax,320,340,175,90,'LOAD\npixel_ready = 1\n64 accepted pixels',size=10)
    box(ax,620,340,190,90,'EVAL8\n32 paired MAC beats\nper class',size=11)
    box(ax,950,340,210,90,'COMPARE\nUpdate best score / class\nfrom pending registers',GOLD,AMBER,size=10)
    box(ax,950,100,210,95,'RESULT\nresult_valid = 1\nClass or input error',size=11)
    arrow(ax,[(205,385),(320,385)],'start_valid',(263,410))
    arrow(ax,[(495,385),(620,385)],'64th pixel;\nno input error',(558,470))
    arrow(ax,[(810,385),(950,385)],'index = 31\nCapture score + tag',(879,470))
    arrow(ax,[(1055,340),(1055,195)],'pending_last',(1115,268))
    arrow(ax,[(950,360),(900,360),(900,270),(715,270),(715,340)],
          'More classes: advance class, reset index, preload next bias',(775,243),color=AMBER)
    arrow(ax,[(407,340),(407,147),(950,147)],'Invalid pixel seen: finish input collection, then return error',(630,175))
    arrow(ax,[(950,120),(120,120),(120,340)],'result_ready: consume result',(485,90))
    arrow(ax,[(65,430),(65,505),(175,505),(175,430)],'Wait for command',(120,533))
    arrow(ax,[(345,430),(345,505),(470,505),(470,430)],'Wait / collect pixels',(407,533))
    arrow(ax,[(640,430),(640,505),(790,505),(790,430)],'index < 31: accumulate',(715,533))
    arrow(ax,[(1160,125),(1180,125),(1180,230),(1130,230),(1130,195)],
          'Hold while\n!result_ready',(1115,59),size=8)
    text(ax,40,18,'Every state box names the control phase; computation and transitions occur on clock edges.\nOne frame is processed at a time. result_fallback is always 0 for this INT8-only engine.',9,ha='left')
    save(fig,'scorepipe_controller','Conceptual state diagram traced to flexmac_int8x2_scorepipe.v. A pixel is accepted only when pixel_valid && pixel_ready.\nAn invalid raw pixel is greater than 16; collection continues until all 64 pixels have been accepted.')


def timeline():
    fig=plt.figure(figsize=(13,8.8));grid=fig.add_gridspec(2,1,height_ratios=[1.15,1],hspace=.65)
    ax=fig.add_subplot(grid[0]);zoom=fig.add_subplot(grid[1]);fig.subplots_adjust(left=.12,right=.97,top=.88,bottom=.19)
    fig.suptitle('FlexMAC: why score registration adds ten cycles per image',x=.06,ha='left',fontsize=17,fontweight='bold')
    for y,pipeline in [(1,False),(0,True)]:
        ax.barh(y,64,left=0,height=.5,color='#c9d4df',edgecolor='white')
        ax.text(32,y,'64 pixel\nloads',ha='center',va='center',fontsize=9)
        for c in range(10):
            start=64+c*(33 if pipeline else 32)
            ax.barh(y,32,left=start,height=.5,color=BLUE if c%2==0 else '#5991c4',edgecolor='white')
            ax.text(start+16,y,f'C{c}',ha='center',va='center',color='white',fontsize=9)
            if pipeline:ax.barh(y,1,left=start+32,height=.5,color=AMBER)
        end=394 if pipeline else 384
        ax.text(end+3,y,str(end),ha='left',va='center',fontweight='bold')
    ax.set_xlim(0,415);ax.set_xticks([0,64,96,130,196,262,328,384,394])
    ax.tick_params(axis='x',labelsize=8);ax.set_yticks([1,0],['Baseline','Score pipeline'])
    ax.set_xlabel('Cycles after command acceptance (0); bar boundaries mark completed cycles')
    ax.set_ylim(-.7,1.7);ax.spines[['top','right','left']].set_visible(False)
    ax.set_title('Full frame: 384 = 64 + 10 × 32; 394 = 64 + 10 × (32 + 1)',loc='left',fontsize=12,fontweight='bold')
    ax.plot([],[],color=AMBER,lw=5,label='One COMPARE cycle per class');ax.legend(frameon=False,loc='upper left',bbox_to_anchor=(0,-.38),fontsize=9)
    base=['C0\nMAC 29','C0\nMAC 30','C0 MAC 31\n+ compare','C1\nMAC 0','C1\nMAC 1','C1\nMAC 2','C1\nMAC 3']
    pipe=['C0\nMAC 29','C0\nMAC 30','C0 MAC 31\nCapture score','COMPARE\nC0','C1\nMAC 0','C1\nMAC 1','C1\nMAC 2']
    for y,labels in [(1,base),(0,pipe)]:
        for i,label in enumerate(labels):
            color=GOLD if y==0 and i==3 else PALE
            zoom.add_patch(Rectangle((i,y-.28),1,.56,facecolor=color,edgecolor='white',linewidth=2))
            zoom.text(i+.5,y,label,ha='center',va='center',fontsize=9,color=INK)
    zoom.set_xlim(0,7);zoom.set_ylim(-.6,1.6);zoom.set_xticks([i+.5 for i in range(7)],[str(i) for i in range(94,101)])
    zoom.set_yticks([1,0],['Baseline','Score pipeline']);zoom.set_xlabel('Cycle number (zoom around the first class boundary)')
    zoom.set_title('The comparison moves from the final MAC cycle into its own cycle',loc='left',fontsize=12,fontweight='bold')
    zoom.spines[['top','right','left']].set_visible(False)
    save(fig,'scorepipe_timeline','Illustrative unstalled schedule, not a captured waveform. Command is accepted at cycle 0; pixels occupy cycles 1–64.\nClass 0: MAC 65–96, compare 97. Class 9: MAC 362–393, compare 394. Input gaps and result stalls are excluded.\nCycles are not elapsed time: tested periods are 13.59375 ns (baseline) and 11.2890625 ns (score pipeline).')


def main():
    datapath();controller();timeline()
    files=['rtl/flexmac_adaptive.v','rtl/flexmac_int8x2_scorepipe.v','tests/tb_scorepipe.v',
           'scripts/draw_architecture.py']
    outputs=[OUT/(stem+suffix) for stem in ('scorepipe_datapath','scorepipe_controller','scorepipe_timeline') for suffix in ('.png','.svg')]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    provenance={'scope':'Manually authored conceptual RTL diagrams and illustrative cycle schedule; not extracted schematics or captured waveforms',
        'matplotlib':matplotlib.__version__,'source_sha256':{p:sha(ROOT/p) for p in files},
        'figure_sha256':{p.name:sha(p) for p in outputs}}
    (OUT/'architecture_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('Rendered three architecture diagrams as PNG and SVG')


if __name__=='__main__':main()

"""Build the six-page technical report from Markdown and archived measurements."""
from pathlib import Path
import csv,hashlib,html,json,re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT,TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle,getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle,Image,Preformatted,KeepTogether
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'output/pdf/flexmac_technical_report.pdf'
MANUSCRIPT=HERE/'flexmac_technical_report.md'
W=A4[0]-88
BLUE='#2166ac';INK='#183047';GRAY='#5e6b78';AMBER='#bd7b18'


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
    for suffix in ('.png','.svg'):
        path=HERE/(name+suffix)
        fig.savefig(path,dpi=200,facecolor='white',metadata={'Date':None} if suffix=='.svg' else None)
        if suffix=='.svg':path.write_text('\n'.join(s.rstrip() for s in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8',newline='\n')
    plt.close(fig)


def inline(s):
    s=html.escape(s)
    s=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m:f'<link href="{html.escape(html.unescape(m[2]),quote=True)}" color="{BLUE}">{m[1]}</link>',s)
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
    return re.sub(r'`([^`]+)`',r'<font name="Courier" size="9">\1</font>',s)


def setup_styles():
    fontdir=Path(matplotlib.get_data_path())/'fonts/ttf'
    for name,file in [('Body','DejaVuSerif.ttf'),('BodyBold','DejaVuSerif-Bold.ttf'),
        ('BodyItalic','DejaVuSerif-Italic.ttf'),('Head','DejaVuSans.ttf'),('HeadBold','DejaVuSans-Bold.ttf')]:
        pdfmetrics.registerFont(TTFont(name,str(fontdir/file)))
    pdfmetrics.registerFontFamily('Body',normal='Body',bold='BodyBold',italic='BodyItalic',boldItalic='BodyBold')
    pdfmetrics.registerFontFamily('Head',normal='Head',bold='HeadBold',italic='Head',boldItalic='HeadBold')
    base={'fontName':'Body','fontSize':10.5,'leading':14.4,'textColor':colors.HexColor(INK),'spaceAfter':7}
    return {
        'body':ParagraphStyle('body',**base,alignment=TA_JUSTIFY),
        'title':ParagraphStyle('title',fontName='HeadBold',fontSize=19,leading=23,textColor=colors.HexColor(INK),spaceAfter=10),
        'h2':ParagraphStyle('h2',fontName='HeadBold',fontSize=12.4,leading=16,textColor=colors.HexColor(INK),spaceBefore=10,spaceAfter=7,keepWithNext=True),
        'h3':ParagraphStyle('h3',fontName='HeadBold',fontSize=10.5,leading=14,textColor=colors.HexColor(INK),spaceBefore=7,spaceAfter=5,keepWithNext=True),
        'caption':ParagraphStyle('caption',fontName='Head',fontSize=8.2,leading=10.6,textColor=colors.HexColor(GRAY),spaceAfter=8),
        'author':ParagraphStyle('author',fontName='Head',fontSize=9,leading=13,textColor=colors.HexColor(GRAY),spaceAfter=10),
        'table':ParagraphStyle('table',fontName='Head',fontSize=8.1,leading=10.5,textColor=colors.HexColor(INK)),
        'th':ParagraphStyle('th',fontName='HeadBold',fontSize=8.1,leading=10.5,textColor=colors.white),
        'reference':ParagraphStyle('reference',fontName='Body',fontSize=8.4,leading=11,textColor=colors.HexColor(INK),spaceAfter=5),
        'code':ParagraphStyle('code',fontName='Courier',fontSize=8.2,leading=11,textColor=colors.HexColor(INK),spaceAfter=8,leftIndent=5)}


def table(lines,styles):
    rows=[[cell.strip() for cell in row.strip().strip('|').split('|')] for row in lines]
    rows=[r for r in rows if not all(re.fullmatch(r':?-+:?',x.replace(' ','')) for x in r)]
    n=len(rows[0]);assert all(len(r)==n for r in rows)
    first=.29 if n>=5 else (.40 if n==3 else .33)
    widths=[W*first]+[W*(1-first)/(n-1)]*(n-1)
    cells=[[Paragraph(inline(c),styles['th' if i==0 else 'table']) for c in row] for i,row in enumerate(rows)]
    t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(INK)),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f1f5f9'),colors.white]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
        ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
        ('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#cbd5e1'))]))
    return [t,Spacer(1,8)]


def parse(source,styles):
    lines=source.splitlines();story=[];i=0
    while i<len(lines):
        s=lines[i].strip()
        if not s:i+=1;continue
        if s=='<!-- pagebreak -->':story.append(PageBreak());i+=1;continue
        if s.startswith('```'):
            block=[];i+=1
            while i<len(lines) and not lines[i].startswith('```'):block.append(lines[i]);i+=1
            story.append(Preformatted('\n'.join(block),styles['code']));i+=1;continue
        if s.startswith('|'):
            block=[]
            while i<len(lines) and lines[i].strip().startswith('|'):block.append(lines[i]);i+=1
            story.extend(table(block,styles));continue
        match=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',s)
        if match:
            img=Image(str(HERE/match[2]));scale=min(W/img.imageWidth,1)
            img.drawWidth=img.imageWidth*scale;img.drawHeight=img.imageHeight*scale
            story.append(KeepTogether([img,Paragraph(inline(match[1]),styles['caption'])]));i+=1;continue
        if s.startswith('# '):story.append(Paragraph(inline(s[2:]),styles['title']));i+=1;continue
        if s.startswith('## '):story.append(Paragraph(inline(s[3:]),styles['h2']));i+=1;continue
        if s.startswith('### '):story.append(Paragraph(inline(s[4:]),styles['h3']));i+=1;continue
        if s.startswith('- '):story.append(Paragraph('• '+inline(s[2:]),styles['body']));i+=1;continue
        block=[s];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#|\||!\[|```|<!--|- )',lines[i].strip()):block.append(lines[i].strip());i+=1
        joined=' '.join(block)
        style='reference' if re.match(r'^\[\d+\]',joined) else 'author' if 'Independent technical report' in joined else 'body'
        story.append(Paragraph(inline(joined),styles[style]))
    return story


def footer(canvas,doc):
    canvas.saveState();canvas.setStrokeColor(colors.HexColor('#cbd5e1'));canvas.line(44,36,A4[0]-44,36)
    canvas.setFont('Head',7.5);canvas.setFillColor(colors.HexColor(GRAY))
    canvas.drawString(44,23,'FlexMAC | Independent technical report | 28 October 2026')
    canvas.drawRightString(A4[0]-44,23,f'{doc.page} / 6');canvas.restoreState()


def main():
    make_figures();styles=setup_styles();source=MANUSCRIPT.read_text(encoding='utf-8')
    assert source.count('<!-- pagebreak -->')==5,'Manuscript must specify six pages'
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(OUTPUT),pagesize=A4,rightMargin=44,leftMargin=44,
        topMargin=43,bottomMargin=48,title='FlexMAC: Precision Adaptation, Parallel INT8, and a Measured Pipeline Tradeoff',
        author='Jeremy W. M. (jrmywm)',subject='Independent technical report; pre-layout RTL architecture study')
    doc.build(parse(source,styles),onFirstPage=footer,onLaterPages=footer)
    pdf=PdfReader(OUTPUT)
    assert len(pdf.pages)==6,f'Expected six pages, produced {len(pdf.pages)}; revise layout before delivery'
    for i,page in enumerate(pdf.pages):
        assert len(page.extract_text().strip())>400,f'Unexpectedly sparse or empty page {i+1}'
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    inputs=['docs/data/mapping/mapped_comparison.csv','docs/data/scorepipe/mapped_comparison.csv',
        'docs/data/mapping/metadata.json','docs/data/scorepipe/metadata.json',
        'model/digits/metadata.json','docs/report/flexmac_technical_report.md','docs/report/build_report.py']
    provenance={'report_date':'2026-10-28','scope':'Independent technical report, not peer-reviewed publication',
        'measurement_commits':{'four_design_study':'96141e7767723cfd53e6830a948e46bef05687d8',
            'score_pipeline_study':'8e9065cb147d38b66423997e6d960a7239d8f5e9'},
        'pages':6,'matplotlib':matplotlib.__version__,
        'source_sha256':{p:sha(ROOT/p) for p in inputs},'pdf_sha256':sha(OUTPUT)}
    (HERE/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'Built and text-checked six pages: {OUTPUT}')


if __name__=='__main__':main()

"""Compile the IEEEtran LaTeX report with Tectonic and package its sources."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,zipfile

ROOT=Path(__file__).resolve().parents[2]
TEX=Path(__file__).resolve().parent/'latex'
BUILD=ROOT/'build/latex'
OUTPUT=ROOT/'output/pdf/flexmac_technical_report.pdf'
PACKAGE=ROOT/'output/flexmac_latex_source.zip'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tectonic',type=Path,help='Path to a Tectonic executable')
    args=parser.parse_args()
    executable=args.tectonic or shutil.which('tectonic')
    if not executable:
        bundled=ROOT/'.tools/tectonic/tectonic.exe'
        if bundled.exists():executable=bundled
    if not executable:parser.error('Tectonic not found. Use --tectonic PATH, or compile main.tex in Overleaf/a standard TeX installation.')
    BUILD.mkdir(parents=True,exist_ok=True);OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    version=subprocess.check_output([str(executable),'--version'],text=True).strip()
    result=subprocess.run([str(executable),'--keep-logs','--keep-intermediates',
        '--outdir',str(BUILD),'main.tex'],cwd=TEX,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (BUILD/'compile.log').write_text(result.stdout,encoding='utf-8',newline='\n')
    print(result.stdout)
    if result.returncode:raise SystemExit(result.returncode)
    pdf=BUILD/'main.pdf'
    if not pdf.exists() or not pdf.read_bytes().startswith(b'%PDF-'):raise ValueError('Compiler did not produce a PDF')
    shutil.copyfile(pdf,OUTPUT)
    try:
        from pypdf import PdfReader
        reader=PdfReader(OUTPUT);pages=len(reader.pages)
        text='\n'.join(p.extract_text() for p in reader.pages)
        final_log=(BUILD/'main.log').read_text(encoding='utf-8',errors='replace')
        if re.search(r'LaTeX Warning: (?:Citation .*undefined|Reference .*undefined|There were undefined references)',final_log):
            raise ValueError('Resolve bibliography/reference warnings before publishing')
    except ImportError:pages=None
    names=['main.tex','manuscript.tex','references.bib','IEEEtran.cls','IEEEtran.bst',
        'README.md','template_provenance.json','images/report_datapath.pdf','images/report_results.pdf']
    with zipfile.ZipFile(PACKAGE,'w',zipfile.ZIP_DEFLATED) as z:
        for name in names:z.write(TEX/name,name)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    sources=['docs/report/build_report.py']+['docs/report/latex/'+n for n in names]
    sources += ['docs/data/mapping/mapped_comparison.csv','docs/data/scorepipe/mapped_comparison.csv']
    provenance={'format':'LaTeX IEEEtran conference class, independent technical report',
        'compiler':version,'pages':pages,'source_sha256':{n:sha(ROOT/n) for n in sources},
        'pdf_sha256':sha(OUTPUT),'source_zip_sha256':sha(PACKAGE),
        'measurement_commits':{'four_design_study':'96141e7767723cfd53e6830a948e46bef05687d8',
            'score_pipeline_study':'8e9065cb147d38b66423997e6d960a7239d8f5e9'}}
    (TEX.parent/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'Compiled IEEEtran manuscript: {pages} pages; {OUTPUT}')
    print(f'Overleaf-ready source package: {PACKAGE}')


if __name__=='__main__':main()

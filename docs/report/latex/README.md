# FlexMAC LaTeX manuscript

This is an independent technical report using the original `IEEEtran` conference
class. Its format is a starting point; select the actual venue's template and
requirements before a future submission.

## Edit and compile

- `main.tex`: document class, title, author and package configuration.
- `manuscript.tex`: abstract, body, equations, tables and figure placement.
- `references.bib`: cited primary sources and project evidence.
- `images/`: vector PDF figures, ready for LaTeX.

Upload the self-contained source ZIP to Overleaf and select `main.tex` as the
main document. No Python or EDA tools are needed to compile that package.

With Tectonic installed, run `tectonic main.tex` in this directory. With a
standard TeX installation, use `pdflatex main`, `bibtex main`, then run
`pdflatex main` twice. From the repository root, the optional wrapper
`python docs/report/build_report.py --tectonic PATH` writes the final PDF and
source ZIP under `output/` and records hashes in `docs/report/provenance.json`.

The figures were generated from the archived result CSVs. To regenerate them
inside the full repository, install `docs/report/requirements.txt` and run
`python docs/report/latex/prepare_figures.py`.

## Template provenance and license

`IEEEtran.cls` version 1.8b and `IEEEtran.bst` version 1.14 are unmodified files
from the [CTAN IEEEtran distribution](https://ctan.org/pkg/ieeetran), downloaded
through its MIT mirror. Both retain their upstream copyright and LPPL 1.3
license notices. File and archive hashes are in `template_provenance.json`.

[IEEE Author Center template guidance](https://conferences.ieeeauthorcenter.ieee.org/write-your-paper/authoring-tools-and-templates/)

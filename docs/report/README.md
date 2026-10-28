# FlexMAC LaTeX technical report

The report uses the original IEEEtran conference class in two-column mode,
native LaTeX equations, vector PDF figures, and a BibTeX bibliography. It remains
an independent technical report; the format does not imply peer-reviewed publication.

- [Read the compiled PDF](../../output/pdf/flexmac_technical_report.pdf)
- [Download the Overleaf-ready source ZIP](../../output/flexmac_latex_source.zip)
- [Edit main.tex](latex/main.tex): template, title and author configuration
- [Edit manuscript.tex](latex/manuscript.tex): report body, equations and tables
- [Edit references.bib](latex/references.bib): bibliography
- [Illustrated architecture guide](../architecture.md)

## Compile

Upload the source ZIP to Overleaf and select main.tex. Alternatively, open the
latex/ project in the built-in LaTeX editor, or use a standard TeX installation.

From the full repository, the lightweight Tectonic wrapper is:

```bash
python docs/report/build_report.py --tectonic PATH_TO_TECTONIC
```

If Tectonic is on PATH or at .tools/tectonic/tectonic.exe, omit the option.
The wrapper copies the compiled PDF to output/pdf/, packages the source ZIP,
and records source/output hashes and the compiler version in provenance.json.

Figures are already included as vectors. To regenerate them from the archived
measurements, install requirements.txt and run python docs/report/latex/prepare_figures.py.
This optional Python step prepares figures; LaTeX typesets the manuscript.

The exact IEEEtran class/style versions, upstream URL, license and hashes are in
latex/template_provenance.json. Both third-party files retain their original notices.

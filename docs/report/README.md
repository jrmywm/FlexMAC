# FlexMAC technical report

This directory contains the editable manuscript and its reproducible PDF builder.
The final PDF is linked from the project README. It is an independent technical
report, not a claim of peer-reviewed publication.

The manuscript uses only archived project measurements and cited primary sources.
See the measured-revision and CI references in the report for provenance.

- [Download the six-page PDF](../../output/pdf/flexmac_technical_report.pdf)
- [Edit the manuscript](flexmac_technical_report.md)
- [Read the illustrated architecture guide](../architecture.md)

From the repository root:

```bash
python -m pip install -r docs/report/requirements.txt
python docs/report/build_report.py
```

The builder creates print-sized figures from the archived result CSVs, embeds
fonts, checks the six-page output, and records source/PDF hashes in
`provenance.json`. It does not run training, simulation or synthesis. Editing
the manuscript may require adjusting page breaks to retain six readable pages.

Final layout was checked by rendering and inspecting all six pages. The author
line uses the name recorded in the repository: Jeremy W. M. (jrmywm).

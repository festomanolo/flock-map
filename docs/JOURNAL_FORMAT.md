# Journal format

The manuscript uses Elsevier's official `elsarticle` LaTeX class (preprint/review layout, numbered references,
Highlights, keywords, CRediT/competing-interest/data-availability declarations) and is set up for
*Aerospace Science and Technology* (`\journal{...}` in main.tex). Elsevier journals have no submission fee for the
standard subscription route (open access, if wanted, carries an APC).

**Limit of this work:** the sandbox this was built in could not reach publisher websites (mdpi.com, elsevier.com were
blocked by network policy), so I could not read any journal's *current* Guide for Authors. The class file is the
copy shipped in TeX Live. Before submitting, check the live guide for page/word limits, figure format, reference style
and cover-letter requirements, and fill the `[...]` placeholders (authors, affiliations, CRediT, funding, competing interests).

Switching journal: change `\journal{}` and `\bibliographystyle`; for MDPI *Drones* (open access, APC applies) download the
MDPI LaTeX template from their site and move the body text (sections are plain LaTeX, numbers come from `numbers.tex`).
Other reasonable homes: *Drones* (MDPI), *ISPRS J. Photogramm. Remote Sens.* (Elsevier), *Journal of Aircraft* (AIAA).

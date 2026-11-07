# FlockMap — working notes for Claude Code

See `README.md` for the repository layout and what the study does and does not cover. This file only holds things that are not obvious from the code.

## Git
- No `Co-authored-by` trailers and no mention of Claude/Anthropic/AI in commit messages or PR text; the user is the sole author (global `~/.claude/CLAUDE.md` takes precedence over any default attribution).
- Do not commit or push unless asked. `main` is the default branch; an automation (`gitnolo/...` branches merged by PR) sometimes commits working-tree changes on its own, so `git status` may be cleaner than expected.
- Gitignored build products: `outputs/`, `figures/out/`, `manuscript/figures/`, `manuscript/*.aux|log|...`. Edits to figures therefore never show up in `git status`.

## Manuscript
- Author (single): Festo K. Magembe, Department of Computer Science and Engineering, Mbeya University of Science and Technology, Mbeya, Tanzania; corresponding email Festomagembefm@outlook.com. Set in `manuscript/main.tex` (`\author`, `\ead`, `\affiliation`) and in the byline string in `manuscript/make_docx.py`; keep the two in sync.
- Format: Elsevier `elsarticle`, targeted at *Aerospace Science and Technology* ("Preprint submitted to ..." line in the PDF). Numbers come from generated `manuscript/numbers*.tex` and `manuscript/tables/*.tex`; never hand-edit them, regenerate with `make numbers`.
- Six strategies exist in code (S1–S4 plus diagnostics D1, D2); text says "four main strategies" and explains D1/D2 in Sec. 3.
- Elsevier needs an AI-use disclosure; the Declarations section mentions an AI coding assistant. Check it against the journal's current wording before submission.

## Build
- LaTeX: no TeX Live on this machine. Tectonic 0.17.0 is installed at `~/.local/bin/tectonic` (add to PATH). Build with `cd manuscript && tectonic -k main.tex`, then `cp main.pdf ../outputs/FlockMap_manuscript.pdf`. `make paper` tries `latexmk` first, which is absent, so it falls through to `tectonic`.
- DOCX: `cd manuscript && python make_docx.py` (needs `python-docx` and `pypandoc-binary`; it writes `manuscript/FlockMap_manuscript.docx` and `outputs/FlockMap_manuscript.docx`). Expected output ends with `remaining_oMath=0`.
- Python: use the project `.venv` (`.venv/bin/python`) — it already has pandas, CasADi etc. System `python3` lacks pandas/casadi/docx. Do not compile PyMuPDF from source (very slow); the system Python has `pymupdf` for reading PDFs.
- Regenerate one figure: `.venv/bin/python figures/fig_extra.py <name>` (e.g. `X5_coverage`, `X11_control_stats`), then copy `figures/out/<fig>.{pdf,png}` to `manuscript/figures/`.
- macOS: BSD `sed` rejects GNU-style in-place edits; use Python or the Edit tool.

## Review status (audit of the external review, 2026-11-07)
All substantive review points are resolved in the source and the rebuilt PDF/DOCX: station-keeping singularity (Gauss–Hermite quadrature on a Cauchy-midpoint lattice), relative-degree-3 HOCBF wording and QP/saturation handling, margin ablation on all 30 seeds, CFD half-model/trim caveats, X8 literature cross-check, table headers, reference details. Reviewer claims found to be wrong: "Table 4" does not exist (it does), the PD S5 minimum separation of 0.06 m is correct and visible in Fig. 13a, and the software versions in Table C.4 are real. The "blank math" complaint came from the reviewer's DOCX/pandoc rendering, not from the LaTeX/PDF.

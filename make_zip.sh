#!/bin/bash
# Package everything (code, data, CFD logs/summaries, figures, manuscript PDF+DOCX) without bulky OpenFOAM mesh/processor dirs.
set -e
cd "$(dirname "$0")/.."
OUT=${1:-flockmap-research.zip}; rm -f "$OUT"
zip -qr "$OUT" flockmap-research \
  -x '*/__pycache__/*' '*/.pytest_cache/*' '*.aux' '*.log.bak' '*.fls' '*.fdb_latexmk' '*.out' '*.synctex.gz' '*.bbl' '*.blg' \
  '*/cfd/cases/*/processor*' '*/cfd/cases/*/constant/polyMesh/*' '*/cfd/cases/*/constant/triSurface/*' '*/cfd/cases/*/[1-9]*' '*/cfd/cases/*/VTK/*/internal.vtu' \
  '*/manuscript/docx_build/*' '*/manuscript/main.tex.bak' '*/.git/*'
ls -la "$OUT"

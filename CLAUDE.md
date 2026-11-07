# FlockMap — working notes for Claude Code

See `README.md` for the repository layout and what the study does and does not cover. This file only holds things that are not obvious from the code.

## Git
- No `Co-authored-by` trailers and no mention of Claude/Anthropic/AI in commit messages or PR text; the user is the sole author (global `~/.claude/CLAUDE.md` takes precedence over any default attribution).
- Do not commit or push unless asked. `main` is the default branch; an automation (`gitnolo/...` branches merged by PR) sometimes commits working-tree changes on its own, so `git status` may be cleaner than expected.
- Gitignored build products: `outputs/`, `figures/out/`, `manuscript/figures/`, `manuscript/*.aux|log|...`. Edits to figures therefore never show up in `git status`.

## Manuscript
- Author (single): Festo K. Magembe, Department of Computer Science and Engineering, Mbeya University of Science and Technology, Mbeya, Tanzania; corresponding email Festomagembefm@outlook.com. Set in `manuscript/main.tex` (`\author`, `\ead`, `\affiliation`) and in the byline string in `manuscript/make_docx.py`; keep the two in sync.

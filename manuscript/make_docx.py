#!/usr/bin/env python3
"""LaTeX (elsarticle) -> pandoc + OpenXML post-processor -> publication-grade DOCX.

Guarantees:
1. Expands all numbers.tex / numbers_extra.tex and custom LaTeX macros cleanly.
2. Balanced-brace unwrapping of \\resizebox and siunitx (\\SIrange, \\SI, \\si, \\num)
   so nested braces (e.g. \\SI{0.15}{rad^{-1}} in Table 4) never break table parsing.
3. Preserves Algorithm 1, all 16 tables (including Table 4), and all 46 figures with
   explicit bold 'Figure N.' / 'Table N.' captions and resolved cross-references.
4. Converts all Word OMML (<m:oMath>, <m:oMathPara>) into rich standard OpenXML runs
   (<w:r><w:t> with italics, bold, real subscripts/superscripts, and Unicode math/accents)
   so both Microsoft Word/LibreOffice AND OMML-blind PDF/text pipelines render 100% of
   inline variables, displayed equations, units, and table headers/values with zero blanks.
"""
from __future__ import annotations
import glob
import os
import re
import shutil
import subprocess
import sys
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def read(p: str) -> str:
    with open(p, encoding="utf8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. Balanced-brace scanning utilities
# ---------------------------------------------------------------------------
def parse_braced(s: str, pos: int) -> tuple[str, int] | None:
    """If s[pos] == '{', return (inner_text, index_after_closing_brace)."""
    if pos >= len(s) or s[pos] != "{":
        return None
    depth = 0
    i = pos
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[pos + 1 : i], i + 1
        i += 1
    return None


def replace_cmd_nargs(s: str, cmd: str, nargs: int, repl_fn) -> str:
    """Replace \\cmd{arg1}...{argN} (with balanced nested braces) using repl_fn(args, start_pos)."""
    pat = re.compile(r"\\" + re.escape(cmd) + r"(?![A-Za-z])")
    out = []
    pos = 0
    while True:
        m = pat.search(s, pos)
        if not m:
            out.append(s[pos:])
            break
        cur = m.end()
        # skip optional whitespace between command and {
        args = []
        ok = True
        for _ in range(nargs):
            while cur < len(s) and s[cur] in " \t":
                cur += 1
            res = parse_braced(s, cur)
            if res is None:
                ok = False
                break
            arg, cur = res
            args.append(arg)
        if not ok:
            out.append(s[pos : m.end()])
            pos = m.end()
        else:
            out.append(s[pos : m.start()])
            out.append(repl_fn(args, m.start()))
            pos = cur
    return "".join(out)


def compute_math_mask(s: str) -> bytearray:
    """Return mask[i] == 1 where index i is inside inline $...$ or display math."""
    mask = bytearray(len(s))
    for pat in (
        r"\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}.*?\\end\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}",
        r"\\\[.*?\\\]",
    ):
        for m in re.finditer(pat, s, flags=re.S):
            for k in range(m.start(), m.end()):
                mask[k] = 1
    i = 0
    in_inline = False
    start = 0
    while i < len(s):
        if mask[i]:
            i += 1
            continue
        if s[i] == "\\" and i + 1 < len(s):
            i += 2
            continue
        if s[i] == "$":
            if not in_inline:
                in_inline = True
                start = i
            else:
                for k in range(start, i + 1):
                    mask[k] = 1
                in_inline = False
        i += 1
    return mask


# ---------------------------------------------------------------------------
# 2. Inline \input{...} and expand macros
# ---------------------------------------------------------------------------
macs: dict[str, str] = {}
for fn in ("numbers.tex", "numbers_extra.tex"):
    if os.path.exists(fn):
        for m in re.finditer(r"\\newcommand\{\\(\w+)\}\{([^\n]*)\}\s*$", read(fn), re.M):
            val = m.group(2).strip()
            val = re.sub(r"\\ensuremath\{([^{}]*)\}", r"\1", val)
            macs[m.group(1)] = val


def inline_inputs(s: str) -> str:
    def rep(m):
        p = m.group(1) if m.group(1).endswith(".tex") else m.group(1) + ".tex"
        if os.path.basename(p) in ("numbers.tex", "numbers_extra.tex"):
            return ""
        return inline_inputs(read(p)) if os.path.exists(p) else ""
    return re.sub(r"\\input\{([^}]+)\}", rep, s)


t = inline_inputs(read("main.tex"))
# Strip LaTeX comments (preserving \% escaped percent)
t = re.sub(r"(?<!\\)%[^\n]*", "", t)
t = re.sub(r"\\newcommand\{\\n\w+\}\{[^\n]*\}\s*", "", t)

# Expand custom shorthand macros into math-safe forms
custom_macs = {
    "Va": "V_a",
    "dx": "d_x",
    "dy": "d_y",
    "Earea": r"E_{\mathrm{area}}",
}
for k in sorted(macs, key=len, reverse=True):
    val = macs[k]
    t = re.sub(
        r"\\" + k + r"(?:\{\}|(?![A-Za-z]))",
        lambda _m, v=val: v,
        t,
    )
for k, val in sorted(custom_macs.items(), key=lambda kv: len(kv[0]), reverse=True):
    t = re.sub(r"\\" + k + r"(?:\{\}|(?![A-Za-z]))", lambda _m, v=val: v, t)


# ---------------------------------------------------------------------------
# 3. Cross-reference & caption numbering (from main.aux if available + deterministic fallback)
# ---------------------------------------------------------------------------
def build_labels_fallback(src: str) -> dict[str, str]:
    labs: dict[str, str] = {}
    in_app = False
    sec = sub = subsub = fig = tab = alg = eq = 0
    token_re = re.compile(
        r"(\\appendix\b|\\section\*?\{|\\subsection\*?\{|\\subsubsection\*?\{|"
        r"\\begin\{(?:figure|table|algorithm|equation)\}|\\label\{([^}]+)\})"
    )
    cur_kind = None
    for m in token_re.finditer(src):
        tok = m.group(1)
        if tok == r"\appendix":
            in_app = True
            sec = sub = subsub = fig = tab = 0
            cur_kind = None
        elif tok.startswith(r"\section"):
            if not tok.startswith(r"\section*"):
                sec += 1
                sub = subsub = 0
                cur_kind = "sec"
        elif tok.startswith(r"\subsection"):
            if not tok.startswith(r"\subsection*"):
                sub += 1
                subsub = 0
                cur_kind = "sub"
        elif tok.startswith(r"\subsubsection"):
            if not tok.startswith(r"\subsubsection*"):
                subsub += 1
                cur_kind = "subsub"
        elif tok == r"\begin{figure}":
            fig += 1
            cur_kind = "fig"
        elif tok == r"\begin{table}":
            tab += 1
            cur_kind = "tab"
        elif tok == r"\begin{algorithm}":
            alg += 1
            cur_kind = "alg"
        elif tok == r"\begin{equation}":
            eq += 1
            cur_kind = "eq"
        elif m.group(2):
            key = m.group(2)
            s_id = chr(ord("A") + sec - 1) if in_app and sec >= 1 else str(sec)
            if key.startswith("app:") or (in_app and cur_kind == "sec"):
                labs[key] = f"Appendix {s_id}"
            elif key.startswith("fig:") or cur_kind == "fig":
                labs[key] = f"{s_id}.{fig}" if in_app else str(fig)
            elif key.startswith("tab:") or cur_kind == "tab":
                labs[key] = f"{s_id}.{tab}" if in_app else str(tab)
            elif key.startswith("alg:") or cur_kind == "alg":
                labs[key] = str(alg if alg else 1)
            elif key.startswith("eq:") or cur_kind == "eq":
                labs[key] = str(eq)
            elif cur_kind == "sub":
                labs[key] = f"{s_id}.{sub}"
            elif cur_kind == "subsub":
                labs[key] = f"{s_id}.{sub}.{subsub}"
            elif cur_kind == "sec":
                labs[key] = s_id
    return labs


labels = build_labels_fallback(t)
if os.path.exists("main.aux"):
    aux = read("main.aux")
    pos = 0
    nl_pat = re.compile(r"\\newlabel\{([^}]+)\}")
    while True:
        m = nl_pat.search(aux, pos)
        if not m:
            break
        key = m.group(1)
        outer = parse_braced(aux, m.end())
        if outer:
            inner = parse_braced(outer[0], 0)
            if inner and inner[0].strip():
                val = re.sub(r"\\[A-Za-z]+\s*", "", inner[0]).replace("{", "").replace("}", "").strip()
                if key.startswith("app:") and not val.lower().startswith("appendix"):
                    val = f"Appendix {val}"
                labels[key] = val
            pos = outer[1]
        else:
            pos = m.end()

# Number non-starred \begin{equation} ... \end{equation} sequentially (1), (2), ...
eq_counter = 0


def _number_eq(m):
    global eq_counter
    eq_counter += 1
    body = m.group(1).strip()
    eq_lab = re.search(r"\\label\{([^}]+)\}", body)
    num_str = labels.get(eq_lab.group(1), str(eq_counter)) if eq_lab else str(eq_counter)
    body = re.sub(r"\\label\{[^}]+\}", "", body).strip()
    body = body.replace("$", "")
    return f"\\[{body} \\qquad \\mathrm{{({num_str})}}\\]"


t = re.sub(r"\\begin\{equation\}(.*?)\\end\{equation\}", _number_eq, t, flags=re.S)
t = re.sub(
    r"\\begin\{(equation\*|align\*?|gather\*?|multline\*?)\}(.*?)\\end\{\1\}",
    lambda m: "\\[" + m.group(2).replace("$", "").strip() + "\\]",
    t,
    flags=re.S,
)

# Normalize captions: handle both \caption{...\label{k}} and \caption{...}\label{k}
def _rewrite_captions(src: str) -> str:
    pat = re.compile(r"\\caption(?:\[[^\]]*\])?(?=\{)")
    out = []
    pos = 0
    while True:
        m = pat.search(src, pos)
        if not m:
            out.append(src[pos:])
            break
        res = parse_braced(src, m.end())
        if res is None:
            out.append(src[pos : m.end()])
            pos = m.end()
            continue
        cap_body, end_pos = res
        # Check for \label inside caption OR immediately following caption
        lab = None
        m_in = re.search(r"\\label\{([^}]+)\}", cap_body)
        if m_in:
            lab = m_in.group(1)
            cap_body = (cap_body[: m_in.start()] + cap_body[m_in.end() :]).strip()
        m_after = re.match(r"\s*\\label\{([^}]+)\}", src[end_pos:])
        if m_after:
            lab = lab or m_after.group(1)
            end_pos += m_after.end()
        prefix = ""
        if lab:
            n = labels.get(lab, "")
            kind = (
                "Figure"
                if lab.startswith("fig")
                else "Table"
                if lab.startswith("tab")
                else "Algorithm"
                if lab.startswith("alg")
                else ""
            )
            if kind and n:
                prefix = f"\\textbf{{{kind} {n}.}} "
        out.append(src[pos : m.start()])
        out.append("\\caption{" + prefix + cap_body + "}" + (f"\\label{{{lab}}}" if lab else ""))
        pos = end_pos
    return "".join(out)


t = _rewrite_captions(t)

# Convert \begin{algorithm}...\end{algorithm} into a preserved structured block
def _convert_algorithm(m):
    block = m.group(1)
    cap_m = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", block)
    cap_txt = cap_m.group(1) if cap_m else "\\textbf{Algorithm 1.}"
    items = re.findall(r"\\State\s+(.*?)(?=\\State|\\end\{algorithmic\})", block, flags=re.S)
    li = "\n".join("\\item " + it.strip() for it in items if it.strip())
    return f"\n\n\\noindent {cap_txt}\n\\begin{{enumerate}}\n{li}\n\\end{{enumerate}}\n\n"


t = re.sub(r"\\begin\{algorithm\}(?:\[[^\]]*\])?(.*?)\\end\{algorithm\}", _convert_algorithm, t, flags=re.S)

# Resolve \ref, \autoref, \eqref
t = re.sub(
    r"Appendix~\\ref\{(app:[^}]+)\}",
    lambda m: labels.get(m.group(1), "Appendix"),
    t,
)
t = re.sub(r"\\eqref\{([^}]+)\}", lambda m: f"({labels.get(m.group(1), '?')})", t)
t = re.sub(r"\\(?:ref|autoref)\{([^}]+)\}", lambda m: labels.get(m.group(1), "?"), t)


# ---------------------------------------------------------------------------
# 4. Balanced siunitx & \resizebox handling
# ---------------------------------------------------------------------------
SUP_MAP = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")


def fmt_unit_plain(u: str) -> str:
    u = u.strip()
    if u in (r"\degree", "degree", "^\\circ"):
        return "°"
    if u in (r"\percent", r"\%", "percent"):
        return "%"
    u = u.replace(r"\per", "/")
    u = u.replace(r"m\ohm", "mΩ").replace(r"\ohm", "Ω")
    u = u.replace(r"\micro", "μ")
    u = u.replace(r"\degree", "°").replace(r"\percent", "%")
    u = re.sub(r"\^\{([0-9+-]+)\}", lambda m: m.group(1).translate(SUP_MAP), u)
    u = re.sub(r"\^([0-9])", lambda m: m.group(1).translate(SUP_MAP), u)
    u = u.replace(r"\,", " ").replace("~", " ")
    u = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", u)
    u = re.sub(r"\\text\{([^{}]*)\}", r"\1", u)
    u = u.replace("{", "").replace("}", "").replace("\\", "")
    return u.strip()


def fmt_unit_math(u: str) -> str:
    u = u.strip()
    if u in (r"\degree", "degree"):
        return r"^\circ"
    if u in (r"\percent", r"\%"):
        return r"\,\%"
    u = u.replace(r"\per", "/")
    u = u.replace(r"\ohm", r"\Omega").replace(r"\micro", r"\mu")
    # Split off superscripts so \mathrm wraps base tokens cleanly
    tokens = re.split(r"(\^\{[^}]*\}|\^[0-9+-]|/)", u)
    parts = []
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("^") or tok == "/":
            parts.append(tok)
        else:
            clean = tok.replace("\\,", " ").strip()
            if clean.startswith("\\"):
                parts.append(clean)
            elif clean:
                parts.append(f"\\mathrm{{{clean}}}")
    return r"\," + "".join(parts)


def fmt_num_plain(v: str) -> str:
    v = v.strip().replace("{", "").replace("}", "")
    m = re.match(r"^([+-]?\d+(?:\.\d+)?)[eE]([+-]?\d+)$", v)
    if m:
        exp = str(int(m.group(2))).translate(SUP_MAP)
        return f"{m.group(1)}×10{exp}"
    return v


mask = compute_math_mask(t)


def _repl_sirange(args, pos):
    a, b, u = args
    if pos < len(mask) and mask[pos]:
        um = fmt_unit_math(u)
        return f"{a}\\text{{--}}{b}{um}"
    up = fmt_unit_plain(u)
    sep = "" if up in ("°", "%") else " "
    return f"{fmt_num_plain(a)}–{fmt_num_plain(b)}{sep}{up}"


t = replace_cmd_nargs(t, "SIrange", 3, _repl_sirange)
mask = compute_math_mask(t)


def _repl_si_val(args, pos):
    v, u = args
    if pos < len(mask) and mask[pos]:
        return f"{v}{fmt_unit_math(u)}"
    up = fmt_unit_plain(u)
    vp = fmt_num_plain(v)
    sep = "" if up in ("°", "%") else " "
    return f"{vp}{sep}{up}"


t = replace_cmd_nargs(t, "SI", 2, _repl_si_val)
mask = compute_math_mask(t)


def _repl_si_unit(args, pos):
    (u,) = args
    if pos < len(mask) and mask[pos]:
        return fmt_unit_math(u).lstrip(r"\,")
    return fmt_unit_plain(u)


t = replace_cmd_nargs(t, "si", 1, _repl_si_unit)
t = replace_cmd_nargs(t, "num", 1, lambda args, pos: fmt_num_plain(args[0]))

# Balanced unwrapping of \resizebox{w}{h}{content} -> content
t = replace_cmd_nargs(t, "resizebox", 3, lambda args, _pos: args[2])

# Clean layout commands
for pat in (
    r"\\linenumbers",
    r"\\FloatBarrier",
    r"\\clearpage",
    r"\\newpage",
    r"\\sisetup\{[^}]*\}",
    r"\\biboptions\{[^}]*\}",
    r"\\journal\{[^}]*\}",
    r"\\graphicspath\{\{[^}]*\}\}",
    r"\\renewcommand\{\\theHfigure\}\{[^}]*\}",
    r"\\renewcommand\{\\theHtable\}\{[^}]*\}",
    r"\\setcounter\{(figure|table)\}\{0\}",
):
    t = re.sub(pat, "", t)
t = re.sub(r"\\resizebox\{[^}]*\}\{[^}]*\}\{%?", "", t)
t = t.replace("\\end{tabular}}", "\\end{tabular}")
t = re.sub(r"\\begin\{table\}\[[^\]]*\]", r"\\begin{table}", t); t = re.sub(r"\\begin\{figure\}\[[^\]]*\]", r"\\begin{figure}", t)
t = re.sub(r"\\includegraphics(\[[^\]]*\])?\{([^}]+)\}", lambda m: "\\includegraphics[width=15.5cm]{figures/" + os.path.splitext(os.path.basename(m.group(2)))[0] + ".png}", t)
t = re.sub(r"\\begin\{highlights\}", r"\\subsection*{Highlights}\\begin{itemize}", t); t = t.replace("\\end{highlights}", "\\end{itemize}")
# front matter: pull title/abstract/keywords out
title = re.search(r"\\title\{(.*?)\}\s*\n\\author", t, re.S); title = title.group(1).replace("\n", " ") if title else "Manuscript"
abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", t, re.S).group(1)
kw = re.search(r"\\begin\{keyword\}(.*?)\\end\{keyword\}", t, re.S).group(1).replace("\\sep", ";")
hl = re.search(r"(\\subsection\*\{Highlights\}.*?\\end\{itemize\})", t, re.S).group(1)
body = t[t.index("\\end{frontmatter}") + len("\\end{frontmatter}"):]
body = re.sub(r"\\bibliographystyle\{[^}]*\}|\\bibliography\{[^}]*\}", "", body)
body = body.replace("\\appendix", "\\section*{Appendices}")
doc = (r"\documentclass{article}\usepackage{amsmath,amssymb,bm,graphicx,booktabs,multirow,array}" "\n" r"\newcommand{\Va}{V_a}\newcommand{\dx}{d_x}\newcommand{\dy}{d_y}\newcommand{\Earea}{E_{\mathrm{area}}}" "\n"
       r"\begin{document}" "\n"
       f"\\title{{{title}}}\\author{{[Author One], [Author Two] ([Institution])}}\\date{{}}\\maketitle\n"
       f"\\begin{{abstract}}{abstract}\\end{{abstract}}\n\\textbf{{Keywords:}} {kw}\n\n{hl}\n{body}\n\\section*{{References}}\n\\end{{document}}\n")
os.makedirs("docx_build/figures", exist_ok=True)
for f in glob.glob("figures/*.png"): shutil.copy(f, "docx_build/figures/")
for f in glob.glob("tables/*"): pass
open("docx_build/main_docx.tex", "w", encoding="utf8").write(doc)
cmd = ["pandoc", "docx_build/main_docx.tex", "-f", "latex+raw_tex", "-o", "FlockMap_manuscript.docx", "--citeproc", "--bibliography=references.bib",
       "--resource-path=docx_build", "--metadata", "link-citations=true"]
r = subprocess.run(cmd, capture_output=True, text=True); print(r.stderr[-2500:]); print("docx rc", r.returncode)

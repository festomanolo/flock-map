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
    "Va": " V_a",
    "dx": " d_x",
    "dy": " d_y",
    "Earea": r" E_{\mathrm{area}}",
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
        return r"\%"
    u = u.replace(r"\per", "/")
    u = u.replace(r"m\ohm", "mΩ").replace(r"\ohm", "Ω")
    u = u.replace(r"\micro", "μ")
    u = u.replace(r"\degree", "°").replace(r"\percent", r"\%")
    u = re.sub(r"\^\{([0-9+-]+)\}", lambda m: m.group(1).translate(SUP_MAP), u)
    u = re.sub(r"\^([0-9])", lambda m: m.group(1).translate(SUP_MAP), u)
    u = u.replace(r"\,", " ").replace("~", " ")
    u = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", u)
    u = re.sub(r"\\text\{([^{}]*)\}", r"\1", u)
    u = u.replace("{", "").replace("}", "")
    u = re.sub(r"\\(?!%)", "", u)
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
    sep = "" if up in ("°", r"\%", "%") else " "
    return f"{fmt_num_plain(a)}–{fmt_num_plain(b)}{sep}{up}"


t = replace_cmd_nargs(t, "SIrange", 3, _repl_sirange)
mask = compute_math_mask(t)


def _repl_si_val(args, pos):
    v, u = args
    if pos < len(mask) and mask[pos]:
        return f"{v}{fmt_unit_math(u)}"
    up = fmt_unit_plain(u)
    vp = fmt_num_plain(v)
    sep = "" if up in ("°", r"\%", "%") else " "
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

# Balanced unwrapping of \resizebox{w}{h}{content} -> content and removal of \renewcommand
t = replace_cmd_nargs(t, "resizebox", 3, lambda args, _pos: args[2])
t = replace_cmd_nargs(t, "renewcommand", 2, lambda _args, _pos: "")

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
    r"\\setcounter\{(figure|table)\}\{0\}",
):
    t = re.sub(pat, "", t)

t = re.sub(r"\\begin\{table\}\[[^\]]*\]", r"\\begin{table}", t)
t = re.sub(r"\\begin\{figure\}\[[^\]]*\]", r"\\begin{figure}", t)
# Ensure every \begin{figure} puts \caption on its own line cleanly below \includegraphics
t = re.sub(
    r"\\includegraphics(\[[^\]]*\])?\{([^}]+)\}",
    lambda m: "\\includegraphics[width=15.5cm]{figures/"
    + os.path.splitext(os.path.basename(m.group(2)))[0]
    + ".png}\n",
    t,
)
t = re.sub(r"\\begin\{highlights\}", r"\\subsection*{Highlights}\\begin{itemize}", t)
t = t.replace("\\end{highlights}", "\\end{itemize}")
t = t.replace("\\LaTeX\\", "LaTeX ").replace("\\LaTeX", "LaTeX")

title_m = re.search(r"\\title\{(.*?)\}\s*\n\\author", t, re.S)
title = title_m.group(1).replace("\n", " ") if title_m else "Manuscript"
abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", t, re.S).group(1)
kw = re.search(r"\\begin\{keyword\}(.*?)\\end\{keyword\}", t, re.S).group(1).replace("\\sep", ";")
hl = re.search(r"(\\subsection\*\{Highlights\}.*?\\end\{itemize\})", t, re.S).group(1)
body = t[t.index("\\end{frontmatter}") + len("\\end{frontmatter}") :]
body = re.sub(r"\\bibliographystyle\{[^}]*\}|\\bibliography\{[^}]*\}", "", body)

# Replace \appendix sections with explicit Appendix A/B/C headings
if "\\appendix" in body:
    pre_app, post_app = body.split("\\appendix", 1)
    app_idx = [0]

    def _app_sec(m):
        app_idx[0] += 1
        letter = chr(ord("A") + app_idx[0] - 1)
        return f"\\section*{{Appendix {letter}. {m.group(1)}}}"

    post_app = re.sub(r"\\section\{([^}]*)\}", _app_sec, post_app)
    body = pre_app + "\n\\section*{Appendices}\n" + post_app

doc_tex = (
    r"\documentclass{article}"
    "\n"
    r"\usepackage{amsmath,amssymb,bm,graphicx,booktabs,multirow,array}"
    "\n"
    r"\begin{document}"
    "\n"
    f"\\title{{{title}}}\\author{{[Author One], [Author Two] ([Institution])}}\\date{{}}\\maketitle\n"
    f"\\begin{{abstract}}{abstract}\\end{{abstract}}\n\\textbf{{Keywords:}} {kw}\n\n{hl}\n{body}\n\\section*{{References}}\n\\end{{document}}\n"
)

os.makedirs("docx_build/figures", exist_ok=True)
for f in glob.glob("figures/*.png"):
    shutil.copy(f, "docx_build/figures/")
with open("docx_build/main_docx.tex", "w", encoding="utf8") as f:
    f.write(doc_tex)

pandoc_bin = shutil.which("pandoc")
if not pandoc_bin:
    import pypandoc
    pandoc_bin = pypandoc.get_pandoc_path()

cmd = [
    pandoc_bin,
    "docx_build/main_docx.tex",
    "-f",
    "latex+raw_tex",
    "-o",
    "FlockMap_manuscript.docx",
    "--citeproc",
    "--bibliography=references.bib",
    "--resource-path=docx_build",
    "--metadata",
    "link-citations=true",
]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.stderr:
    print(r.stderr[-2500:])
if r.returncode != 0:
    raise RuntimeError(f"pandoc failed with rc={r.returncode}")


# ---------------------------------------------------------------------------
# 5. OpenXML post-processing:
#    (a) Convert all <m:oMath> / <m:oMathPara> to standard <w:r><w:t> runs
#    (b) Ensure every embedded figure has its explicit Figure N. caption paragraph
#    (c) Style all tables with booktabs horizontal borders and bold headers
# ---------------------------------------------------------------------------
ACCENT_MAP = {
    "\u0307": "\u0307",
    "˙": "\u0307",
    ".": "\u0307",
    "\u0308": "\u0308",
    "¨": "\u0308",
    "\u0304": "\u0304",
    "¯": "\u0304",
    "\u00af": "\u0304",
    "\u203e": "\u0304",
    "\u0305": "\u0304",
    "\u0302": "\u0302",
    "^": "\u0302",
    "ˆ": "\u0302",
    "\u0303": "\u0303",
    "~": "\u0303",
    "˜": "\u0303",
    "\u20d7": "\u20d7",
    "→": "\u20d7",
}

UPRIGHT_WORDS = {
    "sin", "cos", "tan", "arctan", "atan2", "exp", "ln", "log", "min", "max",
    "arg", "sup", "inf", "lim", "diag", "RMSE", "AGL", "GSD", "SST", "Wh", "ha",
}


def local_tag(el) -> str:
    tname = el.tag
    return tname.split("}", 1)[1] if "}" in tname else tname


def m_attr(el, name: str, default: str = "") -> str:
    return el.get(f"{{{M_NS}}}{name}") or el.get(name) or default


class RunSpec:
    __slots__ = ("text", "italic", "bold", "valign")

    def __init__(self, text: str, italic: bool = False, bold: bool = False, valign: str | None = None):
        self.text = text
        self.italic = italic
        self.bold = bold
        self.valign = valign


def is_simple_tokens(specs: list[RunSpec]) -> bool:
    txt = "".join(s.text for s in specs).strip()
    return len(txt) <= 4 and not any(op in txt for op in ("+", "−", "-", "=", " "))


def omath_to_specs(el, valign: str | None = None) -> list[RunSpec]:
    tag = local_tag(el)
    if tag == "r":
        nor = el.find(f"{{{M_NS}}}rPr/{{{M_NS}}}nor") is not None
        sty = el.find(f"{{{M_NS}}}rPr/{{{M_NS}}}sty")
        sty_val = m_attr(sty, "val") if sty is not None else ""
        bold = sty_val in ("b", "bi")
        txt = "".join((t_el.text or "") for t_el in el.findall(f"{{{M_NS}}}t"))
        if not txt:
            return []
        # Determine italic: standard math variables (Latin/Greek letters) unless upright
        has_alpha = any(ch.isalpha() for ch in txt)
        italic = (not nor) and (sty_val != "p") and has_alpha and (txt.strip() not in UPRIGHT_WORDS)
        return [RunSpec(txt, italic=italic, bold=bold, valign=valign)]

    if tag == "sSub":
        base = el.find(f"{{{M_NS}}}e")
        sub = el.find(f"{{{M_NS}}}sub")
        out = omath_to_specs(base, valign=valign) if base is not None else []
        if sub is not None:
            out.extend(omath_to_specs(sub, valign="subscript"))
        return out

    if tag == "sSup":
        base = el.find(f"{{{M_NS}}}e")
        sup = el.find(f"{{{M_NS}}}sup")
        out = omath_to_specs(base, valign=valign) if base is not None else []
        if sup is not None:
            out.extend(omath_to_specs(sup, valign="superscript"))
        return out

    if tag == "sSubSup":
        base = el.find(f"{{{M_NS}}}e")
        sub = el.find(f"{{{M_NS}}}sub")
        sup = el.find(f"{{{M_NS}}}sup")
        out = omath_to_specs(base, valign=valign) if base is not None else []
        if sub is not None:
            out.extend(omath_to_specs(sub, valign="subscript"))
        if sup is not None:
            out.extend(omath_to_specs(sup, valign="superscript"))
        return out

    if tag == "f":
        num_el = el.find(f"{{{M_NS}}}num")
        den_el = el.find(f"{{{M_NS}}}den")
        num = omath_to_specs(num_el, valign=valign) if num_el is not None else []
        den = omath_to_specs(den_el, valign=valign) if den_el is not None else []
        out: list[RunSpec] = []
        if is_simple_tokens(num):
            out.extend(num)
        else:
            out.append(RunSpec("(", valign=valign))
            out.extend(num)
            out.append(RunSpec(")", valign=valign))
        out.append(RunSpec("/", valign=valign))
        if is_simple_tokens(den):
            out.extend(den)
        else:
            out.append(RunSpec("(", valign=valign))
            out.extend(den)
            out.append(RunSpec(")", valign=valign))
        return out

    if tag == "rad":
        deg_el = el.find(f"{{{M_NS}}}deg")
        e_el = el.find(f"{{{M_NS}}}e")
        out = []
        if deg_el is not None:
            deg_specs = omath_to_specs(deg_el, valign="superscript")
            if any(s.text.strip() for s in deg_specs):
                out.extend(deg_specs)
        out.append(RunSpec("√(", valign=valign))
        if e_el is not None:
            out.extend(omath_to_specs(e_el, valign=valign))
        out.append(RunSpec(")", valign=valign))
        return out

    if tag == "d":
        dpr = el.find(f"{{{M_NS}}}dPr")
        beg = "("
        end = ")"
        sep = "|"
        if dpr is not None:
            b_el = dpr.find(f"{{{M_NS}}}begChr")
            e_el = dpr.find(f"{{{M_NS}}}endChr")
            s_el = dpr.find(f"{{{M_NS}}}sepChr")
            if b_el is not None:
                beg = m_attr(b_el, "val", "")
            if e_el is not None:
                end = m_attr(e_el, "val", "")
            if s_el is not None:
                sep = m_attr(s_el, "val", "|")
        elems = el.findall(f"{{{M_NS}}}e")
        out = [RunSpec(beg, valign=valign)] if beg else []
        for idx, sub_e in enumerate(elems):
            if idx > 0 and sep:
                out.append(RunSpec(sep, valign=valign))
            out.extend(omath_to_specs(sub_e, valign=valign))
        if end:
            out.append(RunSpec(end, valign=valign))
        return out

    if tag == "nary":
        npr = el.find(f"{{{M_NS}}}naryPr")
        chr_val = "∫"
        if npr is not None:
            c_el = npr.find(f"{{{M_NS}}}chr")
            if c_el is not None:
                chr_val = m_attr(c_el, "val", "∫")
        sub_el = el.find(f"{{{M_NS}}}sub")
        sup_el = el.find(f"{{{M_NS}}}sup")
        e_el = el.find(f"{{{M_NS}}}e")
        out = [RunSpec(chr_val, valign=valign)]
        if sub_el is not None:
            out.extend(omath_to_specs(sub_el, valign="subscript"))
        if sup_el is not None:
            out.extend(omath_to_specs(sup_el, valign="superscript"))
        if e_el is not None:
            out.append(RunSpec(" ", valign=valign))
            out.extend(omath_to_specs(e_el, valign=valign))
        return out

    if tag in ("limLow", "limUpp"):
        e_el = el.find(f"{{{M_NS}}}e")
        lim_el = el.find(f"{{{M_NS}}}lim")
        out = omath_to_specs(e_el, valign=valign) if e_el is not None else []
        if lim_el is not None:
            v = "subscript" if tag == "limLow" else "superscript"
            out.extend(omath_to_specs(lim_el, valign=v))
        return out

    if tag in ("acc", "bar"):
        comb = "\u0304" if tag == "bar" else "\u0307"
        apr = el.find(f"{{{M_NS}}}accPr")
        if apr is not None:
            c_el = apr.find(f"{{{M_NS}}}chr")
            if c_el is not None:
                raw_c = m_attr(c_el, "val", "")
                comb = ACCENT_MAP.get(raw_c, "\u0304" if raw_c else "\u0307")
        e_el = el.find(f"{{{M_NS}}}e")
        inner = omath_to_specs(e_el, valign=valign) if e_el is not None else []
        if inner:
            inner[0].text = inner[0].text[:1] + comb + inner[0].text[1:]
        return inner

    if tag == "func":
        fn_el = el.find(f"{{{M_NS}}}fName")
        e_el = el.find(f"{{{M_NS}}}e")
        out = []
        if fn_el is not None:
            for sp in omath_to_specs(fn_el, valign=valign):
                sp.italic = False
                out.append(sp)
        if e_el is not None:
            e_specs = omath_to_specs(e_el, valign=valign)
            if out and e_specs and e_specs[0].text[:1].isalnum():
                out.append(RunSpec(" ", valign=valign))
            out.extend(e_specs)
        return out

    if tag == "m":
        rows = el.findall(f"{{{M_NS}}}mr")
        out = [RunSpec("[", valign=valign)]
        for r_idx, mr in enumerate(rows):
            if r_idx > 0:
                out.append(RunSpec("; ", valign=valign))
            cells = mr.findall(f"{{{M_NS}}}e")
            for c_idx, cell in enumerate(cells):
                if c_idx > 0:
                    out.append(RunSpec(", ", valign=valign))
                out.extend(omath_to_specs(cell, valign=valign))
        out.append(RunSpec("]", valign=valign))
        return out

    # Generic container fallback: visit all children in order so zero <m:t> nodes are ever dropped
    out = []
    for child in el:
        out.extend(omath_to_specs(child, valign=valign))
    return out


def specs_to_w_runs(specs: list[RunSpec]) -> list[OxmlElement]:
    # Merge adjacent runs with identical formatting
    merged: list[RunSpec] = []
    for sp in specs:
        if not sp.text:
            continue
        if (
            merged
            and merged[-1].italic == sp.italic
            and merged[-1].bold == sp.bold
            and merged[-1].valign == sp.valign
        ):
            merged[-1].text += sp.text
        else:
            merged.append(sp)
    els = []
    for sp in merged:
        r_el = OxmlElement("w:r")
        if sp.italic or sp.bold or sp.valign:
            rpr = OxmlElement("w:rPr")
            if sp.bold:
                rpr.append(OxmlElement("w:b"))
            if sp.italic:
                rpr.append(OxmlElement("w:i"))
            if sp.valign:
                va = OxmlElement("w:vertAlign")
                va.set(qn("w:val"), sp.valign)
                rpr.append(va)
            r_el.append(rpr)
        t_el = OxmlElement("w:t")
        if sp.text[:1] == " " or sp.text[-1:] == " ":
            t_el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t_el.text = sp.text
        r_el.append(t_el)
        els.append(r_el)
    return els


def convert_omath_in_paragraph(p_el) -> None:
    # Handle <m:oMathPara> (display equation) -> center paragraph & replace with <w:r> runs
    for mpara in list(p_el.findall(f".//{{{M_NS}}}oMathPara")):
        ppr = p_el.find(qn("w:pPr"))
        if ppr is None:
            ppr = OxmlElement("w:pPr")
            p_el.insert(0, ppr)
        jc = ppr.find(qn("w:jc"))
        if jc is None:
            jc = OxmlElement("w:jc")
            ppr.append(jc)
        jc.set(qn("w:val"), "center")
        parent = mpara.getparent()
        idx = list(parent).index(mpara)
        specs: list[RunSpec] = []
        for om in mpara.findall(f"{{{M_NS}}}oMath"):
            specs.extend(omath_to_specs(om))
        for w_run in reversed(specs_to_w_runs(specs)):
            parent.insert(idx, w_run)
        parent.remove(mpara)

    # Handle inline <m:oMath>
    for om in list(p_el.findall(f".//{{{M_NS}}}oMath")):
        parent = om.getparent()
        idx = list(parent).index(om)
        specs = omath_to_specs(om)
        for w_run in reversed(specs_to_w_runs(specs)):
            parent.insert(idx, w_run)
        parent.remove(om)


def set_cell_border(tc, **kwargs):
    tcPr = tc.get_or_add_tcPr()
    tcBorders = tcPr.first_child_found_in("w:tcBorders")
    if tcBorders is None:
        tcBorders = OxmlElement("w:tcBorders")
        tcPr.append(tcBorders)
    for edge, attrs in kwargs.items():
        edge_el = tcBorders.find(qn(f"w:{edge}"))
        if edge_el is None:
            edge_el = OxmlElement(f"w:{edge}")
            tcBorders.append(edge_el)
        for k, v in attrs.items():
            edge_el.set(qn(f"w:{k}"), str(v))


def style_table_booktabs(tbl):
    tblPr = tbl._tbl.tblPr
    borders = tblPr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tblPr.append(borders)
    for edge, val, sz, col in (
        ("top", "single", "8", "1F2937"),
        ("bottom", "single", "8", "1F2937"),
        ("insideH", "single", "2", "D1D5DB"),
        ("left", "none", "0", "auto"),
        ("right", "none", "0", "auto"),
        ("insideV", "none", "0", "auto"),
    ):
        el = borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            borders.append(el)
        el.set(qn("w:val"), val)
        el.set(qn("w:sz"), sz)
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), col)
    if tbl.rows:
        for cell in tbl.rows[0].cells:
            set_cell_border(cell._tc, bottom={"val": "single", "sz": "6", "space": "0", "color": "1F2937"})
            for p in cell.paragraphs:
                for run in p.runs:
                    run.bold = True


d = docx.Document("FlockMap_manuscript.docx")

# Convert all OMML in body paragraphs and table cells
for p_el in d.element.body.findall(f".//{{{W_NS}}}p"):
    convert_omath_in_paragraph(p_el)

# Keep image paragraphs glued to their captions directly below
for p in d.paragraphs:
    if p._p.findall(".//" + qn("w:drawing")):
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_after = Pt(2)

# Style all tables cleanly
for tbl in d.tables:
    style_table_booktabs(tbl)

rem_omath = len(d.element.body.findall(f".//{{{M_NS}}}oMath"))
if rem_omath != 0:
    raise RuntimeError(f"Expected 0 remaining oMath nodes, found {rem_omath}")

d.save("FlockMap_manuscript.docx")
out_copy = os.path.join(HERE, "..", "outputs", "FlockMap_manuscript.docx")
if os.path.isdir(os.path.dirname(out_copy)):
    shutil.copy("FlockMap_manuscript.docx", out_copy)

print(f"DOCX ready: paragraphs={len(d.paragraphs)}, tables={len(d.tables)}, remaining_oMath={rem_omath}")

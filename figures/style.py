import matplotlib as mpl
import matplotlib.pyplot as plt

C = dict(blue="#2a78d6", orange="#eb6834", aqua="#1baf7a", yellow="#eda100", magenta="#e87ba4", green="#008300",
         violet="#6250d6", red="#e34948", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9", axis="#c3c2b7",
         surface="#ffffff")
STRAT = {"S1_independent": ("S1 Independent", C["blue"]), "S2_rigid_V": ("S2 Rigid V", C["orange"]),
         "S3_adaptive_geometric": ("S3 Adaptive geometric V", C["aqua"]), "S4_wake_aware": ("S4 Wake-aware adaptive V", C["violet"]),
         "D1_independent_14": ("D1 Independent, 14-strip route", C["magenta"])}
MODEL = {"published": ("Manuscript equations (as published)", C["red"]), "strip_corrected": ("Strip theory, corrected", C["orange"]),
         "vlm_analytic": ("VLM follower, analytic wake", C["yellow"]), "vlm_rolled": ("VLM follower, rolled-up pair", C["aqua"]),
         "vlm_sheet": ("VLM follower, planar sheet", C["blue"]), "vlm_free": ("VLM follower, free wake", C["violet"])}


def setup():
    mpl.rcParams.update({
        "font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix",
        "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8.5, "legend.fontsize": 7, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
        "axes.edgecolor": C["axis"], "axes.linewidth": 0.7, "axes.labelcolor": C["ink"], "text.color": C["ink"],
        "xtick.color": C["ink2"], "ytick.color": C["ink2"], "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": C["grid"], "grid.linewidth": 0.5, "axes.axisbelow": True,
        "lines.linewidth": 1.6, "legend.frameon": False, "figure.dpi": 150, "savefig.dpi": 300, "savefig.bbox": "tight",
        "figure.facecolor": "white", "axes.facecolor": "white", "pdf.fonttype": 42})


def save(fig, name):
    import os
    os.makedirs("figures/out", exist_ok=True)
    fig.savefig(f"figures/out/{name}.pdf"); fig.savefig(f"figures/out/{name}.png")
    plt.close(fig)


def panel(ax, letter):
    ax.text(-0.02, 1.04, f"({letter})", transform=ax.transAxes, fontsize=8.5, fontweight="bold", va="bottom", ha="right")

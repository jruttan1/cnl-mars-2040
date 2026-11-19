"""Make a slide-ready chart of the Strategy D estimator.

Run from the repo root:
    .venv/bin/python -B -m bayes_estimator.plot_d
Saves: results/bayes_estimator/strategy_d_estimator.png
"""
import logging
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)   # quiet font fallbacks
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from bayes_estimator import estimator as E, markers as M
from bayes_estimator.demo_d import readings

LIMIT_mGy = M.NASA_30D_LIMIT_mGyEq / M.RBE_BFO     # top of range must stay below this (~167)
CASES = [("Scenario 1: Low exposure (40 mGy)", 40), ("Scenario 2: High exposure (600 mGy)", 600)]
XMIN, XMAX = 10, 3000

BLUE, ORANGE = "#2a78d6", "#eb6834"                # blue = keep working, orange = stop
BLUE_ZONE, ORANGE_ZONE = "#eef4fc", "#fdf0ea"      # faint background zones
INK, INK2, INK3, GRID = "#16181d", "#5b5f68", "#9a9ea6", "#e6e8ec"
KEEP_WORKING = {"proceed", "rotate crew"}
LABEL = {"proceed": "Proceed", "rotate crew": "Keep working",
         "shelter/delay": "Shelter / delay", "abort / treat": "Stop & treat"}
ROWS = [("No test yet", "right after EVA"),
        ("Foci + AEN", "back inside · ~4.5 h"),
        ("+ 4-gene panel", "all 4 genes · 8 h"),
        ("+ FDXR", "next day · 24 h")]
TOP = len(ROWS) - 1


def main():
    plt.rcParams.update({"font.family": ["Inter", "Helvetica Neue", "Arial", "DejaVu Sans"],
                         "font.size": 13})
    fig, axes = plt.subplots(2, 1, figsize=(13, 8.6), sharex=True)

    for ax, (title, true) in zip(axes, CASES):
        rng = np.random.default_rng(42)
        a, b, c = readings(true, rng)        # device results only; estimator never sees `true`
        results = [E.estimate([]), E.estimate(a), E.estimate(a + b), E.estimate(a + b + c)]

        # background zones: safe (left of limit) and over the limit (right)
        ax.axvspan(XMIN, LIMIT_mGy, color=BLUE_ZONE, zorder=0, lw=0)
        ax.axvspan(LIMIT_mGy, XMAX, color=ORANGE_ZONE, zorder=0, lw=0)
        ax.axvline(LIMIT_mGy, color=INK2, lw=1.4, ls=(0, (5, 4)), zorder=1)

        # actual dose: thin line + marker on top
        ax.vlines(true, -0.6, TOP + 0.62, color=INK, lw=1.1, alpha=0.45, zorder=1)
        ax.plot(true, TOP + 0.72, marker="v", ms=9, color=INK, zorder=5, clip_on=False)
        ax.text(true, TOP + 0.95, f"actual {true} mGy", ha="center", va="bottom", fontsize=11, color=INK)

        for i, e in enumerate(results):
            y = TOP - i
            d = E.decision(e["upper95"])
            col = BLUE if d in KEEP_WORKING else ORANGE
            ax.plot([e["lo95"], e["upper95"]], [y, y], color=col, lw=14,
                    solid_capstyle="round", zorder=3)                       # 95% range
            if i > 0:                                                       # best guess
                ax.plot(e["mean"], y, "o", ms=11, color="white", mec=col, mew=3, zorder=4)
            # decision: small dot + coloured text
            ax.plot(4000, y, "o", ms=9, color=col, clip_on=False)
            ax.text(4700, y, LABEL[d], va="center", ha="left", fontsize=13, fontweight="bold",
                    color=col, clip_on=False)

        # row labels: step name + timing
        ax.set_yticks([])
        for i, (name, when) in enumerate(ROWS):
            y = TOP - i
            ax.text(7.6, y + 0.1, name, ha="right", va="center", fontsize=13, color=INK, fontweight="bold")
            ax.text(7.6, y - 0.24, when, ha="right", va="center", fontsize=10.5, color=INK3)

        ax.set_ylim(-0.6, TOP + 1.25)
        ax.set_title(title, loc="left", fontsize=15, fontweight="bold", color=INK, pad=10, x=-0.155)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(length=0, colors=INK2, labelsize=12)
        ax.grid(axis="x", color="white", lw=1.2); ax.set_axisbelow(True)

    # zone labels on the first panel only
    axes[0].text(LIMIT_mGy / 1.06, -0.45, "under limit", ha="right", va="center", fontsize=10.5, color=BLUE)
    axes[0].text(LIMIT_mGy * 1.06, -0.45, "over limit", ha="left", va="center", fontsize=10.5, color=ORANGE)

    ax = axes[1]
    ax.set_xscale("log"); ax.set_xlim(XMIN, XMAX)
    ticks = [10, 30, 100, 300, 1000, 3000]
    ax.set_xticks(ticks); ax.set_xticklabels([str(t) for t in ticks]); ax.minorticks_off()
    axes[0].minorticks_off()
    ax.set_xlabel("Radiation dose (mGy, log scale)", color=INK2, fontsize=12, labelpad=8)

    legend = [Line2D([], [], color=BLUE, lw=8, solid_capstyle="round", label="95% range: safe"),
              Line2D([], [], color=ORANGE, lw=8, solid_capstyle="round", label="95% range: too high / unknown"),
              Line2D([], [], marker="o", ls="", ms=9, mfc="white", mec=INK2, mew=2.2, label="best guess"),
              Line2D([], [], color=INK2, lw=1.4, ls=(0, (5, 4)), label="safety limit")]
    fig.legend(handles=legend, loc="lower center", ncol=4, frameon=False, fontsize=11.5,
               bbox_to_anchor=(0.52, 0.0), handlelength=2.2, columnspacing=2)
    fig.subplots_adjust(left=0.18, right=0.82, top=0.93, bottom=0.15, hspace=0.5)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "results", "bayes_estimator")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "strategy_d_estimator.png")
    fig.savefig(path, dpi=200, facecolor="white")
    print("Saved", path)


if __name__ == "__main__":
    main()
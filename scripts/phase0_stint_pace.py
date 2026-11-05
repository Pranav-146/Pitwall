"""Phase 0: stint pace by compound for the top 5 finishers of the 2024 Bahrain GP.

Plots raw laps. Nothing is cleaned yet: laps a cleaning rule would likely touch
are drawn hollow, and laps above the y-range are shown as ticks on the top edge.
"""

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from pitwall.data import REPO_ROOT
from pitwall.openf1 import find_race_session, load_laps, load_results

YEAR, COUNTRY, ROUND = 2024, "Bahrain", 1
TOP_N = 5
Y_MIN, Y_MAX = 92.0, 101.0
OUTPUT = REPO_ROOT / "figures" / "phase0_stint_pace_bahrain_2024.png"

SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
COMPOUND_STYLE = {
    "SOFT": {"color": "#e34948", "marker": "o"},
    "MEDIUM": {"color": "#eda100", "marker": "D"},
    "HARD": {"color": "#2a78d6", "marker": "s"},
}


def plot_driver(ax, laps) -> None:
    for _, stint in laps.groupby("Stint"):
        compound = stint["Compound"].iloc[0]
        style = COMPOUND_STYLE[compound]
        suspect = stint["PitIn"] | stint["PitOut"] | (stint["LapNumber"] == 1)
        visible = stint["LapTimeSeconds"] <= Y_MAX

        racing = stint[~suspect]
        ax.plot(racing["LapNumber"], racing["LapTimeSeconds"], color=style["color"],
                linewidth=1, alpha=0.45, zorder=2)
        ax.scatter(racing["LapNumber"], racing["LapTimeSeconds"], s=30, color=style["color"],
                   marker=style["marker"], edgecolor=SURFACE, linewidth=0.6, zorder=3)
        flagged = stint[suspect & visible]
        ax.scatter(flagged["LapNumber"], flagged["LapTimeSeconds"], s=30, facecolor="none",
                   edgecolor=style["color"], marker=style["marker"], linewidth=1.2, zorder=3)
        off_scale = stint[~visible]
        ax.scatter(off_scale["LapNumber"], [Y_MAX] * len(off_scale), s=34, marker="^",
                   facecolor="none", edgecolor=style["color"], linewidth=1.2, clip_on=False,
                   zorder=4)

        start, end = stint["LapNumber"].min(), stint["LapNumber"].max()
        age = int(stint["TyreLife"].iloc[0]) - 1
        label = f"{compound.title()} · {len(stint)} laps" + (f" · started {age} laps old" if age else "")
        ax.text((start + end) / 2, Y_MIN + 0.1, label, ha="center", va="bottom",
                fontsize=9, color=MUTED)
        if end < laps["LapNumber"].max():
            ax.axvline(end + 0.5, color=MUTED, linewidth=0.8, linestyle=(0, (3, 3)), zorder=1)

    ax.set_ylim(Y_MIN, Y_MAX)
    ax.set_xlim(0, laps["LapNumber"].max() + 1)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, length=0, labelsize=9)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def legend_handles(compounds) -> list:
    def handle(label, **kwargs):
        return Line2D([], [], linestyle="none", markersize=7, label=label, **kwargs)

    handles = [
        handle(c.title(), marker=COMPOUND_STYLE[c]["marker"], color=COMPOUND_STYLE[c]["color"])
        for c in COMPOUND_STYLE
        if c in compounds
    ]
    handles.append(handle("Lap 1, in-lap or out-lap", marker="o", markerfacecolor="none",
                          markeredgecolor=MUTED))
    handles.append(handle(f"Off scale (> {Y_MAX:.0f}s)", marker="^", markerfacecolor="none",
                          markeredgecolor=MUTED))
    return handles


def main() -> None:
    results = load_results(YEAR, ROUND).head(TOP_N)
    laps = load_laps(find_race_session(YEAR, COUNTRY))

    fig, axes = plt.subplots(TOP_N, 1, figsize=(11, 11), sharex=True, sharey=True,
                             facecolor=SURFACE)
    for ax, result in zip(axes, results.itertuples()):
        ax.set_facecolor(SURFACE)
        plot_driver(ax, laps[laps["DriverNumber"] == result.DriverNumber])
        ax.set_title(f"P{result.Position}  {result.Driver}  ·  {result.Team}", loc="left",
                     fontsize=11, color=INK, fontweight="bold", pad=12)

    axes[-1].set_xlabel("Lap", color=MUTED)
    fig.supylabel("Lap time (s)", color=MUTED, fontsize=10, x=0.012)
    fig.suptitle("2024 Bahrain GP: stint pace by compound, top 5 finishers", x=0.055, y=0.985,
                 ha="left", fontsize=15, fontweight="bold", color=INK)
    fig.text(0.055, 0.952, "Raw laps, uncleaned. Lap times fall through a stint as fuel burns "
             "off, which hides tyre wear. Data: OpenF1, results: Jolpica.",
             fontsize=9.5, color=MUTED)
    fig.legend(handles=legend_handles(set(laps["Compound"])), loc="upper left", ncol=4,
               frameon=False, fontsize=9.5, labelcolor=MUTED, bbox_to_anchor=(0.048, 0.948))
    fig.subplots_adjust(left=0.055, right=0.985, top=0.885, bottom=0.05, hspace=0.38)

    OUTPUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUTPUT, dpi=160, facecolor=SURFACE)
    print(f"saved {OUTPUT}")


if __name__ == "__main__":
    main()

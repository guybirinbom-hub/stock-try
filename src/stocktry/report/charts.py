"""Static PNG charts for the committed report (matplotlib, Agg backend).

Colour rules: each strategy keeps one categorical colour in every chart
(colour follows the entity); heatmaps use a single-hue sequential blue ramp;
one y-axis per panel; thin 1.6 px lines; recessive hairline grid; a legend
on every multi-series chart plus direct end labels. The numbers behind every
chart are in the accompanying markdown tables (the "table view").
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES_COLORS: dict[str, str] = {  # fixed categorical order (validated palette)
    "spy_buy_hold": "#2a78d6",
    "sixty_forty": "#eb6834",
    "trend_sma10": "#1baf7a",
    "trend_absmom12": "#eda100",
    "trend_ensemble": "#e87ba4",
    "gtaa4": "#008300",
    "gtaa5": "#4a3aa7",
}
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def _style(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def equity_and_drawdown(monthly: dict[str, pd.Series], path: Path, title: str, labels: dict[str, str]) -> None:
    """Growth of $1 (log scale) above drawdown from peak; two panels sharing the date axis."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.2), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    fig.patch.set_facecolor(SURFACE)
    for ax in (ax1, ax2):
        _style(ax)
    ends = []
    for name, r in monthly.items():
        col = SERIES_COLORS.get(name, INK2)
        eq = (1 + r).cumprod()
        eq = pd.concat([pd.Series([1.0], index=[r.index[0] - pd.offsets.MonthEnd(1)]), eq])
        dd = eq / eq.cummax() - 1
        ax1.plot(eq.index, eq.values, color=col, linewidth=1.6, label=labels.get(name, name))
        ends.append((float(eq.iloc[-1]), eq.index[-1], col))
        ax2.plot(dd.index, dd.values * 100, color=col, linewidth=1.2)
    # Direct end labels, nudged apart in log space so they never overlap; a colour tick carries identity.
    ends.sort(key=lambda x: x[0])
    placed: list[float] = []
    for v, d, col in ends:
        y = np.log10(v)
        if placed and y - placed[-1] < 0.045:
            y = placed[-1] + 0.045
        placed.append(y)
        ax1.annotate(f"{v:.1f}x", xy=(d, v), xytext=(d, 10**y), textcoords="data", fontsize=7, color=INK2,
                     va="center", ha="left")
        ax1.plot([d], [v], marker="o", markersize=3, color=col)
    ax1.set_yscale("log")
    from matplotlib.ticker import FuncFormatter, LogLocator

    ax1.yaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
    ax1.yaxis.set_minor_locator(LogLocator(base=10, subs=()))
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}x"))
    ax1.set_xlim(right=ax1.get_xlim()[1] + (ax1.get_xlim()[1] - ax1.get_xlim()[0]) * 0.05)
    ax1.set_ylabel("Growth of $1 (log scale)", color=INK2, fontsize=9)
    ax2.set_ylabel("Drawdown from peak (%)", color=INK2, fontsize=9)
    ax1.set_title(title, loc="left", color=INK, fontsize=11)
    ax1.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def heatmap(df: pd.DataFrame, path: Path, title: str, cbar_label: str, annotate: bool = True,
            fmt: str = "{:.2f}", reverse: bool = False) -> None:
    """Sequential single-hue heatmap; darker = larger (or smaller if ``reverse``)."""
    cmap = LinearSegmentedColormap.from_list("seqblue", SEQ_BLUE[::-1] if reverse else SEQ_BLUE)
    h = max(2.2, 0.32 * len(df.index) + 1.4)
    w = max(6.0, 0.42 * len(df.columns) + 2.4)
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_facecolor(SURFACE)
    vals = df.to_numpy(dtype=float)
    im = ax.imshow(vals, cmap=cmap, aspect="auto")
    ax.set_xticks(range(len(df.columns)), [str(c) for c in df.columns], fontsize=7, color=MUTED)
    ax.set_yticks(range(len(df.index)), [str(i) for i in df.index], fontsize=7, color=MUTED)
    ax.set_xlabel(str(df.columns.name or ""), color=INK2, fontsize=8)
    ax.set_ylabel(str(df.index.name or ""), color=INK2, fontsize=8)
    for s in ax.spines.values():
        s.set_visible(False)
    if annotate:
        lo, hi = np.nanmin(vals), np.nanmax(vals)
        mid = (lo + hi) / 2
        for i in range(vals.shape[0]):
            for j in range(vals.shape[1]):
                v = vals[i, j]
                if np.isfinite(v):
                    dark = (v > mid) != reverse
                    ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=6.5,
                            color="#ffffff" if dark else INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label(cbar_label, color=INK2, fontsize=8)
    cb.ax.tick_params(labelsize=7, colors=MUTED)
    cb.outline.set_visible(False)
    ax.set_title(title, loc="left", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def bars(values: pd.Series, path: Path, title: str, ylabel: str, highlight: str | None = None,
         color: str = "#2a78d6") -> None:
    """Single-series bar chart (one colour); an optional reference line for the tranched average."""
    fig, ax = plt.subplots(figsize=(8, 3.2))
    fig.patch.set_facecolor(SURFACE)
    _style(ax)
    x = np.arange(len(values))
    ax.bar(x, values.to_numpy() * 100, color=color, width=0.7)
    ax.set_xticks(x, [str(i) for i in values.index], fontsize=7)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)
    ax.set_xlabel(str(values.index.name or ""), color=INK2, fontsize=8)
    if highlight is not None:
        ax.axhline(float(highlight) * 100, color=INK, linewidth=1.0)
        title = f"{title}\nhorizontal line = tranched portfolio (21 sub-accounts) {float(highlight) * 100:.2f}%"
    ax.set_title(title, loc="left", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)

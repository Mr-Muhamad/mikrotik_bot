"""Visual chart generator using matplotlib for Telegram statistics & analytics.

Generates PNG chart streams (BytesIO) using non-interactive Agg backend.
Provides trend charts for active users/bandwidth and sales distribution.
"""

from __future__ import annotations

import io
import logging

import matplotlib

from core.mikrotik_client import RouterOSRow

# Set non-interactive backend before pyplot import
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

logger = logging.getLogger(__name__)

# Modern Dark Theme Palette
BG_COLOR = "#1e1e2e"
PANEL_COLOR = "#181825"
TEXT_COLOR = "#cdd6f4"
GRID_COLOR = "#313244"
CYAN_LINE = "#89b4fa"
GREEN_LINE = "#a6e3a1"
ORANGE_BAR = "#fab387"
PURPLE_BAR = "#cba6f7"


def _configure_dark_style(fig: plt.Figure, ax: plt.Axes) -> None:
    """Apply modern sleek dark styling to a matplotlib figure and axes."""
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(PANEL_COLOR)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID_COLOR)
    ax.spines["bottom"].set_color(GRID_COLOR)

    ax.tick_params(colors=TEXT_COLOR, labelsize=9)
    ax.yaxis.label.set_color(TEXT_COLOR)
    ax.xaxis.label.set_color(TEXT_COLOR)
    ax.title.set_color(TEXT_COLOR)
    ax.grid(True, color=GRID_COLOR, linestyle="--", alpha=0.5)


def generate_trend_chart(
    snapshots: list[RouterOSRow], title: str = "نشاط المستخدمين (آخر 7 أيام)"
) -> bytes:
    """Generate a PNG trend chart stream for active users and byte usage over time."""
    if not snapshots:
        snapshots = [
            {
                "snapshot_date": "اليوم",
                "active_users": 0,
                "total_users": 0,
                "bytes_in": 0,
                "bytes_out": 0,
            }
        ]

    dates = [str(s.get("snapshot_date", ""))[-5:] for s in snapshots]
    active_users = [int(s.get("active_users", 0) or 0) for s in snapshots]
    total_users = [int(s.get("total_users", 0) or 0) for s in snapshots]

    fig, ax1 = plt.subplots(figsize=(8, 4.5), dpi=120)
    _configure_dark_style(fig, ax1)

    ax1.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax1.set_ylabel("عدد المستخدمين", fontsize=10)

    # Plot Total & Active Users
    line1 = ax1.plot(
        dates,
        total_users,
        color=CYAN_LINE,
        marker="o",
        linewidth=2.5,
        label="إجمالي المستخدمين",
    )
    line2 = ax1.plot(
        dates,
        active_users,
        color=GREEN_LINE,
        marker="s",
        linewidth=2.5,
        linestyle="--",
        label="المستخدمين النشطين",
    )
    ax1.fill_between(dates, active_users, color=GREEN_LINE, alpha=0.15)

    # Legends & Layout
    lines = line1 + line2
    labels = [str(line.get_label()) for line in lines]
    leg = ax1.legend(
        lines,
        labels,
        loc="upper left",
        facecolor=PANEL_COLOR,
        edgecolor=GRID_COLOR,
    )
    for text in leg.get_texts():
        text.set_color(TEXT_COLOR)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_sales_chart(
    batches: list[RouterOSRow], title: str = "توزيع مبيعات الكروت حسب الباقة"
) -> bytes:
    """Generate a PNG bar chart stream for card batch sales by profile."""
    if not batches:
        profile_counts = {"لا توجد مبيعات": 0}
    else:
        profile_counts: dict[str, int] = {}
        for b in batches:
            prof = str(b.get("profile") or "غير محدد")
            cnt = int(b.get("count", 0) or 0)
            profile_counts[prof] = profile_counts.get(prof, 0) + cnt

    profiles = list(profile_counts.keys())
    counts = list(profile_counts.values())

    fig, ax = plt.subplots(figsize=(7.5, 4), dpi=120)
    _configure_dark_style(fig, ax)

    ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("عدد الكروت المباعة", fontsize=10)

    bars = ax.bar(profiles, counts, color=PURPLE_BAR, width=0.5, edgecolor=CYAN_LINE)

    # Value Labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f"{int(height)}",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            color=TEXT_COLOR,
            fontsize=9,
            fontweight="bold",
        )

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

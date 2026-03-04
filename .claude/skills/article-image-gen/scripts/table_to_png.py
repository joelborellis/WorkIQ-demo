#!/usr/bin/env python3
"""
table_to_png.py — Convert a markdown table to a publication-ready PNG image.

Part of the article-image-gen skill for Claude Code.
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.colors import to_rgba
    import numpy as np
except ImportError:
    print("ERROR: matplotlib is required. Run: pip install matplotlib", file=sys.stderr)
    sys.exit(1)

# ── Themes ────────────────────────────────────────────────────────────────────

THEMES = {
    "light": {
        "bg": "#FFFFFF",
        "header_bg": "#2C3E50",
        "header_fg": "#FFFFFF",
        "row_even": "#F8F9FA",
        "row_odd": "#FFFFFF",
        "border": "#DEE2E6",
        "text": "#212529",
        "title": "#2C3E50",
        "accent": "#3498DB",
    },
    "dark": {
        "bg": "#1E1E2E",
        "header_bg": "#313244",
        "header_fg": "#CDD6F4",
        "row_even": "#242438",
        "row_odd": "#1E1E2E",
        "border": "#45475A",
        "text": "#CDD6F4",
        "title": "#89B4FA",
        "accent": "#89DCEB",
    },
    "blue": {
        "bg": "#EBF5FB",
        "header_bg": "#1A5276",
        "header_fg": "#FFFFFF",
        "row_even": "#D6EAF8",
        "row_odd": "#EBF5FB",
        "border": "#AED6F1",
        "text": "#1B2631",
        "title": "#1A5276",
        "accent": "#2E86C1",
    },
    "green": {
        "bg": "#EAFAF1",
        "header_bg": "#1D6A39",
        "header_fg": "#FFFFFF",
        "row_even": "#D5F5E3",
        "row_odd": "#EAFAF1",
        "border": "#A9DFBF",
        "text": "#1C352D",
        "title": "#1D6A39",
        "accent": "#27AE60",
    },
}

# ── Markdown Table Parser ─────────────────────────────────────────────────────

def parse_markdown_table(text: str) -> tuple[list[str], list[list[str]]]:
    """Parse a markdown table into headers and rows."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    # Filter out separator lines (e.g., |---|---|)
    data_lines = [l for l in lines if not re.match(r"^\|[-:| ]+\|$", l)]

    if not data_lines:
        raise ValueError("No valid table data found.")

    def split_row(line: str) -> list[str]:
        # Remove leading/trailing pipes and split
        inner = line.strip().strip("|")
        return [cell.strip() for cell in inner.split("|")]

    headers = split_row(data_lines[0])
    rows = [split_row(l) for l in data_lines[1:]]

    # Normalize column count
    ncols = len(headers)
    normalized_rows = []
    for row in rows:
        if len(row) < ncols:
            row += [""] * (ncols - len(row))
        normalized_rows.append(row[:ncols])

    return headers, normalized_rows


# ── Table Renderer ─────────────────────────────────────────────────────────────

def render_table_png(
    headers: list[str],
    rows: list[list[str]],
    output_path: str,
    title: str = "",
    theme_name: str = "light",
    font_size: int = 12,
    min_width: int = 1000,
) -> str:
    """Render headers + rows as a styled PNG table."""

    theme = THEMES.get(theme_name, THEMES["light"])
    ncols = len(headers)
    nrows = len(rows)

    # Compute column widths based on content
    col_widths = []
    for i in range(ncols):
        max_len = len(headers[i])
        for row in rows:
            if i < len(row):
                max_len = max(max_len, len(str(row[i])))
        col_widths.append(max(max_len, 8))

    total_chars = sum(col_widths)
    char_to_inch = 0.11  # rough mapping
    fig_width = max(min_width / 100, total_chars * char_to_inch + 1)
    header_height = 0.5
    row_height = 0.38
    title_height = 0.6 if title else 0.1
    footer_height = 0.2

    fig_height = title_height + header_height + nrows * row_height + footer_height

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=144)
    fig.patch.set_facecolor(theme["bg"])
    ax.set_facecolor(theme["bg"])
    ax.axis("off")

    # Total height in data coords (we'll use 0–1 normalized)
    total_h = fig_height
    y_cursor = fig_height

    # ── Title ──────────────────────────────────────────────────────────────
    if title:
        y_cursor -= title_height
        ax.text(
            fig_width / 2,
            y_cursor + title_height * 0.55,
            title,
            ha="center",
            va="center",
            fontsize=font_size + 4,
            fontweight="bold",
            color=theme["title"],
            transform=ax.transData,
        )
        # Accent underline
        ax.plot(
            [fig_width * 0.1, fig_width * 0.9],
            [y_cursor + title_height * 0.1, y_cursor + title_height * 0.1],
            color=theme["accent"],
            linewidth=2,
        )

    ax.set_xlim(0, fig_width)
    ax.set_ylim(0, fig_height)

    # Column x positions
    col_fractions = [w / total_chars for w in col_widths]
    x_positions = [0.0]
    for f in col_fractions:
        x_positions.append(x_positions[-1] + f * fig_width)

    def draw_cell(x0, x1, y0, y1, text, bg, fg, bold=False, align="left"):
        rect = mpatches.FancyBboxPatch(
            (x0, y0),
            x1 - x0,
            y1 - y0,
            boxstyle="square,pad=0",
            facecolor=bg,
            edgecolor=theme["border"],
            linewidth=0.5,
        )
        ax.add_patch(rect)
        pad = (x1 - x0) * 0.04
        text_x = x0 + pad if align == "left" else (x0 + x1) / 2
        ax.text(
            text_x,
            (y0 + y1) / 2,
            str(text),
            ha="left" if align == "left" else "center",
            va="center",
            fontsize=font_size,
            fontweight="bold" if bold else "normal",
            color=fg,
            clip_on=True,
        )

    # ── Header row ─────────────────────────────────────────────────────────
    y_cursor -= header_height
    for i, header in enumerate(headers):
        draw_cell(
            x_positions[i],
            x_positions[i + 1],
            y_cursor,
            y_cursor + header_height,
            header.upper(),
            theme["header_bg"],
            theme["header_fg"],
            bold=True,
            align="center",
        )

    # ── Data rows ───────────────────────────────────────────────────────────
    for r_idx, row in enumerate(rows):
        y_cursor -= row_height
        row_bg = theme["row_even"] if r_idx % 2 == 0 else theme["row_odd"]
        for c_idx, cell in enumerate(row):
            draw_cell(
                x_positions[c_idx],
                x_positions[c_idx + 1],
                y_cursor,
                y_cursor + row_height,
                cell,
                row_bg,
                theme["text"],
            )

    # ── Footer line ─────────────────────────────────────────────────────────
    ax.plot(
        [0, fig_width],
        [y_cursor - 0.02, y_cursor - 0.02],
        color=theme["accent"],
        linewidth=1.5,
    )

    plt.tight_layout(pad=0)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, format="png", bbox_inches="tight", dpi=144, facecolor=theme["bg"])
    plt.close(fig)
    return output_path


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Convert a markdown table to a publication-ready PNG image."
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--table-file", help="Path to a file containing the markdown table")
    src.add_argument("--table", help="Markdown table as a string (use quotes)")
    parser.add_argument("--title", default="", help="Optional title displayed above the table")
    parser.add_argument("--theme", choices=list(THEMES.keys()), default="light", help="Color theme")
    parser.add_argument("--font-size", type=int, default=12)
    parser.add_argument("--output", "-o", default="table.png", help="Output PNG path")
    args = parser.parse_args()

    # Read table content
    if args.table_file:
        table_text = Path(args.table_file).read_text()
    elif args.table:
        table_text = args.table
    else:
        # Read from stdin
        print("Reading markdown table from stdin (paste table, then Ctrl+D):", file=sys.stderr)
        table_text = sys.stdin.read()

    if not table_text.strip():
        print("ERROR: No table content provided.", file=sys.stderr)
        sys.exit(1)

    headers, rows = parse_markdown_table(table_text)
    output = render_table_png(
        headers,
        rows,
        output_path=args.output,
        title=args.title,
        theme_name=args.theme,
        font_size=args.font_size,
    )
    print(f"✓ Table PNG saved: {output}")
    result = {"success": True, "output": output, "rows": len(rows), "cols": len(headers)}
    print(json.dumps(result))


if __name__ == "__main__":
    main()

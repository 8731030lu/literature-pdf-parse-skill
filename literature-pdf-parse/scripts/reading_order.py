#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic multi-column reading-order reconstruction (pure standard library).

Input
-----
A JSON array of text blocks, one object per block:

    [
      {"page": 1, "x0": 72.0, "y0": 100.5, "x1": 245.0, "y1": 112.3,
       "text": "first line", "font": "Times-Roman", "size": 10.0}
    ]

Coordinate convention (IMPORTANT)
----------------------------------
Default is TOP-ORIGIN: y increases downward, so `y0` is the TOP of the block and
`y1` is the BOTTOM. If your extractor uses bottom-origin (PDF native, y increases
upward, e.g. `pdftotext -bbox`), pass `--y-origin bottom`. If in doubt, render one
page and compare a known top line's y value with a known bottom line's y value:
top < bottom means top-origin.

Output
------
The same blocks as a JSON array, each annotated with:

    page, column (0-based), kind, order

where `kind` is one of body | header | footer | page_number | spanning | no_coord.
`near_margin: true` merely records that the block sits in the top/bottom margin band;
header and footer are only assigned when that text also repeats across pages.
Blocks that lack usable coordinates are emitted last with `kind: "no_coord"`.

This script only does GEOMETRIC sorting. It makes no semantic judgements (e.g. it
does not confirm a cross-page paragraph continuation). Verify its output against
the rendered page; do not treat it as ground truth.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter

PAGE_NUMBER_RE = re.compile(r"^(?:\d{1,4}|第\s*\d+\s*页|\d+\s*/\s*\d+)$")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _norm(text):
    return re.sub(r"\s+", "", str(text)).lower()


def estimate_page_width(blocks):
    xs0 = [b["x0"] for b in blocks if b["x0"] is not None]
    xs1 = [b["x1"] for b in blocks if b["x1"] is not None]
    if not xs0 or not xs1:
        return 1.0
    return max(max(xs1) - min(xs0), 1.0)


def column_bands(blocks, page_width, max_span_ratio=0.6, min_gap_ratio=0.015):
    """Return the page's column bands as a list of (x_left, x_right).

    Two rules keep this honest on real paper layouts:

    * Full-width blocks (running headers, page-number rules, spanning figures) do
      not vote. A single full-width interval would merge every column run into
      one and hide the gutter, collapsing a two-column page to one column.
    * Bands are the merged text runs themselves, not the regions between them.
      Returning gutter bands as extra "columns" shifts every column index and
      makes ordinary column text look like it spans columns.
    """
    max_span = max_span_ratio * page_width
    intervals = sorted((b["x0"], b["x1"]) for b in blocks
                       if b["x0"] is not None and b["x1"] is not None
                       and (b["x1"] - b["x0"]) <= max_span)
    if not intervals:
        return []
    merged = []
    for s, e in intervals:
        if merged and s <= merged[-1][1] + 1e-6:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append([s, e])
    min_gap = max(min_gap_ratio * page_width, 4.0)
    bands = [list(merged[0])]
    for lo, hi in merged[1:]:
        if lo - bands[-1][1] >= min_gap:
            bands.append([lo, hi])
        else:
            bands[-1][1] = max(bands[-1][1], hi)
    return [tuple(b) for b in bands]


def column_index(x0, x1, col_bounds):
    """Return the column index for a block, or -1 if it cannot be assigned."""
    cx = (x0 + x1) / 2.0
    for i, (lo, hi) in enumerate(col_bounds):
        if lo <= cx <= hi:
            return i
    return -1


def spans_columns(x0, x1, col_bounds, tol=1.0):
    """True when a block overlaps more than one column band by more than `tol`.

    Touching a band boundary is not spanning: without the tolerance, ordinary
    column text whose edge sits on the boundary is misreported as a spanning
    figure.
    """
    if len(col_bounds) <= 1:
        return False
    hits = 0
    for lo, hi in col_bounds:
        if x0 < hi - tol and x1 > lo + tol:
            hits += 1
    return hits >= 2


def visual_edges(b, y_origin):
    """Return (visual_top_y, visual_bottom_y) regardless of origin convention."""
    a, c = b["y0"], b["y1"]
    if a is None or c is None:
        return None, None
    lo, hi = min(a, c), max(a, c)
    if y_origin == "top":
        return lo, hi  # smaller y = higher on page
    return hi, lo      # larger y = higher on page


def sort_key(b, y_origin):
    vt = b["_vtop"]
    x = b["x0"] if b["x0"] is not None else 0.0
    if y_origin == "bottom":
        return (-(vt if vt is not None else 0.0), x)
    return (vt if vt is not None else 0.0, x)


def main():
    ap = argparse.ArgumentParser(description="Deterministic multi-column reading-order reconstruction")
    ap.add_argument("--input", "-i", default=None, help="input JSON file (default: stdin)")
    ap.add_argument("--output", "-o", default=None, help="output JSON file (default: stdout)")
    ap.add_argument("--y-origin", choices=["top", "bottom"], default="top",
                    help="coordinate convention: top-origin (default) or bottom-origin")
    ap.add_argument("--margin-ratio", type=float, default=0.08,
                    help="top/bottom margin band as fraction of page height (default 0.08)")
    ap.add_argument("--page-height", type=float, default=None,
                    help="true page height in pt when the extractor knows it. Without it the text "
                         "bounding box is used, which shrinks the margin band on sparse pages "
                         "(a text-only page then keeps all blocks as body, flagged near_margin)")
    args = ap.parse_args()

    try:
        if args.input:
            with open(args.input, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        else:
            data = json.load(sys.stdin)
    except FileNotFoundError:
        sys.stderr.write(f"input file not found: {args.input}\n")
        return 2
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"input is not valid JSON: {exc}\n")
        return 2
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write(f"cannot read input: {exc}\n")
        return 2

    if not isinstance(data, list):
        sys.stderr.write("input must be a JSON array of blocks\n")
        return 2

    for b in data:
        b["x0"] = _num(b.get("x0"))
        b["x1"] = _num(b.get("x1"))
        b["y0"] = _num(b.get("y0"))
        b["y1"] = _num(b.get("y1"))
        b["text"] = str(b.get("text", ""))

    text_freq = Counter()
    for b in data:
        if b["text"].strip():
            text_freq[_norm(b["text"])] += 1

    pages = {}
    for b in data:
        pages.setdefault(b.get("page", 0), []).append(b)
    page_ids = sorted(pages.keys())

    out = []
    for pid in page_ids:
        blocks = [b for b in pages[pid] if b["x0"] is not None and b["x1"] is not None]
        no_coord = [b for b in pages[pid] if b["x0"] is None or b["x1"] is None]

        if not blocks:
            for b in no_coord:
                item = {k: v for k, v in b.items() if not k.startswith("_")}
                item["kind"] = "no_coord"
                item["column"] = None
                item["order"] = 0
                out.append(item)
            continue

        for b in blocks:
            b["_vtop"], b["_vbottom"] = visual_edges(b, args.y_origin)

        page_width = estimate_page_width(blocks)
        all_y = [v for b in blocks for v in (b["y0"], b["y1"]) if v is not None]
        if args.page_height:
            page_height = float(args.page_height)
            page_lo = min(all_y) if all_y else 0.0
            page_hi = page_lo + page_height
            page_top = 0.0 if args.y_origin == "top" else page_height
            page_bottom = page_height if args.y_origin == "top" else 0.0
        elif all_y:
            page_lo, page_hi = min(all_y), max(all_y)
            page_height = max(page_hi - page_lo, 1.0)
            page_top, page_bottom = (page_lo, page_hi) if args.y_origin == "top" else (page_hi, page_lo)
        else:
            page_lo, page_hi, page_height = 0.0, 1.0, 1.0
            page_top, page_bottom = 0.0, 1.0

        col_bounds = column_bands(blocks, page_width)
        if not col_bounds:
            # Every block on this page is full width: a single-column page.
            xs = [b["x0"] for b in blocks] + [b["x1"] for b in blocks]
            col_bounds = [(min(xs), max(xs))]

        margin = args.margin_ratio * page_height

        for b in blocks:
            n = _norm(b["text"])
            repeated = text_freq[n] >= 2 and n != ""
            vt = b["_vtop"]
            vb = b["_vbottom"]
            is_page_number = bool(PAGE_NUMBER_RE.match(str(b["text"]).strip()))

            near_top = vt is not None and abs(vt - page_top) < margin
            near_bottom = vb is not None and abs(vb - page_bottom) < margin

            if is_page_number:
                b["kind"] = "page_number"
            elif repeated and (near_top or near_bottom):
                b["kind"] = "header" if near_top else "footer"
            else:
                b["kind"] = "body"
            # Keep the geometric hint instead of reclassifying. A single block
            # near an edge is far more often body text on a sparse page than a
            # margin note; repetition across pages is what makes header/footer
            # trustworthy.
            b["near_margin"] = bool(near_top or near_bottom)

            if spans_columns(b["x0"], b["x1"], col_bounds) and b["kind"] == "body":
                b["kind"] = "spanning"

            b["column"] = column_index(b["x0"], b["x1"], col_bounds)

        body = [b for b in blocks if b["kind"] in ("body", "spanning")]
        non_body = [b for b in blocks if b["kind"] not in ("body", "spanning")]

        def body_key(b):
            col = b["column"] if b["column"] is not None and b["column"] >= 0 else 0
            return (col, sort_key(b, args.y_origin))

        body.sort(key=body_key)

        order = 0
        for b in body + non_body:
            order += 1
            item = {k: v for k, v in b.items() if not k.startswith("_")}
            item["order"] = order
            out.append(item)

        for b in no_coord:
            item = {k: v for k, v in b.items() if not k.startswith("_")}
            item["kind"] = "no_coord"
            item["column"] = None
            item["order"] = 0
            out.append(item)

    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text + "\n")
        except OSError as exc:
            # Degrade instead of dying: the caller still gets a usable result.
            sys.stderr.write(f"cannot write {args.output}: {exc}; writing to stdout instead\n")
            sys.stdout.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

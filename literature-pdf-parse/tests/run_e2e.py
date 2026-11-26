#!/usr/bin/env python3
"""End-to-end check: PDF -> pdftotext -bbox -> blocks -> reading_order.py -> ground truth.

This exercises the real pipeline the Skill describes, not just the geometry rules:
the PDF is parsed by poppler, word boxes are grouped into lines, the line blocks are
reordered by scripts/reading_order.py, and the resulting text sequence is compared
with tests/expected_order.json.

Run:
  python tests/run_e2e.py --pdf tests/synthetic_two_column.pdf --pdftotext pdftotext

Exit code 0 = all pages matched, 1 = mismatch or pipeline error.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "reading_order.py")
LINE_TOLERANCE = 3.0  # pt; words whose vertical centres differ by less sit on one line
WORD_GAP = 8.0        # pt; a wider horizontal gap starts a new block on the same baseline


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def parse_bbox(xml_path):
    """Return {page_no: [blocks]} with one block per visual line."""
    tree = ET.parse(xml_path)
    pages = {}
    page_no = 0
    for page in tree.iter():
        if local_name(page.tag) != "page":
            continue
        page_no += 1
        words = []
        for w in page.iter():
            if local_name(w.tag) != "word":
                continue
            words.append({
                "x0": float(w.get("xMin")), "y0": float(w.get("yMin")),
                "x1": float(w.get("xMax")), "y1": float(w.get("yMax")),
                "text": (w.text or ""),
            })
        if not words:
            continue
        words.sort(key=lambda w: ((w["y0"] + w["y1"]) / 2.0, w["x0"]))

        lines = []
        for w in words:
            yc = (w["y0"] + w["y1"]) / 2.0
            if lines and abs(yc - lines[-1]["yc"]) <= LINE_TOLERANCE:
                ln = lines[-1]
                ln["words"].append(w)
                ln["yc"] = (ln["yc"] * (len(ln["words"]) - 1) + yc) / len(ln["words"])
            else:
                lines.append({"yc": yc, "words": [w]})

        blocks = []
        for ln in lines:
            ws = sorted(ln["words"], key=lambda w: w["x0"])
            # Split on wide horizontal gaps: two columns sharing a baseline must not
            # become one line, or the text reads left-right across the gutter.
            runs = [[ws[0]]]
            for prev, cur in zip(ws, ws[1:]):
                if cur["x0"] - prev["x1"] > WORD_GAP:
                    runs.append([cur])
                else:
                    runs[-1].append(cur)
            for run in runs:
                blocks.append({
                    "page": page_no,
                    "x0": min(w["x0"] for w in run),
                    "y0": min(w["y0"] for w in run),
                    "x1": max(w["x1"] for w in run),
                    "y1": max(w["y1"] for w in run),
                    "text": " ".join(w["text"] for w in run),
                })
        blocks.sort(key=lambda b: b["y0"])
        pages[page_no] = blocks
    return pages


def norm(s):
    return " ".join(s.split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=os.path.join(HERE, "synthetic_two_column.pdf"))
    ap.add_argument("--pdftotext", default="pdftotext")
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    if not os.path.exists(args.pdf):
        sys.stderr.write("missing PDF: %s (run make_synthetic_pdf.py first)\n" % args.pdf)
        return 1

    tmp = tempfile.mkdtemp(prefix="e2e_")
    xml_path = os.path.join(tmp, "bbox.xml")

    proc = subprocess.run([args.pdftotext, "-bbox", args.pdf, xml_path],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write("pdftotext failed: %s\n%s\n" % (proc.returncode, proc.stderr))
        return 1

    pages = parse_bbox(xml_path)
    blocks = [b for p in sorted(pages) for b in pages[p]]

    blocks_path = os.path.join(tmp, "blocks.json")
    ordered_path = os.path.join(tmp, "ordered.json")
    with open(blocks_path, "w", encoding="utf-8") as f:
        json.dump(blocks, f, ensure_ascii=False, indent=1)

    proc = subprocess.run([args.python, SCRIPT, "-i", blocks_path, "-o", ordered_path,
                           "--y-origin", "top"], capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write("reading_order.py failed: %s\n%s\n" % (proc.returncode, proc.stderr))
        return 1

    with open(ordered_path, encoding="utf-8") as f:
        ordered = json.load(f)
    with open(os.path.join(HERE, "expected_order.json"), encoding="utf-8") as f:
        expected = json.load(f)

    got = [(r["page"], norm(r["text"])) for r in ordered]
    want = [(r["page"], norm(r["text"])) for r in expected]

    ok = got == want
    print("pages=%d  blocks=%d  expected=%d" % (len(pages), len(blocks), len(want)))
    if ok:
        print("PASS: reading order matches ground truth")
        for i, (p, t) in enumerate(got, 1):
            print("  %2d p%d %s" % (i, p, t))
        return 0

    print("FAIL: order mismatch")
    for i in range(max(len(got), len(want))):
        g = got[i] if i < len(got) else None
        w = want[i] if i < len(want) else None
        flag = "  " if g == w else "!!"
        print("%s %2d want=%s  got=%s" % (flag, i + 1, w, g))
    return 1


if __name__ == "__main__":
    sys.exit(main())

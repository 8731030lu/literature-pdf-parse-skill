#!/usr/bin/env python3
"""Generate a synthetic two-column PDF used for end-to-end testing.

The document is fully synthetic and deliberately small: two A4 pages, one running
header repeated on both pages, a left column and a right column of short lines,
and a page number at the bottom right. It contains no real scientific content and
is not a formal test case.

Run:  python tests/make_synthetic_pdf.py --out tests/synthetic_two_column.pdf
Writes the PDF and tests/expected_order.json (the ground-truth reading order).
"""
import argparse
import json
import os

A4 = (595, 842)
HEADER = "Synthetic Two-Column Test Document"

# (x, y_from_top, text) per page. Left column starts at x=60, right column at x=320.
LINES = {
    1: [
        (60, 120, "L1 left column first line alpha beta"),
        (60, 134, "L2 left column second line gamma"),
        (60, 148, "L3 left column third line delta epsilon"),
        (60, 200, "L4 left column next paragraph zeta"),
        (60, 214, "L5 left column next paragraph eta"),
        (320, 120, "R1 right column first line theta"),
        (320, 134, "R2 right column second line iota"),
        (320, 200, "R3 right column next paragraph kappa"),
    ],
    2: [
        (60, 120, "L1 page two left column lambda"),
        (60, 134, "L2 page two left column mu"),
        (320, 120, "R1 page two right column nu"),
    ],
}
PAGE_NUMBER_X = 500
PAGE_NUMBER_Y = 800


def esc(s):
    return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def content_stream(page_no):
    out = []

    def text(x, y_top, s, size):
        out.append("BT /F1 %d Tf 1 0 0 1 %.2f %.2f Tm (%s) Tj ET"
                   % (size, x, A4[1] - y_top, esc(s)))

    text(60, 30, HEADER, 10)
    for x, y, s in LINES[page_no]:
        text(x, y, s, 9)
    text(PAGE_NUMBER_X, PAGE_NUMBER_Y, str(page_no), 9)
    return "\n".join(out)


def build_pdf():
    objs = {}
    objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[2] = b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>"
    for page_no, obj_no, contents_no in ((1, 3, 6), (2, 4, 7)):
        objs[obj_no] = ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] "
                        "/Resources << /Font << /F1 5 0 R >> >> /Contents %d 0 R >>"
                        % (A4[0], A4[1], contents_no)).encode()
    objs[5] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    for page_no, obj_no in ((1, 6), (2, 7)):
        raw = content_stream(page_no).encode("latin-1")
        objs[obj_no] = (b"<< /Length %d >>\nstream\n" % len(raw)) + raw + b"\nendstream"

    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for i in range(1, 8):
        offsets[i] = len(buf)
        buf += b"%d 0 obj\n" % i + objs[i] + b"\nendobj\n"
    xref_pos = len(buf)
    buf += b"xref\n0 8\n0000000000 65535 f \n"
    for i in range(1, 8):
        buf += b"%010d 00000 n \n" % offsets[i]
    buf += (b"trailer\n<< /Size 8 /Root 1 0 R >>\nstartxref\n"
            + str(xref_pos).encode() + b"\n%%EOF\n")
    return bytes(buf)


def expected_order():
    """Ground truth: left column top-to-bottom, then right column, then header, then page number."""
    out = []
    for page_no in sorted(LINES):
        left = [t for x, y, t in sorted(LINES[page_no], key=lambda r: (r[1], r[0])) if x < 300]
        right = [t for x, y, t in sorted(LINES[page_no], key=lambda r: (r[1], r[0])) if x >= 300]
        for t in left + right + [HEADER, str(page_no)]:
            out.append({"page": page_no, "text": t})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "synthetic_two_column.pdf"))
    args = ap.parse_args()
    with open(args.out, "wb") as f:
        f.write(build_pdf())
    exp_path = os.path.join(os.path.dirname(args.out), "expected_order.json")
    with open(exp_path, "w", encoding="utf-8") as f:
        json.dump(expected_order(), f, ensure_ascii=False, indent=1)
    print("wrote %s (%d bytes) and %s" % (args.out, os.path.getsize(args.out), exp_path))


if __name__ == "__main__":
    main()

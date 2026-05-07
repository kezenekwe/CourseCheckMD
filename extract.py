"""
extract.py — Extract premed course requirements from the AAMC MSAR PDF.

Reads the PDF, classifies the Yes/No/Case-by-Case icon images by pixel color,
and writes data.json next to this script.

Usage:
    pip install pdfplumber pymupdf pillow numpy
    python3 extract.py
    python3 extract.py path/to/other.pdf   # override default PDF path
"""

import sys, re, json, collections
import pdfplumber
import fitz  # PyMuPDF
import numpy as np

PDF_PATH = "MSAR002 - MSAR Premed Course Requirements-1.pdf"
OUT_PATH = "data.json"
SCALE    = 2  # render resolution multiplier (higher = slower but more accurate)

# X-ranges (in PDF points) for the five icon columns.
# Derived from the header row cell bounding boxes; consistent across all pages.
ICON_COLS = {
    "lab":               (525.9, 554.4),
    "pass_fail":         (554.4, 608.4),
    "ap_credit":         (608.4, 662.4),
    "online":            (662.4, 716.4),
    "community_college": (716.4, 770.0),
}


def classify_icon(arr, x0, top, x1, bottom):
    """
    Sample an icon cell region in a rendered page array and classify it.

    Color rules (tuned on AAMC 2026 icon palette):
      Green  (Yes)          — G channel dominates R and B
      Red    (No)           — R channel dominates G and B
      Yellow/cream (CbC)    — R ≈ G, both notably higher than B
      Otherwise             — None (blank cell)

    Args:
        arr:            numpy uint8 array (H x W x 3) of the rendered page
        x0, top, x1, bottom: pdfplumber "top-from-top" coordinates
    """
    xi0, yi0 = int(x0 * SCALE), int(top * SCALE)
    xi1, yi1 = int(x1 * SCALE), int(bottom * SCALE)
    xi0, yi0 = max(0, xi0), max(0, yi0)
    xi1, yi1 = min(arr.shape[1], xi1), min(arr.shape[0], yi1)
    region = arr[yi0:yi1, xi0:xi1]
    if region.size == 0:
        return "None"

    R = region[:, :, 0].astype(int)
    G = region[:, :, 1].astype(int)
    B = region[:, :, 2].astype(int)

    # Exclude near-white background pixels
    colorful = ~((R > 230) & (G > 230) & (B > 230))

    green  = colorful & ((G - R) > 10) & ((G - B) > 10)
    red    = colorful & ((R - G) > 15) & ((R - B) > 15)
    # Yellow/cream: R and G both well above B, R ≈ G
    yellow = colorful & ((R - B) > 25) & ((G - B) > 15) & ((G - R) < 20)

    g, r, y = int(green.sum()), int(red.sum()), int(yellow.sum())
    if max(g, r, y) < 3:
        return "None"
    if g >= r and g >= y:
        return "Yes"
    if r > g and r >= y:
        return "No"
    return "CbC"


def find_icon_group(img_lookup_tops, row_top, tolerance=3.0):
    """Return the closest image-group top within tolerance, or None."""
    if not img_lookup_tops:
        return None
    best = min(img_lookup_tops, key=lambda t: abs(t - row_top))
    return best if abs(best - row_top) <= tolerance else None


def clean(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def extract(pdf_path):
    doc_fitz = fitz.open(pdf_path)
    records  = []
    state_carry  = ""
    school_carry = ""

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages):
            print(f"\r  page {page_num + 1}/{total}", end="", flush=True)

            tables = page.find_tables()
            if not tables:
                continue
            tbl  = tables[0]
            rows = tbl.extract()
            if not rows or len(rows) < 2:
                continue

            # Build icon-image lookup: top_value → {col_name: (x0, top, x1, bottom)}
            img_lookup: dict[float, dict] = {}
            for img in page.images:
                cx = (img["x0"] + img["x1"]) / 2
                for col_name, (cx0, cx1) in ICON_COLS.items():
                    if cx0 <= cx <= cx1:
                        key = round(img["top"], 1)
                        img_lookup.setdefault(key, {})[col_name] = (
                            img["x0"], img["top"], img["x1"], img["bottom"]
                        )
                        break

            # Render page once for all icon sampling on this page
            pix = doc_fitz[page_num].get_pixmap(matrix=fitz.Matrix(SCALE, SCALE))
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, 3
            )

            current_row = None
            for cells, trow in zip(rows[1:], tbl.rows[1:]):
                row_top = trow.bbox[1]
                state   = clean(cells[0])
                school  = clean(cells[1])
                course  = clean(cells[2])
                cls     = clean(cells[3])
                req     = clean(cells[4])
                addinfo = clean(cells[5])
                credits = clean(cells[6])

                # Continuation row: no course/status text — append icon-column notes
                if not course and not req:
                    if current_row is not None:
                        names = ["lab", "pass_fail", "ap_credit", "online", "community_college"]
                        for ci, col in enumerate(names, 7):
                            txt = clean(cells[ci]) if len(cells) > ci else ""
                            if txt:
                                current_row[col + "_notes"] += " " + txt
                    continue

                # Primary data row
                if state:  state_carry  = state
                if school: school_carry = school

                # Classify icons
                match_top = find_icon_group(list(img_lookup.keys()), row_top)
                icons = {}
                for col_name in ICON_COLS:
                    if match_top is not None and col_name in img_lookup[match_top]:
                        icons[col_name] = classify_icon(arr, *img_lookup[match_top][col_name])
                    else:
                        icons[col_name] = "None"

                names = ["lab", "pass_fail", "ap_credit", "online", "community_college"]
                icon_notes = {
                    col + "_notes": clean(cells[ci]) if len(cells) > ci else ""
                    for ci, col in enumerate(names, 7)
                }

                current_row = {
                    "state":                state_carry,
                    "medical_school":       school_carry,
                    "course":               course,
                    "class":                cls,
                    "required_recommended": req,
                    "additional_info":      addinfo,
                    "credit_hours":         credits,
                    **icons,
                    **icon_notes,
                }
                records.append(current_row)

    print()  # newline after progress
    return records


def summarize(records):
    schools = len({r["medical_school"] for r in records})
    states  = sorted({r["state"] for r in records})
    icon_counts = {
        col: dict(collections.Counter(r[col] for r in records))
        for col in ICON_COLS
    }
    print(f"Records : {len(records)}")
    print(f"Schools : {schools}")
    print(f"States  : {states}")
    print("Icons   :")
    for col, cnt in icon_counts.items():
        print(f"  {col}: {cnt}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else PDF_PATH
    print(f"Extracting from: {path}")
    records = extract(path)
    summarize(records)
    with open(OUT_PATH, "w") as f:
        json.dump(records, f, indent=2)
    print(f"\nWrote {len(records)} records → {OUT_PATH}")

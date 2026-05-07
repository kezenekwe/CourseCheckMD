# MSAR Premed Course Requirements — Web App

An interactive browser tool for exploring the 2026 AAMC Medical School Admission Requirements (MSAR) premed course prerequisite data. Filter by state, school, course type, and admissions policies without scrolling a 219-page PDF.

---

## Project Files

| File | Purpose |
|------|---------|
| `index.html` | The web app — open in a browser or serve locally |
| `data.json` | Structured course data extracted from the PDF (1,146 records) |
| `extract.py` | Python script that produced `data.json` from the PDF |
| `MSAR002 - MSAR Premed Course Requirements-1.pdf` | Source PDF (AAMC, 2026) |

---

## Running the App

The app requires a local HTTP server because the browser won't load `data.json` via `file://` directly.

```bash
# Python 3 (built-in)
python3 -m http.server 8787

# Then open:
# http://localhost:8787
```

That's it — no build step, no dependencies, no framework.

---

## How the App Works

### Filters

Ten dropdowns sit at the top of the page. Any combination can be active at once.

| Dropdown | Behaviour |
|----------|-----------|
| **State / Province** | Always lists all 49 state/province codes. Selecting a state narrows the School dropdown. |
| **Medical School** | Lists schools in the selected state (or all schools if no state is chosen). |
| **Course** | Lists courses available after State + School filters are applied. |
| **Subject Area (Class)** | BIOL · CHEM · ENGL · MATH · PHYS · BESS — further narrows results. |
| **Required / Recommended** | Show required-only, recommended-only, or both. |
| **Lab Required?** | Yes / No |
| **Pass/Fail Accepted?** | Yes / No / Case-by-Case |
| **AP Credit Accepted?** | Yes / No / Case-by-Case |
| **Online Course OK?** | Yes / No / Case-by-Case |
| **Community College OK?** | Yes / No / Case-by-Case |

Changing any dropdown immediately re-filters and re-renders the table. The **Clear All Filters** button resets everything.

### Icon Legend

Each of the five policy columns (Lab?, Pass/Fail, AP Credit, Online, Community College) shows a coloured badge:

| Badge | Meaning |
|-------|---------|
| ✓ green | Yes / Accepted |
| ✗ red | No / Not Accepted |
| ● yellow | Case-by-Case |
| — grey | Not specified in source data |

**Hover** any badge to read the school's specific policy note (e.g. "AP credits accepted with proper denotation on the undergraduate transcript").

### Cascading Dropdowns

State → School → Course cascade: selecting a state trims the school list; selecting a school trims the course list. This prevents invalid filter combinations and reduces noise.

---

## Data Schema (`data.json`)

Each record is one course requirement row from the MSAR PDF.

```jsonc
{
  "state":                "AL",
  "medical_school":       "Frederick P. Whiddon College of Medicine ...",
  "course":               "Biology",
  "class":                "BIOL",
  "required_recommended": "Required",
  "additional_info":      "General Biology — ...",
  "credit_hours":         "8",

  // Icon column values: "Yes" | "No" | "CbC" | "None"
  "lab":                  "Yes",
  "pass_fail":            "CbC",
  "ap_credit":            "Yes",
  "online":               "CbC",
  "community_college":    "Yes",

  // Policy notes from the school (may be empty string)
  "lab_notes":                "",
  "pass_fail_notes":          "We will accept Pass/Fail grading for ...",
  "ap_credit_notes":          "U.S. Advanced Placement credits will be ...",
  "online_notes":             "Labs should be completed in-person.",
  "community_college_notes":  ""
}
```

**Record counts (2026 extract):** 1,146 rows · 166 schools · 49 states/provinces

---

## Re-extracting the Data

Run `extract.py` whenever the source PDF is updated (e.g. a new MSAR year).

### Install dependencies (one-time)

```bash
pip install pdfplumber pymupdf pillow numpy
```

### Run

```bash
# Uses the PDF in the same directory
python3 extract.py

# Or pass a path explicitly
python3 extract.py "/path/to/new-msar.pdf"
```

Output is written to `data.json` in the current directory.

### How extraction works

The AAMC PDF stores the five policy columns (Lab?, Pass/Fail, etc.) as embedded PNG icons rather than text — pdfplumber cannot read them as strings. `extract.py` works around this in three steps:

1. **Text extraction** — `pdfplumber` reads every table cell. Columns 0–6 (State through Credit Hours) come out as clean text. Icon columns come out empty.

2. **Image detection** — `pdfplumber`'s image list gives the position (`top`, `bottom`, `x0`, `x1`) of every embedded PNG on each page. Images whose x-centre falls in one of the five icon column x-ranges are collected into a per-row lookup.

3. **Colour classification** — each page is rendered to a pixel array via `PyMuPDF`. For each icon image, the corresponding pixel region is sampled and classified by dominant hue:
   - **Green** (G − R > 10 and G − B > 10) → `"Yes"`
   - **Red** (R − G > 15 and R − B > 15) → `"No"`
   - **Yellow/cream** (R − B > 25 and G − B > 15 and G − R < 20) → `"CbC"`
   - Insufficient colour signal → `"None"`

   Row-to-image matching uses fuzzy position lookup (±3 pt tolerance) to handle sub-pixel rounding differences between pdfplumber's table rows and its image coordinate list.

---

## Data Source & Copyright

Data is sourced from the **AAMC Medical School Admission Requirements™ (MSAR®) Report for Applicants and Advisors, 2026 edition**, provided directly by individual medical schools.

> © 2026 Association of American Medical Colleges. The following reports and data may be reproduced and distributed with attribution for individual, educational, and noncommercial purposes only.

This tool is for individual, educational, and noncommercial use only, consistent with the AAMC licence terms above.

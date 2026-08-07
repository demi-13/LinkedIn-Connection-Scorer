"""
score_leads.py -- Fast LinkedIn connections CSV scorer for [YOUR_COMPANY].
No API calls. Runs against all 2,000 rows in seconds.

Usage:
    python score_leads.py your_connections_file.csv
"""

import csv
import sys
import io

# Ensure Unicode names print safely on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from pathlib import Path

# ---------------------------------------------------------------------------
# Scoring keyword tables
# ---------------------------------------------------------------------------

INDUSTRY_HIGH = [
    "medtech", "medical device", "medical devices", "biotech", "biomedical",
    "life science", "life sciences", "fertility", "ivf", "reproductive",
    "pharmaceutical", "pharma", "implant", "surgical", "diagnostic",
    "diagnostics", "pfas", "per- and polyfluoroalkyl", "polyfluoroalkyl",
    "forever chemicals", "greentech", "green tech", "nanotech",
    "nanotechnology",
]

INDUSTRY_MED = [
    "manufacturing", "plastics", "polymer", "polymers", "materials",
    "aerospace", "automotive", "defense", "consumer goods", "packaging",
    "industrial", "chemical", "chemicals", "lab", "laboratory",
    "r&d", "research", "adhesive", "adhesives", "coating", "coatings",
    "composite", "composites", "elastomer", "elastomers", "laminate",
    "laminates", "film", "films", "sustainable materials", "compostable",
    "oem", "contract manufacturer", "contract manufacturing",
]

TITLE_HIGH = [
    "engineer", "scientist", "researcher", "director of engineering",
    "vp engineering", "vp of engineering", "materials", "r&d", "formulation",
    "quality", "regulatory", "product development", "lab manager",
    "principal", "technical lead", "chief scientist", "chief technology",
]

TITLE_MED = [
    "manager", "procurement", "supply chain", "operations",
    "process owner", "ops lead",
]

# Exec titles: worth +3 (outranks individual-contributor engineers/scientists)
# but only when company or title carries an industry signal.
# A CEO/CTO/co-founder at a relevant company is a decision-maker worth pursuing.
# A CEO at a totally unrelated company is noise.
# Uses word-boundary matching to avoid "cto" matching "doctor" etc.
TITLE_EXEC = [
    "ceo", "cto", "coo", "cso", "director", "vp", "vice president",
    "founder", "owner", "co-founder", "cofounder",
]
TITLE_EXEC_WEIGHT = 3

TITLE_NEG = [
    "sales", "marketing", "recruiter", "recruiting", "hr ", " hr",
    "human resources", "talent", "social media", "content creator",
    "content writer", "accountant", "finance", "financial advisor",
    "bookkeeper",
]

# -3 penalty if company name signals a staffing / recruiting firm
COMPANY_NEG = [
    "staffing", "recruiting", "recruiter", "talent", "workforce",
    "headhunter", "placement", "search firm", "human resources",
    "hr solutions", "manpower", "outsourcing",
]

# Hard cap at 0 if title signals a recruiter role (industry keywords in their title are noise)
TITLE_RECRUITER_NEG = [
    "recruiter", "recruiting", "recruitment", "talent acquisition", "talent partner",
    "sourcer", "sourcing", "staffing", "people operations", "people partner",
    "executive search",
]

# Hard cap at 0 for specific companies known to be staffing/recruiting firms
# despite a generic-sounding name and job titles that don't say so (the
# staffing signal only shows up in LinkedIn's company "About" text, which
# isn't in the CSV export, so keyword matching alone can't catch these).
# Match on exact company name (case-insensitive), not substring, to avoid
# accidentally excluding unrelated companies with similar words.
MANUAL_EXCLUDE_COMPANIES = [
    "spi of chicago, inc.",  # talent acquisition franchisor -- confirmed by [YOUR_ALIAS]
]

# Hard cap at 1 if title contains any of these (student / trainee signals)
STUDENT_KEYWORDS = [
    "undergraduate", "grad student", "phd student", "ms student",
    "mba student", "intern", "trainee",
]

import re


def _contains(text: str, keywords: list[str]) -> list[str]:
    """Return which keywords appear in text (case-insensitive, substring)."""
    lower = text.lower()
    return [kw for kw in keywords if kw in lower]


def _contains_word(text: str, keywords: list[str]) -> list[str]:
    """Return which keywords appear as whole words (avoids 'cto' matching 'doctor')."""
    lower = text.lower()
    return [kw for kw in keywords if re.search(r'\b' + re.escape(kw) + r'\b', lower)]


def _is_student(position: str) -> bool:
    pos = position.lower()
    if any(kw in pos for kw in STUDENT_KEYWORDS):
        return True
    if "fellow" in pos and ("student" in pos or "graduate" in pos):
        return True
    return False


def _has_industry_signal(company: str, position: str) -> bool:
    """True if company OR title carries an industry signal (e.g. a cofounder
    whose title mentions PFAS/materials even if the company name doesn't)."""
    combined = f"{company} {position}".lower()
    return bool(_contains(combined, INDUSTRY_HIGH) or _contains(combined, INDUSTRY_MED))


def score_row(company: str, position: str) -> int:
    combined = f"{company} {position}".lower()
    score = 0

    # Industry signals (company + title combined)
    score += 2 * len(_contains(combined, INDUSTRY_HIGH))
    score += 1 * len(_contains(combined, INDUSTRY_MED))

    # Technical title signals
    score += 2 * len(_contains(position, TITLE_HIGH))

    # Non-exec business titles
    score += 1 * len(_contains(position, TITLE_MED))

    # Exec titles: +3 each (outranks engineer +2) if company OR title has an
    # industry signal. Uses word-boundary matching so "cto" doesn't match "doctor".
    if _has_industry_signal(company, position):
        score += TITLE_EXEC_WEIGHT * len(_contains_word(position, TITLE_EXEC))

    score -= 1 * len(_contains(position, TITLE_NEG))

    # Staffing/recruiting firm penalty
    score -= 3 * len(_contains(company, COMPANY_NEG))

    # Recruiter hard cap
    if _contains(position, TITLE_RECRUITER_NEG):
        score = min(score, 0)

    # Manually-known staffing firm hard cap (company name alone doesn't say so)
    if company.strip().lower() in MANUAL_EXCLUDE_COMPANIES:
        score = min(score, 0)

    # Student hard cap
    if _is_student(position):
        score = min(score, 1)

    return score


def tier(score: int) -> str:
    if score >= 4:
        return "Top"
    if score >= 2:
        return "Strong"
    if score == 1:
        return "Weak"
    return "Skip"


def run(input_path: str) -> None:
    src = Path(input_path)
    if not src.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    rows = []
    with open(src, newline="", encoding="utf-8-sig") as f:
        # LinkedIn CSVs have a notes block before the real header; skip to it
        lines = f.readlines()
        start = next((i for i, l in enumerate(lines) if l.startswith("First Name")), 0)
        import io
        reader = csv.DictReader(io.StringIO("".join(lines[start:])))
        fieldnames = reader.fieldnames or []
        for row in reader:
            company = row.get("Company", "") or ""
            position = row.get("Position", "") or ""
            s = score_row(company, position)
            row["score"] = s
            row["tier"] = tier(s)
            rows.append(row)

    rows.sort(key=lambda r: r["score"], reverse=True)

    out_path = src.parent / "scored_leads.csv"
    out_fields = list(fieldnames) + ["score", "tier"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    counts = {"Top": 0, "Strong": 0, "Weak": 0, "Skip": 0}
    for r in rows:
        counts[r["tier"]] += 1

    print(f"\n{'='*56}")
    print(f"  LinkedIn Lead Scorer -- [YOUR_COMPANY]")
    print(f"{'='*56}")
    print(f"  Total connections processed : {len(rows)}")
    print(f"  Top    (score >= 4)         : {counts['Top']}")
    print(f"  Strong (score 2-3)          : {counts['Strong']}")
    print(f"  Weak   (score 1)            : {counts['Weak']}")
    print(f"  Skip   (score <= 0)         : {counts['Skip']}")
    print(f"{'='*56}")
    print(f"\n  Output saved to: {out_path}\n")

    print("  TOP 10 PROSPECTS")
    print(f"  {'#':<4} {'Name':<28} {'Company':<28} {'Title':<30} {'Score'}")
    print(f"  {'-'*4} {'-'*28} {'-'*28} {'-'*30} {'-'*5}")
    for i, r in enumerate(rows[:10], 1):
        name = f"{r.get('First Name','')} {r.get('Last Name','')}".strip()
        company = (r.get("Company", "") or "")[:27]
        pos = (r.get("Position", "") or "")[:29]
        print(f"  {i:<4} {name:<28} {company:<28} {pos:<30} {r['score']}")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python score_leads.py <connections_file.csv>")
        sys.exit(1)
    run(sys.argv[1])

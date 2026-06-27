"""
score_leads.py -- Fast LinkedIn connections CSV scorer for [YOUR_COMPANY].
No API calls. Runs against all 2,000 rows in seconds.

Usage:
    python score_leads.py your_connections_file.csv
"""

import csv
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Scoring keyword tables
# ---------------------------------------------------------------------------

INDUSTRY_HIGH = [
    "medtech", "medical device", "medical devices", "biotech", "biomedical",
    "life science", "life sciences", "fertility", "ivf", "reproductive",
    "pharmaceutical", "pharma", "implant", "surgical", "diagnostic",
    "diagnostics",
]

INDUSTRY_MED = [
    "manufacturing", "plastics", "polymer", "polymers", "materials",
    "aerospace", "automotive", "defense", "consumer goods", "packaging",
    "industrial", "chemical", "chemicals", "lab", "laboratory",
    "r&d", "research",
]

TITLE_HIGH = [
    "engineer", "scientist", "researcher", "director of engineering",
    "vp engineering", "vp of engineering", "materials", "r&d", "formulation",
    "quality", "regulatory", "product development", "lab manager",
    "principal", "technical lead", "chief scientist", "chief technology",
]

TITLE_MED = [
    "manager", "founder", "owner", "co-founder", "cofounder", "president",
    "procurement", "supply chain", "operations", "cto", "coo",
]

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

# Hard cap at 1 if title contains any of these (student / trainee signals)
STUDENT_KEYWORDS = [
    "undergraduate", "grad student", "phd student", "ms student",
    "mba student", "intern", "trainee",
]

# Exec-only titles: score 0 from title unless at least one technical keyword
# is also present in the position
EXEC_ONLY = [
    "ceo", "president", "founder", "owner", "co-founder", "cofounder",
]

TECHNICAL_TITLE_SIGNALS = [
    "engineer", "scientist", "r&d", "materials", "formulation",
    "researcher", "technical", "product development", "quality",
    "regulatory", "procurement",
]


def _contains(text: str, keywords: list[str]) -> list[str]:
    """Return which keywords appear in text (case-insensitive)."""
    lower = text.lower()
    return [kw for kw in keywords if kw in lower]


def _is_student(position: str) -> bool:
    pos = position.lower()
    if any(kw in pos for kw in STUDENT_KEYWORDS):
        return True
    # "fellow" only counts as student if paired with student/graduate context
    if "fellow" in pos and ("student" in pos or "graduate" in pos):
        return True
    return False


def _exec_only_no_technical(position: str) -> bool:
    """True if position has exec keywords but zero technical signals."""
    pos = position.lower()
    has_exec = any(kw in pos for kw in EXEC_ONLY)
    has_technical = any(kw in pos for kw in TECHNICAL_TITLE_SIGNALS)
    return has_exec and not has_technical


def score_row(company: str, position: str) -> int:
    combined = f"{company} {position}".lower()
    score = 0

    # Industry signals
    score += 2 * len(_contains(combined, INDUSTRY_HIGH))
    score += 1 * len(_contains(combined, INDUSTRY_MED))

    # Title signals
    score += 2 * len(_contains(position, TITLE_HIGH))

    # Exec-only titles with no technical grounding contribute 0 from TITLE_MED
    if not _exec_only_no_technical(position):
        score += 1 * len(_contains(position, TITLE_MED))

    score -= 1 * len(_contains(position, TITLE_NEG))

    # Staffing/recruiting firm penalty
    score -= 3 * len(_contains(company, COMPANY_NEG))

    # Recruiter hard cap: industry keywords in a recruiter's title are noise, not signal
    if _contains(position, TITLE_RECRUITER_NEG):
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

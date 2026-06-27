"""
research_prospect.py -- Deep prospect research agent for [YOUR_COMPANY].
Uses Claude claude-sonnet-4-6 with web_search_20250305 tool.

Usage:
    python research_prospect.py                     # interactive prompts
    python research_prospect.py --row 3             # load row 3 from scored_leads.csv
"""

import csv
import sys
import argparse
from datetime import date
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ENV_PATH = Path(r"C:\Users\demio\outreach-emailer.env")
load_dotenv(ENV_PATH)

MODEL = "claude-sonnet-4-6"
BRIEFS_DIR = Path(__file__).parent / "briefs"
SCORED_CSV = Path(__file__).parent / "scored_leads.csv"

SYSTEM_PROMPT = """You are a research analyst for [YOUR_COMPANY], a fractional R&D consulting firm founded by [YOUR_NAME] ([YOUR_ALIAS]) ([YOUR_ALIAS]), a materials scientist and chemist.

[YOUR_COMPANY]'s core services:
- Material selection and testing
- Failure analysis
- Resin-based 3D printing / additive manufacturing
- Chemical formulation
- Regulatory / biocompatibility support for medical devices and fertility products

Your job is to research a specific prospect and produce a structured brief that helps [YOUR_ALIAS] decide whether and how to reach out.

Rules:
- No em dashes anywhere in the output. Use a colon or a period instead.
- Be factual and direct. [YOUR_ALIAS] is a scientist. No hype, no filler.
- If search results are thin, say so with Confidence: Low. Do not pad.
- Keep each section tight. The whole brief should be skimmable in under 60 seconds.
- Only list [YOUR_COMPANY] services that genuinely apply to what you found.
- Dates, product names, and company news should be specific when available.

Output format (use exactly this structure):

PROSPECT BRIEF
Name: [name]
Company: [company]
Title: [title]
Date: [today's date]

WHO THEY ARE
- [bullet]
- [bullet]
- [bullet if warranted]

WHAT IS HAPPENING AT THEIR COMPANY
- [bullet]
- [bullet]
- [bullet if warranted]

WHY REACH OUT NOW
- [specific, concrete reason tied to a [YOUR_COMPANY] service]
- [specific, concrete reason tied to a [YOUR_COMPANY] service]
- [specific, concrete reason tied to a [YOUR_COMPANY] service if warranted]

BEST ANGLE FOR [YOUR_ALIAS]
[One sentence: what to lead with in the opening line of an outreach message]

RELEVANT [YOUR_COMPANY] SERVICES
- [service 1]
- [service 2 if applicable]

CONFIDENCE: [High / Medium / Low]
[One sentence explaining the confidence level, especially if Low]
"""


def load_row(row_number: int) -> dict:
    if not SCORED_CSV.exists():
        print(f"ERROR: scored_leads.csv not found at {SCORED_CSV}")
        print("Run score_leads.py first to generate it.")
        sys.exit(1)
    with open(SCORED_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    idx = row_number - 1
    if idx < 0 or idx >= len(rows):
        print(f"ERROR: Row {row_number} is out of range (file has {len(rows)} rows).")
        sys.exit(1)
    return rows[idx]


def prompt_for_prospect() -> dict:
    print("\nEnter prospect details (press Enter to skip optional fields):\n")
    first = input("  First name: ").strip()
    last = input("  Last name: ").strip()
    company = input("  Company: ").strip()
    title = input("  Job title: ").strip()
    url = input("  LinkedIn URL (optional): ").strip()
    return {
        "First Name": first,
        "Last Name": last,
        "Company": company,
        "Position": title,
        "URL": url,
    }


def build_research_prompt(prospect: dict) -> str:
    name = f"{prospect.get('First Name', '')} {prospect.get('Last Name', '')}".strip()
    company = prospect.get("Company", "")
    title = prospect.get("Position", "")
    url = prospect.get("URL", "")

    parts = [
        f"Research this prospect for [YOUR_ALIAS] at [YOUR_COMPANY].",
        f"",
        f"Name: {name}",
        f"Company: {company}",
        f"Title: {title}",
    ]
    if url:
        parts.append(f"LinkedIn: {url}")

    parts += [
        f"",
        f"Please:",
        f"1. Search for recent activity, publications, patents, or conference talks by {name} at {company}.",
        f"2. Search for recent news about {company}: product launches, funding, hiring, regulatory filings, or anything related to materials, manufacturing, or R&D.",
        f"3. Map your findings to [YOUR_COMPANY] services and produce the structured brief in the exact format specified.",
    ]
    return "\n".join(parts)


def run_research(prospect: dict) -> str:
    client = anthropic.Anthropic()

    name = f"{prospect.get('First Name', '')} {prospect.get('Last Name', '')}".strip()
    company = prospect.get("Company", "") or "unknown"
    print(f"\nResearching {name} at {company} ...")
    print("(This may take 20-40 seconds while searching the web)\n")

    user_prompt = build_research_prompt(prospect)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Extract text from final response
    brief_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            brief_text += block.text

    return brief_text.strip()


def save_brief(brief: str, prospect: dict) -> Path:
    BRIEFS_DIR.mkdir(exist_ok=True)
    today = date.today().isoformat()
    company_slug = (prospect.get("Company", "Unknown") or "Unknown")
    company_slug = "".join(c if c.isalnum() or c in " -" else "" for c in company_slug)
    company_slug = company_slug.strip().replace(" ", "_")[:40]
    name_slug = (prospect.get("Last Name", "") or "").strip()
    filename = f"{today}_{company_slug}_{name_slug}.txt" if name_slug else f"{today}_{company_slug}.txt"
    out_path = BRIEFS_DIR / filename
    out_path.write_text(brief, encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Research a prospect for [YOUR_COMPANY] outreach.")
    parser.add_argument("--row", type=int, help="Row number from scored_leads.csv (1-indexed)")
    args = parser.parse_args()

    if args.row:
        prospect = load_row(args.row)
        name = f"{prospect.get('First Name', '')} {prospect.get('Last Name', '')}".strip()
        company = prospect.get("Company", "")
        title = prospect.get("Position", "")
        score = prospect.get("score", "?")
        tier = prospect.get("tier", "?")
        print(f"\nLoaded row {args.row}: {name} | {title} | {company}")
        print(f"Score: {score}  Tier: {tier}")
        confirm = input("\nProceed with research? [Y/n]: ").strip().lower()
        if confirm == "n":
            print("Aborted.")
            sys.exit(0)
    else:
        prospect = prompt_for_prospect()

    brief = run_research(prospect)

    print("\n" + "="*60)
    print(brief)
    print("="*60 + "\n")

    out_path = save_brief(brief, prospect)
    print(f"Brief saved to: {out_path}\n")


if __name__ == "__main__":
    main()

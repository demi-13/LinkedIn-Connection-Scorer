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

ENV_PATH = Path(r"C:\Users\demio\outreach-emailer\.env")
load_dotenv(ENV_PATH)

MODEL = "claude-sonnet-4-6"
BRIEFS_DIR = Path(__file__).parent / "briefs"
SCORED_CSV = Path(__file__).parent / "scored_leads.csv"

SYSTEM_PROMPT = """You are a research analyst for [YOUR_COMPANY], a fractional R&D consulting firm founded by [YOUR_NAME] ([YOUR_ALIAS]) ([YOUR_ALIAS]), CEO and Principal Scientist, based in Chicago, IL.

[YOUR_COMPANY]'s mission: make world-class materials, chemistry, and adhesion R&D accessible, sustainable, and equitable for every company, at every stage, in every industry. They deliver top-0.01% level expertise through productized R&D services built for speed, rigor, and real-world constraints, without requiring companies to hire full-time technical staff.

Focus industries: MedTech, GreenTech, Consumer, NanoTech.

[YOUR_COMPANY]'s six productized services:

1. AUDIT -- diagnoses hidden material or process risks before they turn into failures. Determines whether an issue is chemistry, processing, or design. Delivers a full materials + process diagnostic, failure-mode and risk ranking, and recommended mitigations. For: OEMs, product teams, medtech, consumer goods, founders under manufacturing pressure. Applies at: early concepts, prototypes, scale-up planning, supplier/manufacturer transitions, manufacturing troubleshooting.

2. DISCOVERY -- determines the right test or method to get a real answer, avoiding wasted time on the wrong experiments. Delivers DOE (design of experiments) design, test plans, prioritized variable lists, and equipment/vendor/lab recommendations. For: startups, small R&D teams, founders without in-house testing expertise, contract manufacturers needing clarity. Applies at: complex chemistries, polymers, nanofluids, coatings, adhesives, medtech interface testing, QA/QC test design.

3. FORMULATION -- identifies which material system best meets performance and sustainability needs, and helps choose between polymer, adhesive, or composite options. Delivers a materials shortlist, performance and sustainability scoring, initial concept formulations, and compatibility guidance. For: medtech, biotech, GreenTech packaging, consumer brands, adhesive/coating developers. Applies at: compostable coatings, adhesives, films, elastomers, polymer blends, nanoparticle carriers, early product R&D.

4. CHARACTERIZATION -- proves whether a material actually works, defines thermal/mechanical/surface limits, and diagnoses failure mechanisms. Delivers thermal/mechanical/surface characterization, rheology profiles, chemical/material compatibility assessments, and failure-mode mapping. For: nanotech, medtech, consumer goods, packaging companies, startups preparing for manufacturing. Applies at: nanofluids, coatings, adhesives, composites, films, elastomers, materials scale-up transitions.

5. IMPLEMENTATION -- translates scientific findings and data into actionable manufacturing decisions, reduces rework/scrap/late-stage surprises, and communicates decision-paths to stakeholders. Delivers manufacturing-ready recommendations, internal technical alignment meetings, decision frameworks, and integration into QA/QC workflows. For: OEMs, product and manufacturing teams, startups entering scale-up, medtech, consumer goods, advanced materials, hardware founders, engineering teams, process owners, QC/QA teams, ops leads. Applies at: pilot lines, first manufacturing runs, supplier onboarding, process optimization, post-failure recovery, design-for-manufacturing refinement, new materials launch, manufacturing transfer, supplier reviews.

6. AID (Adhesion Integrity Diagnostic) -- root-causes adhesion and interface failures such as contamination, incompatibility, or blooming, and determines if it's a processing or chemistry issue. Delivers surface and interface analysis (contact angle, FTIR, SEM/EDS), a root-cause report, and an actionable fix and prevention plan. For: OEMs, product companies, contract manufacturers (referrals). Applies at: overmolds, coatings, PSA/tapes, printed graphics, films and laminates, medtech, consumer goods.

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
- [service name from the six above, e.g. "Audit", "Discovery", "Formulation", "Characterization", "Implementation", "AID"]
- [additional service if applicable]

CONFIDENCE: [High / Medium / Low]
[One sentence explaining the confidence level, especially if Low]

Only list a service if the prospect's actual work or company stage genuinely matches its "Who It's For" and "Where It Applies" criteria. Do not force a fit.
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

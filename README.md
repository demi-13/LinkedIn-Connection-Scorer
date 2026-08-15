# LinkedIn Lead Scoring + CRM Automation

**Turns a raw LinkedIn connections export into a ranked, deduplicated client pipeline that syncs new prospects straight into Zoho CRM.**

---

## The Problem

My supervisor runs a fractional R&D consulting firm specializing in materials science, polymer engineering, and biomedical product development. She had roughly 2,500 LinkedIn connections and 200 contacts in her CRM. There was no reliable way to know which of those 2,300 uncategorized connections were actually worth pursuing.

The manual process: open each profile, read the title and company, make a judgment call, move on. For 2,500 people, that's weeks of work, and it doesn't repeat itself cleanly month over month as new connections come in.

The other problem: naive keyword scoring doesn't work. A pharma recruiter scores just as high as a pharma engineer if you're not careful. Early versions of this tool surfaced executive search consultants and student researchers in the top 10, people with zero need for R&D consulting services.

---

## What This Does

1. **Scores all 2,500+ connections in seconds.** No internet required, no API calls. Reads the LinkedIn connections CSV export and ranks every contact by how likely they are to need materials science or R&D consulting services.

2. **Filters out false positives automatically.** Recruiters, staffing firms, students, and executives with no technical background are penalized or capped, even when their titles contain high-value industry keywords.

3. **Runs monthly without a person in the loop.** Takes the top-scoring batch of not-yet-surfaced connections, checks each against existing Zoho CRM records to avoid duplicates, creates Leads for genuine net-new prospects, and emails a summary. Built so the pipeline keeps running after the internship that produced it ends.

4. **Generates a research brief on any top prospect.** One command pulls up a structured brief with background on the person, recent company news, specific reasons to reach out, and the best opening angle for [YOUR_ALIAS] to use.

---

## How It Works

### Part 1: Lead Scorer (`score_leads.py`)

Reads the raw LinkedIn CSV (which includes a multi-line notes header LinkedIn injects before the actual data, handled automatically) and scores every row using a keyword matching system across two fields: `Company` and `Position`.

**Scoring logic:**
- Industry keywords in the combined Company + Position field: +2 for high-value signals (medtech, biotech, pharmaceutical, fertility, life science, implant, surgical) and +1 for medium signals (manufacturing, polymer, materials, aerospace, chemical, R&D, lab)
- Title keywords in the Position field: +2 for technical roles (engineer, scientist, researcher, materials, formulation, quality, regulatory, principal) and +1 for business roles (manager, founder, CTO)

**False positive filters, built after testing on real data:**
- Recruiter hard cap: if the title contains any recruiter signal (recruiter, recruiting, recruitment, talent acquisition, executive search, sourcer, staffing), the score is capped at 0 regardless of industry keywords. A pharma executive search specialist isn't a consulting prospect even though "pharmaceutical" appears in their title.
- Student hard cap: titles containing student, undergraduate, intern, or trainee are capped at score 1.
- Exec-only penalty: CEO, President, and Founder titles with zero technical keywords (engineer, scientist, materials, formulation, R&D, regulatory, quality) contribute 0 from the title scoring pass.
- Staffing firm company penalty: companies with staffing, recruiting, workforce, outsourcing, or placement in their name receive -3.

Output is sorted by score and tiered: Top (4+), Strong (2-3), Weak (1), Skip (0 or below).

### Part 2: Monthly CRM Automation (`monthly_lead_import.py`)

Imports the scoring logic directly from `score_leads.py`, so the standalone scorer and the automated monthly run can never drift apart. Each month:

1. Scores a fresh CSV export using the same rules as above
2. Drops anyone already surfaced in a previous run (tracked both locally in `surfaced_leads.json` and via a `Scorer_Batch_Date` field in Zoho, so the CRM stays the source of truth even if the local file is lost)
3. Takes the top N (default 25, configurable)
4. Checks each against Zoho CRM by name and company. Existing contacts get flagged as "already known" instead of duplicated. New ones become Leads tagged with this month's batch date
5. Emails a run summary to a configured recipient list, and logs it locally regardless of whether the email send succeeds

Full setup and troubleshooting details live in `MONTHLY_IMPORT_README.md`.

### Part 3: Prospect Research Agent (`research_prospect.py`)

Takes a single prospect by row number from the scored CSV (or manual input) and runs Claude (`claude-sonnet-4-6`) with the `web_search_20250305` tool to research two things:
1. Recent activity, publications, patents, or talks by the person
2. Recent company news: product launches, funding, hiring signals, regulatory filings

Maps findings to the firm's specific service areas and returns a structured brief: who they are, what's happening at their company, why to reach out now, the best opening angle, and which services apply. Every brief carries a confidence rating (High/Medium/Low). If search results are thin, the agent says so instead of padding the brief. Saves automatically to `briefs/{date}_{company}_{last_name}.txt`.

```bash
python research_prospect.py --row 3   # load row 3 from scored_leads.csv
python research_prospect.py           # interactive prompts instead
```

---

## Key Features

- **Processes 2,500+ connections in under 3 seconds**, no API calls or internet access required for scoring
- **Eliminates recruiter and student false positives** that naive keyword scoring misses, validated against real LinkedIn export data
- **Never re-surfaces the same connection twice** across monthly runs, checked against both a local cache and Zoho CRM directly
- **Blocks duplicate CRM writes.** A name and company match against existing records stops a duplicate Lead from ever being created
- **Dry-run mode** for testing scoring and duplicate logic against a real CSV without writing to the CRM or sending an email
- **Row-number lookup** takes a prospect straight from the scored CSV into a research brief without retyping any contact details
- **Confidence-rated briefs.** The research agent says "Confidence: Low" and why, rather than padding out a thin result

---

## Tech Stack

| Tool | Why |
|---|---|
| Python 3 (stdlib csv, io, pathlib) | No dependencies for the scorer. Fast, portable, runs anywhere |
| `requests` | Zoho CRM API calls (OAuth token refresh, Lead lookup/creation) from the monthly import |
| `python-dotenv` | Loads Zoho and Anthropic credentials from a shared `.env` file |
| Zoho CRM API | Duplicate checking and Lead creation, with two custom fields (`Scorer_Batch_Date`, `Lead_Score_Raw`) to track batches |
| `anthropic` SDK, `claude-sonnet-4-6` | Research agent's model, called with the native `web_search_20250305` tool. No separate search API key needed |

---

## Results

- **2,555 connections scored** in under 3 seconds on first run
- **Top tier cleaned up significantly** after false positive filtering. Removed a pharma executive search consultant (old score: 10, new: 0) and a biotech recruiter (old score: 9, new: 0) from the top 10
- **Legitimate prospects unaffected.** A Principal Materials Engineer at Raytheon and a Materials Research Engineer at the U.S. Naval Research Laboratory held their scores after all filters were applied
- **Research briefs generated in 20-40 seconds** per prospect using live web search
- Replaced what would have been days of manual LinkedIn review with a repeatable, monthly automated pipeline that runs without further input once a CSV is uploaded

---

## Setup

```bash
# Clone and enter the project
git clone https://github.com/demi-13/LinkedIn-Connection-Scorer.git
cd LinkedIn-Connection-Scorer

# Install dependencies
pip install -r requirements.txt

# Add Zoho CRM and Anthropic credentials to a .env file (see MONTHLY_IMPORT_README.md for the full Zoho field list)
echo "ANTHROPIC_API_KEY=your_key_here" >> .env
```

**Download your LinkedIn connections:**
1. LinkedIn > Settings and Privacy > Data Privacy > Get a copy of your data
2. Select Connections only, request the archive
3. Download and unzip when the email arrives, find `Connections.csv`
4. Move it into this folder

---

## Usage

**Score all connections:**
```bash
python score_leads.py Connections.csv
```
Prints a tier summary and top 10 preview. Saves full results to `scored_leads.csv`.

**Run the monthly CRM import:**
```bash
python monthly_lead_import.py --csv Connections.csv
python monthly_lead_import.py --csv Connections.csv --dry-run       # test without writing to CRM or emailing
python monthly_lead_import.py --csv Connections.csv --batch-size 40 # override the default batch of 25
```

**Research a top prospect:**
```bash
python research_prospect.py --row 3   # by row number from scored_leads.csv
python research_prospect.py           # or enter details manually
```
Brief prints to terminal and saves to `briefs/YYYY-MM-DD_Company_Name.txt`.

**Verify scoring logic:**
```bash
python test_score.py
```
Runs test cases including real false positive examples pulled from production data. All should pass.

---

## What's Next

1. **Chain scoring straight into outreach.** Automatically pass a research brief as context to the [outreach drafting agent](https://github.com/demi-13/zoho-outreach-agent) so a new Lead can go from score to research brief to draft email in one pass instead of three manual steps.
2. **Score decay by connection date.** The `Connected On` field is in the CSV but unused. A strong prospect connected in 2019 with no follow-up is a different priority than one connected last month.

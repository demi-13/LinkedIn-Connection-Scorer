# LinkedIn Lead Scoring + Prospect Research Agent

**Turns a 2,500-connection LinkedIn export into a ranked client pipeline — with AI-generated research briefs on the best prospects.**

---

## The Problem

My supervisor runs a fractional R&D consulting firm specializing in materials science, polymer engineering, and biomedical product development. She had roughly 2,500 LinkedIn connections and 200 contacts in her CRM — and no reliable way to know which of those 2,300 uncategorized connections were actually worth pursuing.

The manual process: open each profile, read the title and company, make a judgment call, move on. For 2,500 people, that is weeks of work. And even when you find a strong lead, you still need to research them before reaching out.

The other problem: naive keyword scoring does not work. A pharma recruiter scores just as high as a pharma engineer if you are not careful. Early versions of this tool surfaced executive search consultants and student researchers in the top 10 — people with zero need for R&D consulting services.

---

## What This Does

1. **Scores all 2,500+ connections in seconds** — no internet required, no API calls. Reads the LinkedIn connections CSV export and ranks every contact by how likely they are to need materials science or R&D consulting services.

2. **Filters out false positives automatically** — recruiters, staffing firms, students, and executives with no technical background are penalized or capped, even when their titles contain high-value industry keywords.

3. **Generates a research brief on any top prospect** — one command pulls up a structured brief with background on the person, recent company news, specific reasons to reach out, and the best opening angle for [YOUR_ALIAS] to use.

---

## How It Works

### Part 1 — Lead Scorer (`score_leads.py`)

Reads the raw LinkedIn CSV (which includes a multi-line notes header LinkedIn injects before the actual data — handled automatically) and scores every row using a keyword matching system across two fields: `Company` and `Position`.

**Scoring logic:**
- Industry keywords in the combined Company + Position field: +2 for high-value signals (medtech, biotech, pharmaceutical, fertility, life science, implant, surgical) and +1 for medium signals (manufacturing, polymer, materials, aerospace, chemical, R&D, lab)
- Title keywords in the Position field: +2 for technical roles (engineer, scientist, researcher, materials, formulation, quality, regulatory, principal) and +1 for business roles (manager, founder, CTO)

**False positive filters built after testing on real data:**
- Recruiter hard cap: if the title contains any recruiter signal (recruiter, recruiting, recruitment, talent acquisition, executive search, sourcer, staffing), the score is capped at 0 regardless of industry keywords. A pharma executive search specialist is not a consulting prospect even though "pharmaceutical" appears in their title.
- Student hard cap: titles containing student, undergraduate, intern, or trainee are capped at score 1.
- Exec-only penalty: CEO, President, and Founder titles with zero technical keywords (engineer, scientist, materials, formulation, R&D, regulatory, quality) contribute 0 from the title scoring pass.
- Staffing firm company penalty: companies with staffing, recruiting, workforce, outsourcing, or placement in their name receive -3.

Output is sorted by score and tiered: Top (4+), Strong (2-3), Weak (1), Skip (0 or below).

### Part 2 — Research Agent (`research_prospect.py`)

Takes a single prospect by row number from the scored CSV (or manual input) and runs two web searches using Claude claude-sonnet-4-6 with the `web_search_20250305` tool:
1. Recent activity, publications, patents, or talks by the person
2. Recent company news — product launches, funding, hiring signals, regulatory filings

Maps findings to the firm's specific service areas and returns a structured brief: who they are, what is happening at their company, why to reach out now, the best opening angle, and which services apply. Saves automatically to `/briefs/`.

---

## Key Features

- **Processes 2,500+ connections in under 3 seconds** with no API calls or internet access required for scoring
- **Eliminates recruiter and student false positives** that naive keyword scoring misses — validated against real LinkedIn export data
- **Row-number lookup** lets you go from scored CSV to research brief in one command without retyping any contact details
- **Structured brief output** is designed to feed directly into a downstream email drafting agent — clean enough to paste as context
- **Confidence rating** on every brief: if web search returns thin results, the agent says so rather than padding

---

## Tech Stack

| Tool | Why |
|---|---|
| Python 3 (stdlib csv, io, pathlib) | No dependencies for the scorer — fast, portable, runs anywhere |
| `anthropic` SDK | Claude claude-sonnet-4-6 with built-in web search tool for the research agent |
| `web_search_20250305` tool | Native search via the Anthropic API — no separate search API key needed |
| `python-dotenv` | Loads API key from shared `.env` file used across the broader agent suite |

---

## Results

- **2,555 connections scored** in under 3 seconds on first run
- **Top tier cleaned up significantly** after false positive filtering: removed a pharma executive search consultant (old score: 10, new: 0) and a biotech recruiter (old score: 9, new: 0) from the top 10
- **Legitimate prospects unaffected**: a Principal Materials Engineer at Raytheon and a Materials Research Engineer at the U.S. Naval Research Laboratory held their scores after all filters were applied
- **Research briefs generated in 20-40 seconds** per prospect using live web search
- Replaced what would have been days of manual LinkedIn review with a repeatable, automated pipeline

---

## Setup

```bash
# Clone and enter the project
cd linkedin-lead-agent

# Install dependencies
pip install anthropic python-dotenv

# Add your Anthropic API key to a .env file
echo "ANTHROPIC_API_KEY=your_key_here" > ../outreach-emailer.env
```

**Download your LinkedIn connections:**
1. LinkedIn > Settings and Privacy > Data Privacy > Get a copy of your data
2. Select Connections only, request the archive
3. Download and unzip when the email arrives — find `Connections.csv`
4. Move it into this folder

---

## Usage

**Score all connections:**
```bash
python score_leads.py Connections.csv
```
Prints a tier summary and top 10 preview. Saves full results to `scored_leads.csv`.

**Research a top prospect:**
```bash
# By row number from scored_leads.csv
python research_prospect.py --row 3

# Or enter details manually
python research_prospect.py
```
Brief prints to terminal and saves to `/briefs/YYYY-MM-DD_Company_Name.txt`.

**Verify scoring logic:**
```bash
python test_score.py
```
Runs 15 test cases including real false positive examples. All should pass.

---

## What I Would Do Next

1. **Chain the two scripts** — after generating a brief, automatically pass it as context to the outreach email agent so [YOUR_ALIAS] can go from score to draft in one step instead of two

2. **Add CRM deduplication** — cross-reference `scored_leads.csv` against the existing Zoho CRM contacts before surfacing Top prospects, so she is not researching people already in her pipeline

3. **Score decay by connection date** — the `Connected On` field is in the CSV but unused. A strong prospect connected in 2019 with no follow-up is a different priority than one connected last month

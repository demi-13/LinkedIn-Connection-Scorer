# LinkedIn Lead Agent -- [YOUR_COMPANY]

## What This Tool Does

This tool scores your LinkedIn connections by how likely they are to need [YOUR_COMPANY]'s services, then batch-imports the top net-new prospects into Zoho CRM as Leads once a month. Scoring runs entirely offline (no internet, no API calls needed).

---

## Step 1 -- Download Your LinkedIn Connections CSV

1. Go to LinkedIn and click your profile photo in the top-right corner
2. Select **Settings and Privacy**
3. Click **Data Privacy** in the left sidebar
4. Click **Get a copy of your data**
5. Select **Connections** (you do not need the full archive)
6. Click **Request archive**
7. LinkedIn will email you a download link within 10 minutes to a few hours
8. Download the ZIP, unzip it, and find the file named `Connections.csv`
9. Move that file into this folder: `C:\Users\demio\OneDrive\Desktop\claude\linkedin-lead-agent\`

---

## Step 2 -- Score All Your Connections

Open a terminal in `C:\Users\demio\OneDrive\Desktop\claude\linkedin-lead-agent\` and run:

```
python score_leads.py Connections.csv
```

What happens:
- Every connection is scored based on their job title and company
- Results are saved to `scored_leads.csv` in the same folder
- The terminal prints a summary and your top 10 prospects

**Understanding the scores:**

Scores are additive -- every matching keyword adds points. Typical Top prospects score between 6 and 10.

Industry keywords scanned across Company and Title:
- +2 each: medtech, medical device, biotech, life science, fertility, IVF, pharma, implant, surgical, diagnostic, PFAS, forever chemicals, etc.
- +1 each: manufacturing, plastics, polymer, materials, aerospace, chemical, R&D, lab, etc.

Job title keywords scanned on Title only:
- **+3 each (decision-makers, prioritized over individual contributors):** CEO, CTO, COO, CSO, Director, VP, Vice President, Founder, Co-Founder, Owner -- but only when the company OR the title itself carries an industry signal. A cofounder whose title mentions PFAS scores high even if their company name is generic. A CEO at a totally unrelated company scores 0 from title.
- +2 each: engineer, scientist, researcher, materials, R&D, quality, regulatory, formulation, principal, lab manager, technical lead, etc.
- +1 each: manager, operations, procurement, supply chain
- -1 each: sales, marketing, HR, social media, finance, etc.

[YOUR_ALIAS] wants people with buying power first. Decision-makers (CEO, CTO, cofounders) now outscore individual-contributor engineers and scientists when both have a relevant industry signal, since they are the ones who can actually greenlight a consulting engagement.

**False positive filters (applied automatically):**
- Recruiters and executive search professionals are capped at 0 (Skip) regardless of how many industry keywords appear in their title. A pharma executive search consultant is not a [YOUR_COMPANY] prospect.
- Students, interns, and trainees are capped at 1 (Weak).
- CEOs, Directors, and other exec titles at companies with no industry signal score 0 from the title pass.
- Companies with staffing/workforce/outsourcing in their name receive a -3 penalty.

Tiers explained:
- **Top** (score 4+): Strong match, worth researching right away
- **Strong** (score 2-3): Likely relevant, good secondary list
- **Weak** (score 1): Marginal, maybe revisit later
- **Skip** (score 0 or below): Not a fit for [YOUR_COMPANY] right now

The exact number matters less than the tier. Anyone in Top is worth running the research agent on.

---

## Step 3 -- Monthly Batch Import to Zoho CRM

`monthly_lead_import.py` runs the monthly automation: score a fresh connections CSV, skip anyone already surfaced in a prior run, cross-reference Zoho CRM, and create Leads for the top net-new prospects.

```
python monthly_lead_import.py --csv Connections.csv
python monthly_lead_import.py --csv Connections.csv --dry-run
python monthly_lead_import.py --csv Connections.csv --batch-size 25
```

**Batch selection with backfill:** the script does not simply take the top 25 scores and stop. It walks the full sorted candidate pool one contact at a time, in score order, and skips anyone who already exists in Zoho (Lead or Contact). Every skip pulls in the next-highest-scoring unmatched contact to take its place, so the batch keeps filling until it reaches the target batch size (default 25) or the candidate pool runs out -- whichever comes first. This means the final batch size can only fall short of the target when there genuinely aren't enough net-new candidates left, not because top-scored people happened to already be in CRM.

Each contact is only ever examined once per run (single pass, no re-scanning), so a contact flagged as already-in-CRM can never later be double-counted as its own backfill.

The terminal prints a **Selection / backfill log** before the summary, showing exactly what happened:
```
SKIP (already in CRM): Jane Doe (Acme Corp) -- score 8
BACKFILL: replaced Jane Doe (already in CRM) with John Smith, score 7
ACCEPT: Maria Lopez (BetaLabs) -- score 6
```
Use this to sanity-check the batch before it goes out, especially in `--dry-run` mode.

Scoring itself (role/industry fit, recruiter penalty, student cap) is unchanged -- it's imported directly from `score_leads.py`, so this step never drifts from the main scorer. `Scorer_Batch_Date` and `Lead_Score_Raw` are still stamped on every created Lead exactly as before.

**Missing emails -- LinkMatch follow-up list:** LinkedIn only includes a connection's email in the export if that person has enabled "let connections see my email" in their own settings, so most rows won't have one. When a Lead is created and the CSV had no email for them, the Lead is still created normally, and they're listed directly in the run summary email under "No email on file, add via LinkMatch" -- name, company, and a clickable LinkedIn profile link. [YOUR_ALIAS] works this list manually with the LinkMatch Chrome extension the same way she already does today -- this is not automated, since bulk automated actions against LinkedIn risk the account getting flagged. If a connection did have an email in the CSV, it's written straight onto the Lead's `Email` field and they won't appear on this list.

---

## Troubleshooting

**"File not found" when running score_leads.py**
Make sure the CSV is in the same folder as `score_leads.py` and the filename matches exactly what you typed.

---

## File Reference

```
linkedin-lead-agent/
  monthly_lead_import.py  Monthly scorer -> Zoho CRM import automation
  score_leads.py          Scoring rules -- imported by monthly_lead_import.py
  test_score.py           Scoring verification -- run once to confirm logic
  AGENT.md                This file
  MONTHLY_IMPORT_README.md  Runbook for the monthly import
```

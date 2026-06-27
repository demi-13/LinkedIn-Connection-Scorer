# LinkedIn Lead Agent -- [YOUR_COMPANY]

## What This Tool Does

This tool scores your LinkedIn connections by how likely they are to need [YOUR_COMPANY]'s services, then lets you generate a deep research brief on any promising contact. It is designed to run in two steps: first score everyone fast (no internet needed), then research the ones worth pursuing one at a time.

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
- +2 each: medtech, medical device, biotech, life science, fertility, IVF, pharma, implant, surgical, diagnostic, etc.
- +1 each: manufacturing, plastics, polymer, materials, aerospace, chemical, R&D, lab, etc.

Job title keywords scanned on Title only:
- +2 each: engineer, scientist, researcher, materials, R&D, quality, regulatory, formulation, lab manager, principal, etc.
- +1 each: manager, founder, owner, CTO, COO, operations, supply chain, etc.
- -1 each: sales, marketing, HR, social media, finance, etc.

**False positive filters (applied automatically):**
- Recruiters and executive search professionals are capped at 0 (Skip) regardless of how many industry keywords appear in their title. A pharma recruiter is not a [YOUR_COMPANY] prospect.
- Students, interns, and trainees are capped at 1 (Weak).
- CEOs and Presidents with no technical keywords in their title score 0 from title (not +1).
- Companies with staffing/workforce/outsourcing in their name receive a -3 penalty.

Tiers explained:
- **Top** (score 4+): Strong match, worth researching right away
- **Strong** (score 2-3): Likely relevant, good secondary list
- **Weak** (score 1): Marginal, maybe revisit later
- **Skip** (score 0 or below): Not a fit for [YOUR_COMPANY] right now

The exact number matters less than the tier. Anyone in Top is worth running the research agent on.

---

## Step 3 -- Research a Top Prospect

Once you have `scored_leads.csv`, run the research agent on anyone in the Top or Strong tier.

**Option A -- Enter details manually:**
```
python research_prospect.py
```
You will be prompted for name, company, title, and optional LinkedIn URL.

**Option B -- Use the row number from scored_leads.csv:**
```
python research_prospect.py --row 3
```
This pulls row 3 directly so you do not have to retype anything. Open `scored_leads.csv` first to find the row number of the person you want.

The agent:
- Searches the web for recent activity by that person and their company
- Maps findings to [YOUR_COMPANY]'s services
- Prints a structured brief to the terminal
- Automatically saves the brief to the `/briefs/` folder

---

## Step 4 -- What To Do With the Brief

The brief is designed to feed directly into the outreach email agent.

1. Open the saved `.txt` file from `/briefs/`
2. Go to the outreach agent at `C:\Users\demio\[YOUR_ALIAS]-outreach-agent\`
3. Paste the brief as context when drafting the email
4. The outreach agent will use the research to write a specific, relevant opening

If the Confidence rating is Low, review the brief before sending anything. It means the web search did not return much and you may want to verify details first.

---

## Troubleshooting

**"File not found" when running score_leads.py**
Make sure the CSV is in the same folder as `score_leads.py` and the filename matches exactly what you typed.

**"scored_leads.csv not found" when running research_prospect.py**
Run `score_leads.py` first to generate it.

**API key error**
The tool reads your key from `C:\Users\demio\outreach-emailer.env`. Make sure `ANTHROPIC_API_KEY=...` is in that file.

**Research takes a long time**
Normal. Web search takes 20-40 seconds per prospect. Do not close the terminal.

---

## File Reference

```
linkedin-lead-agent/
  score_leads.py          Fast scorer -- no API calls, runs on all 2,000 rows
  research_prospect.py    Deep research agent -- one prospect at a time
  test_score.py           Scoring verification -- run once to confirm logic
  AGENT.md                This file
  scored_leads.csv        Generated after you run score_leads.py
  briefs/                 Research briefs saved here automatically
```

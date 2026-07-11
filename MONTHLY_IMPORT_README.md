# Monthly LinkedIn Lead Scorer → CRM Automation

This agent scores a fresh LinkedIn connections export, filters out anyone already brought in during a prior month, takes the top-scoring batch, checks each against existing CRM records, creates new Leads for genuine net-new prospects, and emails a summary. Built so it can run without Demi once she leaves the internship.

## What you need before running this for the first time

1. Two custom fields on the Leads module in Zoho CRM *(created 2026-07-07 — already in place)*:
   * `Scorer_Batch_Date` (Date) — stamps which monthly batch a lead came from, and prevents the same lead being surfaced twice
   * `Lead_Score_Raw` (Number) — the score assigned by the scorer, useful for later analysis

   If these ever get deleted, ask Claude Code to recreate them via the Zoho CRM API (`createFields`) before the next run.

2. A `.env` file at `C:\Users\demio\outreach-emailer\.env` containing:

   ```
   ZOHO_CLIENT_ID=...
   ZOHO_CLIENT_SECRET=...
   ZOHO_REFRESH_TOKEN=...
   MONTHLY_IMPORT_RECIPIENTS=you@yourcompany.com,demo-assistant@example.com
   ```

   (Same file already used by the other agents. `MONTHLY_IMPORT_RECIPIENTS` was added 2026-07-07 — update it when Demi's address should come off the list.)

3. A fresh LinkedIn connections CSV export. LinkedIn does not support automated export, so this one step stays manual: go to LinkedIn → Settings → Data Privacy → Get a copy of your data → Connections, download the CSV once it's ready (can take a few minutes to a few hours), and save it somewhere easy to point this script at.

## How to run it

Ask Claude Code:

> "Run the monthly lead import using this CSV: [path to file]"

Or run directly:

```
python monthly_lead_import.py --csv path/to/connections.csv
```

To test without changing the CRM or sending an email (it still *reads* the CRM to check duplicates):

```
python monthly_lead_import.py --csv path/to/connections.csv --dry-run
```

To change how many leads get pulled in a given month (default is 25):

```
python monthly_lead_import.py --csv path/to/connections.csv --batch-size 40
```

## What happens each run

1. Reads the CSV and scores every connection using the **same rules as the original lead scorer** — the scoring is imported directly from `score_leads.py`, so the two can never drift apart (technical title match, industry match, staffing/recruiting penalty, student cap, executive titles only counted alongside a technical or industry signal).
2. Drops anyone already surfaced in a previous run (tracked both locally in `surfaced_leads.json` and via the `Scorer_Batch_Date` field in Zoho, so the CRM stays the source of truth even if the local file is lost).
3. Takes the top N (batch size) of what's left.
4. For each one, checks Zoho CRM by name + company:
   * Already exists → does not create a duplicate. Adds to the "already-known contact" list in the summary instead, so [YOUR_ALIAS] can decide whether it's worth a re-engagement touch.
   * Doesn't exist → creates a new Lead, stage "New Connection," source "Lead Scorer," tagged with this month's date.
5. Emails a summary to everyone listed in `MONTHLY_IMPORT_RECIPIENTS`: how many new leads were added, how many known contacts were flagged, and whether anything went wrong or came up short (e.g. fewer than 25 usable leads remained in the pool).

## If something looks wrong

* **No email arrives:** check `logs/run_<date>.txt` — the summary is always saved locally even if the email send fails.
* **Fewer leads than expected:** the summary will say so explicitly ("only N unsurfaced leads remained"). This usually means the pool of scored, not-yet-surfaced connections is running low — time to request a fresh LinkedIn export with newer connections, or revisit the scoring thresholds.
* **A lead you expected to see wasn't created:** check whether it was flagged as "already-known" instead — that's the intended behavior, not a bug, since the goal is no duplicates.

## Adjusting the scoring logic later

The scoring rules live in `score_leads.py` (keyword lists for technical titles, industry match, staffing penalty, student cap) — `monthly_lead_import.py` imports them from there, so one edit updates both the standalone scorer and the monthly import. Ask Claude Code:

> "Update the scoring in score_leads.py to also count [new keyword]"

and it can make the edit directly. No need to touch anything else.

## Scheduling this to run automatically

This is meant to run once a month via a Claude Cowork scheduled task. Since LinkedIn's CSV export has to be requested and downloaded manually, the scheduled task should prompt for the CSV upload rather than run silently — similar to the existing weekly LinkedIn content refresh pattern. Once the CSV is uploaded, everything downstream (scoring, CRM writes, email) runs without further input.

## Notes for whoever maintains this after Demi

* `Lead_Source` is written as "Lead Scorer", which is not a predefined picklist value in Zoho — the API accepts it and it displays fine, but if you want it filterable from the picklist dropdown, add it in Zoho CRM Settings → Fields → Lead Source.
* The duplicate check treats a same-name Contact with **no account** as already-known (errs toward flagging rather than duplicating).
* A run that hits errors exits with code 1 so a scheduler can tell something went wrong; details are in the emailed summary and the log file.

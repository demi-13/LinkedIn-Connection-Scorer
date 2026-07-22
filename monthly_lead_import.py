"""
monthly_lead_import.py

Monthly LinkedIn Lead Scorer -> Zoho CRM Automation

Scores a fresh LinkedIn connections CSV export, filters out leads already
surfaced in a prior monthly run, takes the top N by score, checks each
against existing Zoho CRM records (name + company) to avoid duplicates,
creates new Leads for genuine net-new prospects, flags already-known
contacts separately, and emails a summary to [YOUR_ALIAS] and Demi.

Run this once a month. Requires a fresh LinkedIn CSV export as input
(LinkedIn does not support automated export, so this step is manual).

Scoring rules are NOT defined here -- they are imported from score_leads.py
in this folder, so the monthly import always matches the original scorer.

Credentials load from the shared .env file at:
    C:\\Users\\demio\\outreach-emailer\\.env

Usage:
    python monthly_lead_import.py --csv path/to/connections.csv
    python monthly_lead_import.py --csv path/to/connections.csv --dry-run
    python monthly_lead_import.py --csv path/to/connections.csv --batch-size 25
"""

import argparse
import csv
import io
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
import requests

from score_leads import score_row

# Ensure Unicode names print safely on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ENV_PATH = Path(r"C:\Users\demio\outreach-emailer\.env")
DEFAULT_BATCH_SIZE = 25
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

ZOHO_ACCOUNTS_URL = "https://accounts.zoho.com/oauth/v2/token"
ZOHO_API_BASE = "https://www.zohoapis.com/crm/v2"
ZOHO_MAIL_BASE = "https://mail.zoho.com/api"


# ---------------------------------------------------------------------------
# Batch tracking state (local file is a fallback; the Scorer_Batch_Date
# field in Zoho is the source of truth and is re-read on every run)
# ---------------------------------------------------------------------------

STATE_FILE = Path(__file__).parent / "surfaced_leads.json"


def load_surfaced_local() -> set:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    return set()


def save_surfaced_local(surfaced: set):
    STATE_FILE.write_text(json.dumps(sorted(surfaced), indent=0), encoding="utf-8")


def lead_key(name: str, company: str) -> str:
    return f"{(name or '').strip().lower()}|{(company or '').strip().lower()}"


# ---------------------------------------------------------------------------
# Zoho CRM + Mail access
# ---------------------------------------------------------------------------

def _esc(value: str) -> str:
    """Escape characters with special meaning in Zoho search criteria."""
    for ch in ("\\", "(", ")", ","):
        value = value.replace(ch, "\\" + ch)
    return value


class ZohoClient:
    def __init__(self):
        self.client_id = os.environ["ZOHO_CLIENT_ID"]
        self.client_secret = os.environ["ZOHO_CLIENT_SECRET"]
        self.refresh_token = os.environ["ZOHO_REFRESH_TOKEN"]
        self.access_token = None

    def _refresh(self):
        resp = requests.post(ZOHO_ACCOUNTS_URL, params={
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
        })
        resp.raise_for_status()
        self.access_token = resp.json()["access_token"]

    def _headers(self):
        if not self.access_token:
            self._refresh()
        return {"Authorization": f"Zoho-oauthtoken {self.access_token}"}

    def fetch_surfaced_from_crm(self) -> set:
        """Rebuild the surfaced-lead set from Zoho: every Lead stamped with a
        Scorer_Batch_Date came from a prior monthly run. Keeps the CRM as the
        source of truth even if surfaced_leads.json is lost."""
        surfaced = set()
        page = 1
        while True:
            resp = requests.get(
                f"{ZOHO_API_BASE}/Leads",
                headers=self._headers(),
                params={
                    "fields": "Full_Name,Company,Scorer_Batch_Date",
                    "per_page": 200,
                    "page": page,
                },
            )
            if resp.status_code == 204:  # no records at all
                break
            resp.raise_for_status()
            payload = resp.json()
            for rec in payload.get("data", []):
                if rec.get("Scorer_Batch_Date"):
                    surfaced.add(lead_key(rec.get("Full_Name", ""), rec.get("Company", "")))
            if not payload.get("info", {}).get("more_records"):
                break
            page += 1
        return surfaced

    def find_existing_lead_or_contact(self, name: str, company: str) -> bool:
        """Return True if a Lead or Contact with this name + company already exists."""
        company_l = (company or "").strip().lower()

        # Leads have a Company field, so the API can match name + company directly.
        resp = requests.get(
            f"{ZOHO_API_BASE}/Leads/search",
            headers=self._headers(),
            params={"criteria": f"((Full_Name:equals:{_esc(name)})and(Company:equals:{_esc(company)}))"},
        )
        if resp.status_code == 200 and resp.json().get("data"):
            return True
        resp.raise_for_status()

        # Contacts have no Company field (company lives on the Account lookup),
        # so match by name and compare the account name client-side.
        resp = requests.get(
            f"{ZOHO_API_BASE}/Contacts/search",
            headers=self._headers(),
            params={"criteria": f"(Full_Name:equals:{_esc(name)})"},
        )
        if resp.status_code == 204:
            return False
        resp.raise_for_status()
        for rec in resp.json().get("data", []):
            account = rec.get("Account_Name") or {}
            account_name = (account.get("name") or "").strip().lower()
            if account_name == company_l or not account_name:
                # Same name with a matching account, or same name with no
                # account at all, counts as already known -- err on the side
                # of flagging rather than duplicating.
                return True
        return False

    def create_lead(self, name: str, company: str, title: str, score: int, batch_date: str, email: str = ""):
        first, _, last = name.partition(" ")
        lead_data = {
            "First_Name": first if last else "",
            "Last_Name": last or name,
            "Company": company,
            "Designation": title,
            "Lead_Source": "Lead Scorer",
            "Lead_Status": "New Connection",
            "Scorer_Batch_Date": batch_date,
            "Lead_Score_Raw": score,
        }
        if email:
            lead_data["Email"] = email
        payload = {"data": [lead_data]}
        resp = requests.post(f"{ZOHO_API_BASE}/Leads", headers=self._headers(), json=payload)
        resp.raise_for_status()
        result = resp.json()["data"][0]
        if result.get("status") != "success":
            raise RuntimeError(f"Zoho rejected lead: {result}")

    def send_mail(self, to_addresses: list, subject: str, body: str):
        resp = requests.get(f"{ZOHO_MAIL_BASE}/accounts", headers=self._headers())
        resp.raise_for_status()
        account = resp.json()["data"][0]
        from_address = (
            os.environ.get("FROM_ADDRESS")
            or account.get("primaryEmailAddress")
            or account.get("incomingUserName")
        )
        resp = requests.post(
            f"{ZOHO_MAIL_BASE}/accounts/{account['accountId']}/messages",
            headers={**self._headers(), "Content-Type": "application/json"},
            json={
                "fromAddress": from_address,
                "toAddress": ",".join(to_addresses),
                "subject": subject,
                "content": body.replace("\n", "<br>"),
                "mailFormat": "html",
            },
        )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# CSV parsing (LinkedIn exports start with a "Notes:" preamble block)
# ---------------------------------------------------------------------------

def read_connections(csv_path: str) -> list:
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        lines = f.readlines()
    start = next((i for i, l in enumerate(lines) if l.startswith("First Name")), 0)
    reader = csv.DictReader(io.StringIO("".join(lines[start:])))
    rows = []
    for row in reader:
        name = f"{(row.get('First Name') or '').strip()} {(row.get('Last Name') or '').strip()}".strip()
        company = (row.get("Company") or "").strip()
        title = (row.get("Position") or "").strip()
        email = (row.get("Email Address") or "").strip()
        profile_url = (row.get("URL") or "").strip()
        if name and company:
            rows.append((name, company, title, email, profile_url))
    return rows


# ---------------------------------------------------------------------------
# Email summary
# ---------------------------------------------------------------------------

def send_summary_email(client, new_leads, flagged_contacts, batch_size, pool_size, errors, dry_run: bool,
                       needs_linkmatch=None):
    recipients = os.environ.get("MONTHLY_IMPORT_RECIPIENTS", "").split(",")
    recipients = [r.strip() for r in recipients if r.strip()]

    today = date.today().isoformat()
    lines = [f"Monthly LinkedIn Lead Scorer Run -- {today}", ""]
    lines.append(f"New leads added to CRM: {len(new_leads)}")
    for n, c, s in new_leads:
        lines.append(f"  - {n} ({c}) -- score {s}")
    lines.append("")
    lines.append(f"Already-known contacts flagged (not duplicated): {len(flagged_contacts)}")
    for n, c, s in flagged_contacts:
        lines.append(f"  - {n} ({c}) -- score {s}")
    lines.append("")
    if needs_linkmatch:
        lines.append(f"No email on file, add via LinkMatch: {len(needs_linkmatch)}")
        for n, c, url in needs_linkmatch:
            lines.append(f"  - {n} ({c}): {url}" if url else f"  - {n} ({c})")
        lines.append("")
    if pool_size < batch_size:
        lines.append(f"NOTE: only {pool_size} unsurfaced leads with a usable score remained in the "
                     f"pool this month (target batch size was {batch_size}). Time to request a "
                     f"fresh LinkedIn export with newer connections, or revisit the scoring thresholds.")
        lines.append("")
    if errors:
        lines.append("ERRORS during this run:")
        for e in errors:
            lines.append(f"  - {e}")
        lines.append("")
    if not new_leads and not flagged_contacts and not errors:
        lines.append("No leads were found or processed this run. Check the CSV input and scoring "
                     "criteria if this is unexpected.")

    body = "\n".join(lines)
    print(body)

    log_path = LOG_DIR / f"run_{today}.txt"
    log_path.write_text(body, encoding="utf-8")
    print(f"\nSummary saved to {log_path}")

    if dry_run:
        print(f"[DRY RUN] Would email this summary to: {', '.join(recipients) or '(no recipients configured)'}")
        return

    if not recipients:
        print("WARNING: MONTHLY_IMPORT_RECIPIENTS is not set in the .env -- no summary email sent.")
        return

    try:
        email_body = re.sub(r"(https?://\S+)", r'<a href="\1">\1</a>', body)
        client.send_mail(recipients, f"Monthly Lead Scorer Run -- {today}", email_body)
        print(f"Summary emailed to: {', '.join(recipients)}")
    except Exception as e:
        print(f"Could not send email automatically ({type(e).__name__}: {e}). "
              f"Summary is saved at {log_path}.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to LinkedIn connections CSV export")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true",
                        help="Read-only: score and check duplicates but do not create leads, "
                             "save state, or send email")
    args = parser.parse_args()

    load_dotenv(ENV_PATH)
    client = ZohoClient()
    errors = []

    # Union of local state and CRM-stamped leads, so a lost local file
    # never causes the same lead to be surfaced twice.
    surfaced = load_surfaced_local()
    try:
        surfaced |= client.fetch_surfaced_from_crm()
    except Exception as e:
        errors.append(f"Could not read surfaced leads from CRM, using local state only: {e}")

    scored = []
    for name, company, title, email, profile_url in read_connections(args.csv):
        key = lead_key(name, company)
        if key in surfaced:
            continue
        s = score_row(company, title)
        if s <= 0:
            continue
        scored.append((name, company, title, email, profile_url, s, key))

    scored.sort(key=lambda x: x[5], reverse=True)

    new_leads = []
    flagged_contacts = []
    needs_linkmatch = []  # created leads with no email -- [YOUR_ALIAS] adds email via LinkMatch manually
    backfill_log = []
    pending_skips = []
    batch_date = date.today().isoformat()
    pool_size = 0

    # Single pass over the full sorted candidate pool: keep pulling the next
    # highest-scoring unmatched contact until the batch is full of net-new
    # leads, or the pool runs out. Each candidate is examined exactly once,
    # so a contact flagged as already-in-CRM can never later be reconsidered
    # as its own backfill.
    for name, company, title, email, profile_url, s, key in scored:
        if len(new_leads) >= args.batch_size:
            break
        pool_size += 1

        try:
            exists = client.find_existing_lead_or_contact(name, company)
        except Exception as e:
            errors.append(f"Lookup failed for {name} ({company}): {e}")
            continue

        if exists:
            flagged_contacts.append((name, company, s))
            pending_skips.append(name)
            backfill_log.append(f"SKIP (already in CRM): {name} ({company}) -- score {s}")
            surfaced.add(key)
            continue

        if args.dry_run:
            print(f"[DRY RUN] Would create Lead: {name} @ {company} (score {s})"
                  f"{'' if email else ' -- NO EMAIL, would need LinkMatch'}")
        else:
            try:
                client.create_lead(name, company, title, s, batch_date, email)
            except Exception as e:
                errors.append(f"Create failed for {name} ({company}): {e}")
                continue

        new_leads.append((name, company, s))
        if not email:
            needs_linkmatch.append((name, company, profile_url))
        if pending_skips:
            replaced = pending_skips.pop(0)
            backfill_log.append(f"BACKFILL: replaced {replaced} (already in CRM) with {name}, score {s}")
        else:
            backfill_log.append(f"ACCEPT: {name} ({company}) -- score {s}")
        surfaced.add(key)

    if backfill_log:
        print("\n--- Selection / backfill log ---")
        for line in backfill_log:
            print(line)
        print("---------------------------------\n")

    if not args.dry_run:
        save_surfaced_local(surfaced)

    send_summary_email(client, new_leads, flagged_contacts,
                       args.batch_size, pool_size, errors, args.dry_run,
                       needs_linkmatch)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()

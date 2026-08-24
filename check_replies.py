#!/usr/bin/env python3
"""
Scans Gmail via IMAP for replies from contacts already marked Status=Sent,
and flags contacts.csv rows with Response=Replied when a message from that
contact's email arrives after their Date Contacted. Detection only — it
does not judge whether the reply is positive/negative, that's still a
manual call (fill in Positive / Negative / Referral Given yourself once
you've read it; the dashboard treats any non-blank Response as "Replied").

Required environment variables (set as GitHub Actions secrets):
  GMAIL_ADDRESS        - the Gmail address you're sending from
  GMAIL_APP_PASSWORD   - a Gmail App Password (same one used for sending)
"""

import os
import csv
import imaplib
import email
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime

CSV_PATH = os.environ.get("CONTACTS_CSV", "contacts.csv")
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def main():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    fieldnames = list(rows[0].keys())

    pending = [
        r for r in rows
        if (r.get("Status") or "").strip() == "Sent"
        and not (r.get("Response") or "").strip()
        and parse_date(r.get("Date Contacted"))
    ]

    if not pending:
        print("No sent-but-unanswered contacts to check.")
        return

    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("Missing GMAIL_ADDRESS / GMAIL_APP_PASSWORD - skipping reply check.")
        return

    earliest = min(parse_date(r["Date Contacted"]) for r in pending)
    since_str = earliest.strftime("%d-%b-%Y")

    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

    status, _ = imap.select('"[Gmail]/All Mail"', readonly=True)
    if status != "OK":
        imap.select("INBOX", readonly=True)

    status, data = imap.search(None, f'(SINCE "{since_str}")')
    ids = data[0].split() if status == "OK" and data and data[0] else []
    print(f"Scanning {len(ids)} messages since {since_str}...")

    latest_by_sender = {}
    for msg_id in ids:
        status, msg_data = imap.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM DATE)])")
        if status != "OK" or not msg_data or not msg_data[0]:
            continue
        header = email.message_from_bytes(msg_data[0][1])
        _, sender = parseaddr(header.get("From", ""))
        sender = sender.lower().strip()
        if not sender:
            continue
        try:
            msg_date = parsedate_to_datetime(header.get("Date")).date()
        except (TypeError, ValueError):
            continue
        if sender not in latest_by_sender or msg_date > latest_by_sender[sender]:
            latest_by_sender[sender] = msg_date

    imap.logout()

    updated = 0
    for row in pending:
        contact_email = (row.get("Email") or "").strip().lower()
        contacted = parse_date(row["Date Contacted"])
        reply_date = latest_by_sender.get(contact_email)
        if reply_date and contacted and reply_date >= contacted:
            row["Response"] = "Replied"
            updated += 1

    if updated:
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

    print(f"Detected {updated} new reply(ies).")


if __name__ == "__main__":
    main()

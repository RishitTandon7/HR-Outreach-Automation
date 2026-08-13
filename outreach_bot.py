#!/usr/bin/env python3
"""
Outreach bot — sends personalized cold emails to HR contacts from contacts.csv,
updates the tracker in place, and stops once the hourly BATCH_SIZE is hit.

Designed to be triggered once per hour by GitHub Actions (see
.github/workflows/outreach.yml). Each run:
  1. Loads contacts.csv
  2. Picks the next BATCH_SIZE rows where Status is empty (already sorted by
     priority tier, so Tier 1 always goes first)
  3. Asks Gemini to classify the company into one of a fixed set of
     categories, then picks the matching hand-written hook line for it
  4. Sends the email via Gmail SMTP with your resume attached
  5. Writes Status=Sent, Date Contacted, and a Follow-up Date (+6 days) back
     into contacts.csv, then commits the file (done by the workflow, not here)

Required environment variables (set as GitHub Actions secrets):
  GMAIL_ADDRESS        - the Gmail address you're sending from
  GMAIL_APP_PASSWORD   - a Gmail App Password (not your normal password)
  GEMINI_API_KEYS      - comma-separated list of Gemini API keys to rotate through
  RESUME_PATH          - path to your resume PDF in the repo (e.g. resume.pdf)

Optional:
  BATCH_SIZE           - contacts to send this run (default 10)
  DRY_RUN              - if "true", generates + prints emails but does not send
"""

import os
import re
import csv
import time
import random
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage
import urllib.request
import json

CSV_PATH = os.environ.get("CONTACTS_CSV", "contacts.csv")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "10"))
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
RESUME_PATH = os.environ.get("RESUME_PATH", "resume.pdf")

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
GEMINI_API_KEYS = [k.strip() for k in re.split(r"[,\s]+", os.environ.get("GEMINI_API_KEYS", "")) if k.strip()]

YOUR_NAME = "Rishit"
YOUR_PHONE = "+91 7394865520"
YOUR_LINKEDIN = "linkedin.com/in/rishit-tandon-928661287"
YOUR_GITHUB = "github.com/RishitTandon7"
YOUR_PORTFOLIO = "portfolio.rishit.site"

HIGHLIGHTS = (
    "12+ hackathon wins (incl. 1st at RoboRoarZ Singapore 2024), SDE "
    "internship at DGTL Innovations, 80+ public repos across ML/full-stack/robotics."
)

EMAIL_BODY_TEMPLATE = """Hi {first_name},

I'm {your_name}, a final-year CS student at SRM, currently looking for full-time AI/ML or SDE roles. {hook}

Quick highlights: {highlights}

Resume attached — open to a quick call, or happy to be pointed to the right person on the team.

Best,
{your_name}
{your_phone} | {your_linkedin} | {your_github} | {your_portfolio}"""

SUBJECT_TEMPLATE = "Final-year SDE/ML engineer — {company}"

# Curated hook lines, one per category — these are fixed, hand-written text.
# Gemini is only ever asked to classify the company into one of these
# categories, never to write prose, so the sentence that actually goes out
# is always exactly what's below.
HOOK_BANK = {
    "fintech": "I built Agent Marketplace, a Razorpay + AWS-integrated platform, and run a live payments side business.",
    "infra": "I designed QML·PLACE, a quantum ML system for VLSI placement showing 8-15% gains over OpenROAD.",
    "consumer": "I built SplitFair, a UPI-integrated expense-splitting app with a live React Native release.",
    "robotics": "I led Arclyth, a drone swarm system that won SEISMO HACK 1.0.",
    "ai": "I built DocMind, a Graph RAG platform using LangGraph and Neo4j.",
    "climate": "I built a satellite-based flood early-warning pipeline as a research intern at SRM x NIDM.",
}
DEFAULT_HOOK = "I'd love the chance to bring that same hands-on, ship-fast approach to {company}'s engineering team."


# Only models with nonzero RPM quota on the account's AI Studio rate-limit
# page — models showing 0/0 there aren't enabled for this account/tier.
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
]
MAX_GEMINI_ATTEMPTS = 12


def classify_company_category(company, title):
    """Ask Gemini to classify the company into one of HOOK_BANK's categories
    (never to write prose — the actual hook sentence sent is always the
    fixed, hand-written text in HOOK_BANK). Rotates across both API keys
    and models to spread load and dodge per-model rate limits. Returns None
    if every attempt fails, no keys are configured, or the reply doesn't
    match a known category."""
    if not GEMINI_API_KEYS:
        return None

    categories = list(HOOK_BANK.keys())
    prompt = (
        f"Classify the company '{company}' (a contact there has the title "
        f"'{title}') into exactly ONE of these categories based on its "
        f"primary business: {', '.join(categories)}, other. "
        f"Reply with only the single category word, nothing else."
    )

    attempts = [(key, model) for key in GEMINI_API_KEYS for model in GEMINI_MODELS]
    random.shuffle(attempts)
    for key, model in attempts[:MAX_GEMINI_ATTEMPTS]:
        try:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={key}"
            )
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}]
            }).encode()
            req = urllib.request.Request(
                url, data=payload, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
            for category in categories:
                if category in text:
                    return category
            return None
        except Exception as e:
            print(f"  [gemini key ...{key[-4:]} / {model} failed: {e}]")
            continue
    return None


def pick_hook(company, title):
    category = classify_company_category(company, title)
    if category and category in HOOK_BANK:
        return HOOK_BANK[category]
    return DEFAULT_HOOK.format(company=company)


def send_email(to_email, subject, body, resume_path):
    if DRY_RUN:
        print(f"  [DRY RUN] Would send to {to_email}\n---\n{body}\n---")
        return True
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("  Missing GMAIL_ADDRESS / GMAIL_APP_PASSWORD — skipping send.")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email
    msg.set_content(body)

    if os.path.exists(resume_path):
        with open(resume_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="pdf",
                filename=os.path.basename(resume_path),
            )

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"  Send failed for {to_email}: {e}")
        return False


def main():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

    pending = [r for r in rows if not r.get("Status", "").strip()]
    print(f"Pending contacts: {len(pending)} / {len(rows)}")

    batch = pending[:BATCH_SIZE]
    if not batch:
        print("No pending contacts left. All done!")
        return

    sent_count = 0
    for row in batch:
        company = row["Company"]
        title = row["Title"]
        name = row["Name"]
        email = row["Email"]
        first_name = name.split()[0] if name else "there"

        print(f"-> {name} ({title}) at {company} <{email}>")
        hook = pick_hook(company, title)

        body = EMAIL_BODY_TEMPLATE.format(
            first_name=first_name,
            your_name=YOUR_NAME,
            hook=hook,
            highlights=HIGHLIGHTS,
            your_phone=YOUR_PHONE,
            your_linkedin=YOUR_LINKEDIN,
            your_github=YOUR_GITHUB,
            your_portfolio=YOUR_PORTFOLIO,
        )
        subject = SUBJECT_TEMPLATE.format(company=company)

        ok = send_email(email, subject, body, RESUME_PATH)

        if DRY_RUN:
            # Never mutate contacts.csv during a dry run — leave Status
            # blank so a real run still picks these same contacts up.
            if ok:
                sent_count += 1
        elif ok:
            row["Status"] = "Sent"
            row["Date Contacted"] = datetime.now().strftime("%Y-%m-%d")
            row["Follow-up Date"] = (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d")
            sent_count += 1
        else:
            row["Status"] = "Bounced"

        # gentle pacing between sends within the batch (avoid spam-pattern bursts)
        time.sleep(random.uniform(3, 8))

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Done. Sent {sent_count}/{len(batch)} this run.")


if __name__ == "__main__":
    main()

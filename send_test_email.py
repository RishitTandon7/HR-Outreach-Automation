#!/usr/bin/env python3
"""
Sends a single test email to verify the Gmail SMTP + resume attachment
pipeline works, completely separate from contacts.csv and the real
outreach batch logic. Never touches contacts.csv.

Required environment variables (set as GitHub Actions secrets):
  GMAIL_ADDRESS        - the Gmail address you're sending from
  GMAIL_APP_PASSWORD   - a Gmail App Password (not your normal password)

Optional:
  TEST_TO       - address to send the test email to (default kingrishit1@gmail.com)
  RESUME_PATH   - path to resume PDF to attach (default resume.pdf)
  DRY_RUN       - if "true", prints the email instead of sending it
"""

import os
import ssl
import smtplib
from email.message import EmailMessage

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
TEST_TO = os.environ.get("TEST_TO", "kingrishit1@gmail.com")
RESUME_PATH = os.environ.get("RESUME_PATH", "resume.pdf")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

SUBJECT = "Outreach bot test send"
BODY = (
    "This is a test email from the HR outreach bot's send pipeline.\n\n"
    "If you're reading this in your inbox with the resume attached, "
    "Gmail SMTP + the app password + the attachment step all work.\n\n"
    "No HR contacts were involved in sending this."
)


def main():
    print(f"Test send -> {TEST_TO}")

    if DRY_RUN:
        print(f"[DRY RUN] Would send to {TEST_TO}\n---\n{BODY}\n---")
        return

    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        raise SystemExit("Missing GMAIL_ADDRESS / GMAIL_APP_PASSWORD secrets.")

    msg = EmailMessage()
    msg["Subject"] = SUBJECT
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = TEST_TO
    msg.set_content(BODY)

    if os.path.exists(RESUME_PATH):
        with open(RESUME_PATH, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="pdf",
                filename=os.path.basename(RESUME_PATH),
            )
        print(f"Attached {RESUME_PATH}")
    else:
        print(f"No resume found at {RESUME_PATH} — sending without attachment.")

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)

    print(f"Sent test email to {TEST_TO}")


if __name__ == "__main__":
    main()

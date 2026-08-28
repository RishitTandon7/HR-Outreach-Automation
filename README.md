# HR Outreach Bot

Sends personalized cold emails to your HR contact list, 10/hour, 9am-7pm IST,
every day — clears all 1,841 contacts in ~18-19 days, inside your 3-week window.

## Setup (one-time)

1. Create a **new private GitHub repo** and push these files:
   - `outreach_bot.py`
   - `contacts.csv` (your tracker — already sorted Tier 1 → Tier 2 → Tier 3)
   - `.github/workflows/outreach.yml`
   - `resume.pdf` (your resume — gets attached to every email)

2. Get a **Gmail App Password**:
   Google Account → Security → 2-Step Verification (must be on) → App Passwords
   → generate one for "Mail". Use this, NOT your normal Gmail password.

3. Add these as **repo secrets** (Settings → Secrets and variables → Actions):
   | Secret | Value |
   |---|---|
   | `GMAIL_ADDRESS` | the Gmail address you're sending from |
   | `GMAIL_APP_PASSWORD` | the app password from step 2 |
   | `GEMINI_API_KEYS` | your rotating keys, comma-separated: `key1,key2,key3,...` |

4. Test it first with a dry run before letting it send anything for real:
   Actions tab → "HR Outreach Bot" → "Run workflow" → set `dry_run` to `true`.
   Check the logs — it will print the generated emails without sending.

5. Once you're happy with the output, the scheduled cron will pick it up
   automatically and start sending 10/hour during business hours. No further
   action needed — just check in on `contacts.csv` periodically.

## Checking progress

`contacts.csv` is the single source of truth. After each run:
- `Status` = `Sent` / `Bounced` / (blank = not reached yet)
- `Date Contacted` and `Follow-up Date` are filled in automatically

Pull the repo locally anytime to see where things stand, or open it on GitHub.

## Follow-ups

This bot only handles the *first* send. For the 5-7 day follow-up pass, filter
`contacts.csv` for `Status = Sent` and `Response` still blank — those are your
follow-up list. (A follow-up mode can be added to the script later if you want
it automated too.)

## Safety notes

- 10/hour x ~10hrs/day ≈ 100/day, well under Gmail's ~500/day limit for a
  regular account — you won't get flagged for volume.
- The bot paces sends with a random 3-8 second gap within each batch, and only
  fires within business hours, so it doesn't look like a 3am spam blast.
- If a lot of `Bounced` shows up, check your Gmail App Password / SMTP setup
  before re-running — it likely means auth failed, not that the emails are bad.
- Gemini calls fail silently to a generic personalization line if all keys are
  rate-limited, so a run never crashes — worst case you get a slightly
  less-personalized email, never a skipped contact.

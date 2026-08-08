#!/usr/bin/env python3
"""
Generates dashboard.html from contacts.csv — a static, self-contained report
showing how many contacts were sent, replied, ghosted, bounced, or not yet
reached. Run this locally any time, or let the GitHub Actions workflow
regenerate it automatically after every outreach batch.

Usage:
    python generate_dashboard.py [contacts.csv] [dashboard.html]

Definitions:
    Sent          - Status == "Sent"
    Replied       - Response is filled in (Positive / Negative / Referral Given)
    Ghosted       - Status == "Sent", Response still blank, AND today's date
                    is past the Follow-up Date (i.e. the 6-day window lapsed
                    with no reply)
    Awaiting reply - Status == "Sent", Response blank, follow-up date not yet
                    reached — still in the normal waiting window, not ghosted
    Bounced       - Status == "Bounced"
    Not started   - Status blank
"""

import csv
import sys
import json
from datetime import datetime
from collections import Counter, defaultdict

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "contacts.csv"
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else "dashboard.html"

TODAY = datetime.now().date()


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def classify(row):
    status = (row.get("Status") or "").strip()
    response = (row.get("Response") or "").strip()
    followup = parse_date(row.get("Follow-up Date"))

    if status == "Bounced":
        return "Bounced"
    if status != "Sent":
        return "Not started"
    if response:
        return "Replied"
    if followup and TODAY > followup:
        return "Ghosted"
    return "Awaiting reply"


def main():
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    bucket_counts = Counter()
    tier_bucket = defaultdict(lambda: Counter())
    response_breakdown = Counter()
    recent_sent = []

    for row in rows:
        bucket = classify(row)
        bucket_counts[bucket] += 1
        tier = (row.get("Tier") or "Unknown").strip()
        tier_bucket[tier][bucket] += 1

        resp = (row.get("Response") or "").strip()
        if resp:
            response_breakdown[resp] += 1

        if (row.get("Status") or "").strip() == "Sent":
            recent_sent.append(row)

    recent_sent.sort(key=lambda r: r.get("Date Contacted") or "", reverse=True)
    recent_sent = recent_sent[:15]

    buckets = ["Sent", "Replied", "Awaiting reply", "Ghosted", "Bounced", "Not started"]
    # "Sent" overlaps with Replied/Awaiting/Ghosted conceptually — compute a
    # true "ever sent" count separately for the headline card.
    ever_sent = sum(1 for row in rows if (row.get("Status") or "").strip() in ("Sent", "Bounced"))
    replied = bucket_counts["Replied"]
    ghosted = bucket_counts["Ghosted"]
    awaiting = bucket_counts["Awaiting reply"]
    bounced = bucket_counts["Bounced"]
    not_started = bucket_counts["Not started"]

    reply_rate = (replied / ever_sent * 100) if ever_sent else 0
    ghost_rate = (ghosted / ever_sent * 100) if ever_sent else 0

    tier_rows_html = ""
    for tier in sorted(tier_bucket.keys()):
        c = tier_bucket[tier]
        tier_total = sum(c.values())
        tier_rows_html += f"""
        <tr>
          <td>{tier}</td>
          <td>{tier_total}</td>
          <td>{c['Replied']}</td>
          <td>{c['Awaiting reply']}</td>
          <td>{c['Ghosted']}</td>
          <td>{c['Bounced']}</td>
          <td>{c['Not started']}</td>
        </tr>"""

    recent_rows_html = ""
    for row in recent_sent:
        status_badge = classify(row)
        recent_rows_html += f"""
        <tr>
          <td>{row.get('Company','')}</td>
          <td>{row.get('Name','')}</td>
          <td>{row.get('Date Contacted','')}</td>
          <td><span class="badge badge-{status_badge.lower().replace(' ', '-')}">{status_badge}</span></td>
        </tr>"""

    chart_data = json.dumps({
        "labels": ["Replied", "Awaiting reply", "Ghosted", "Bounced", "Not started"],
        "values": [replied, awaiting, ghosted, bounced, not_started],
    })

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Outreach Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117; --card: #171a23; --border: #2a2e3a;
    --text: #e5e7eb; --muted: #9ca3af;
    --blue: #3b82f6; --green: #22c55e; --yellow: #eab308;
    --red: #ef4444; --gray: #6b7280;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    background: var(--bg); color: var(--text);
    font-family: -apple-system, Segoe UI, Arial, sans-serif;
    margin: 0; padding: 32px;
  }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .subtitle {{ color: var(--muted); font-size: 13px; margin-bottom: 28px; }}
  .cards {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px; margin-bottom: 32px;
  }}
  .card {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px 18px;
  }}
  .card .num {{ font-size: 28px; font-weight: 700; }}
  .card .label {{ color: var(--muted); font-size: 12.5px; margin-top: 4px; }}
  .card.blue .num {{ color: var(--blue); }}
  .card.green .num {{ color: var(--green); }}
  .card.yellow .num {{ color: var(--yellow); }}
  .card.red .num {{ color: var(--red); }}
  .card.gray .num {{ color: var(--gray); }}
  .grid2 {{ display: grid; grid-template-columns: 1.1fr 1fr; gap: 24px; margin-bottom: 32px; }}
  @media (max-width: 900px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
  .panel {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 18px;
  }}
  .panel h2 {{ font-size: 14px; margin: 0 0 14px 0; color: var(--text); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  th {{ text-align: left; color: var(--muted); font-weight: 600; padding: 6px 8px; border-bottom: 1px solid var(--border); }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #1f2330; }}
  .badge {{ padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }}
  .badge-replied {{ background: rgba(34,197,94,0.15); color: var(--green); }}
  .badge-awaiting-reply {{ background: rgba(59,130,246,0.15); color: var(--blue); }}
  .badge-ghosted {{ background: rgba(234,179,8,0.15); color: var(--yellow); }}
  .badge-bounced {{ background: rgba(239,68,68,0.15); color: var(--red); }}
  .badge-not-started {{ background: rgba(107,114,128,0.15); color: var(--gray); }}
  .updated {{ color: var(--muted); font-size: 11.5px; margin-top: 24px; }}
</style>
</head>
<body>
  <h1>HR Outreach Dashboard</h1>
  <div class="subtitle">Generated {TODAY.isoformat()} &middot; {total} total contacts</div>

  <div class="cards">
    <div class="card blue"><div class="num">{ever_sent}</div><div class="label">Sent</div></div>
    <div class="card green"><div class="num">{replied}</div><div class="label">Replied ({reply_rate:.1f}%)</div></div>
    <div class="card yellow"><div class="num">{ghosted}</div><div class="label">Ghosted ({ghost_rate:.1f}%)</div></div>
    <div class="card blue"><div class="num">{awaiting}</div><div class="label">Awaiting reply</div></div>
    <div class="card red"><div class="num">{bounced}</div><div class="label">Bounced</div></div>
    <div class="card gray"><div class="num">{not_started}</div><div class="label">Not started yet</div></div>
  </div>

  <div class="grid2">
    <div class="panel">
      <h2>By tier</h2>
      <table>
        <thead>
          <tr><th>Tier</th><th>Contacted</th><th>Replied</th><th>Awaiting</th><th>Ghosted</th><th>Bounced</th><th>Not started</th></tr>
        </thead>
        <tbody>{tier_rows_html}
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h2>Outcome breakdown</h2>
      <canvas id="outcomeChart" height="220"></canvas>
    </div>
  </div>

  <div class="panel">
    <h2>Most recent sends</h2>
    <table>
      <thead><tr><th>Company</th><th>Contact</th><th>Date</th><th>Status</th></tr></thead>
      <tbody>{recent_rows_html if recent_rows_html else '<tr><td colspan="4" style="color:var(--muted)">No sends yet.</td></tr>'}
      </tbody>
    </table>
  </div>

  <div class="updated">Regenerate this file any time by running <code>python generate_dashboard.py</code> after the bot updates contacts.csv.</div>

<script>
const data = {chart_data};
new Chart(document.getElementById('outcomeChart'), {{
  type: 'doughnut',
  data: {{
    labels: data.labels,
    datasets: [{{
      data: data.values,
      backgroundColor: ['#22c55e', '#3b82f6', '#eab308', '#ef4444', '#6b7280'],
      borderColor: '#171a23',
      borderWidth: 2,
    }}]
  }},
  options: {{
    plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#e5e7eb', font: {{ size: 11 }} }} }} }}
  }}
}});
</script>
</body>
</html>"""

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {OUT_PATH} — Sent {ever_sent}, Replied {replied}, Ghosted {ghosted}, Awaiting {awaiting}, Bounced {bounced}, Not started {not_started}")


if __name__ == "__main__":
    main()

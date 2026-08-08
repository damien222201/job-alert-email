"""
Daily remote job alert email.

Fetches the latest remote job postings from RemoteOK's public JSON API,
filters for roles matching target keywords (AI Engineer, Software
Engineer, Full-Stack Developer, Data Analyst), skips postings already
emailed before (tracked in seen_jobs.json in this repo), and emails
the new matches via SMTP.

Environment variables (set as GitHub Actions secrets):
    SMTP_HOST       e.g. smtp.gmail.com
    SMTP_PORT       e.g. 587
    SMTP_USER       the Gmail address sending the email
    SMTP_PASSWORD   a Gmail App Password (NOT your normal password)
    EMAIL_TO        address(es) to send the report to (comma-separated ok)
"""

import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

KEYWORDS = [
    "ai engineer",
    "software engineer",
    "full-stack developer",
    "full stack developer",
    "data analyst",
]

API_URL = "https://remoteok.com/api"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JobAlertBot/1.0; +https://github.com)"}
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_jobs.json")
MAX_SEEN_IDS_KEPT = 1000


def fetch_jobs() -> list:
    resp = requests.get(API_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    # RemoteOK's first array element is a legal/metadata notice, not a job
    return [job for job in data if isinstance(job, dict) and job.get("id")]


def matches_keywords(job: dict) -> bool:
    haystack = " ".join(
        [
            str(job.get("position", "")),
            str(job.get("title", "")),
            " ".join(job.get("tags", []) or []),
        ]
    ).lower()
    return any(kw in haystack for kw in KEYWORDS)


def load_seen_ids() -> set:
    if not os.path.exists(STATE_FILE):
        return set()
    try:
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen_ids(ids: set) -> None:
    trimmed = list(ids)[-MAX_SEEN_IDS_KEPT:]
    with open(STATE_FILE, "w") as f:
        json.dump(trimmed, f)


def clean_html(text: str) -> str:
    return re.sub("<[^<]+?>", "", text or "").strip()


def build_email_body(new_jobs: list) -> tuple[str, str]:
    today = datetime.now(timezone.utc).strftime("%A, %B %d, %Y")

    text_lines = [f"Remote Job Alert — {today}\n"]
    html_cards = []

    for job in new_jobs:
        title = job.get("position") or job.get("title") or "Untitled role"
        company = job.get("company", "Unknown company")
        location = job.get("location") or "Remote (worldwide)"
        url = job.get("url") or f"https://remoteok.com/remote-jobs/{job.get('id')}"
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")
        tags = ", ".join(job.get("tags", []) or [])

        salary_str = ""
        if salary_min and salary_max:
            salary_str = f"${salary_min:,} - ${salary_max:,}"

        text_lines.append(f"{title} @ {company}")
        text_lines.append(f"  Location: {location}")
        if salary_str:
            text_lines.append(f"  Salary: {salary_str}")
        if tags:
            text_lines.append(f"  Tags: {tags}")
        text_lines.append(f"  Apply: {url}\n")

        salary_html = f"<p style='margin:2px 0;color:#1a9c4c;font-size:13px;'>{salary_str}</p>" if salary_str else ""
        tags_html = f"<p style='margin:2px 0;color:#888;font-size:12px;'>{tags}</p>" if tags else ""

        html_cards.append(
            f"""
            <div style="border:1px solid #eee;border-radius:6px;padding:14px;margin-bottom:12px;">
              <p style="margin:0 0 4px 0;font-weight:bold;font-size:15px;">{title}</p>
              <p style="margin:0 0 4px 0;color:#444;">{company} — {location}</p>
              {salary_html}
              {tags_html}
              <a href="{url}" style="display:inline-block;margin-top:8px;color:#fff;background:#2563eb;
                 padding:6px 14px;border-radius:4px;text-decoration:none;font-size:13px;">View & Apply</a>
            </div>
            """
        )

    text_body = "\n".join(text_lines)

    html_body = f"""\
<html>
  <body style="font-family:Arial,sans-serif;background:#f7f7f7;padding:20px;">
    <div style="max-width:560px;margin:auto;background:#fff;border-radius:8px;padding:24px;">
      <h2 style="margin-top:0;">💼 Remote Job Alert</h2>
      <p style="color:#666;margin-top:-10px;">{today} — {len(new_jobs)} new match{'es' if len(new_jobs) != 1 else ''}</p>
      {''.join(html_cards)}
      <p style="color:#999;font-size:12px;margin-top:20px;">Data via RemoteOK (remoteok.com)</p>
    </div>
  </body>
</html>
"""
    return text_body, html_body


def send_email(text_body: str, html_body: str, match_count: int) -> None:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    email_to = os.environ["EMAIL_TO"]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Remote Job Alert — {match_count} new match{'es' if match_count != 1 else ''} — {today}"
    msg["From"] = smtp_user
    msg["To"] = email_to

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, email_to.split(","), msg.as_string())


def main():
    try:
        jobs = fetch_jobs()
    except requests.RequestException as e:
        print(f"Failed to fetch jobs: {e}", file=sys.stderr)
        sys.exit(1)

    seen_ids = load_seen_ids()
    matched = [j for j in jobs if matches_keywords(j)]
    new_jobs = [j for j in matched if str(j["id"]) not in seen_ids]

    # Always update and save state, even if there's nothing new to email —
    # this guarantees seen_jobs.json exists after every run, so the
    # workflow's commit step never fails looking for a missing file.
    seen_ids.update(str(j["id"]) for j in matched)
    save_seen_ids(seen_ids)

    if not new_jobs:
        print("No new matching jobs today — skipping email.")
        return

    text_body, html_body = build_email_body(new_jobs)

    try:
        send_email(text_body, html_body, len(new_jobs))
    except Exception as e:
        print(f"Failed to send email: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Email sent successfully with {len(new_jobs)} new job(s).")


if __name__ == "__main__":
    main()

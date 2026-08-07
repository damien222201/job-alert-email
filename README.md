# Remote Job Alert Email

Sends a daily email at 6:00 AM (WAT) with new remote job postings
matching: **AI Engineer, Software Engineer, Full-Stack Developer,
Data Analyst**. Powered by [RemoteOK's](https://remoteok.com) free
public JSON API (no key needed) and run entirely on GitHub Actions
(no server needed).

Only genuinely **new** postings get emailed — once a job has been
sent to you, it's remembered (`seen_jobs.json`) and won't show up
again even if it's still listed tomorrow. If there are no new matches
on a given day, no email is sent at all (no empty "0 jobs today"
noise).

## Setup

1. **Create a Gmail App Password** (skip if you already have one from
   another project — you can reuse it)
   - Go to your Google Account → Security → 2-Step Verification (must be on)
   - Then Security → App passwords → generate one for "Mail"
   - Copy the 16-character password

2. **Push this repo to GitHub**

3. **Add repository secrets**
   Go to your repo → Settings → Secrets and variables → Actions → New repository secret, and add:

   | Secret name     | Value                                  |
   |-----------------|-----------------------------------------|
   | `SMTP_USER`     | your Gmail address                     |
   | `SMTP_PASSWORD` | the Gmail App Password                 |
   | `EMAIL_TO`      | the email address(es) to send reports to (comma-separated for multiple) |

4. **Set workflow permissions**
   Go to Settings → Actions → General → Workflow permissions → select
   **"Read and write permissions"**. This is required because the
   workflow commits `seen_jobs.json` back to the repo after each run.

5. **Test it manually**
   Go to the "Actions" tab → "Daily Remote Job Alert Email" → "Run workflow"
   to trigger it immediately. The first run will likely email quite a
   few matches at once (everything currently live matching your
   keywords) — after that, you'll only get genuinely new postings.

## Customizing keywords

Edit the `KEYWORDS` list near the top of `main.py` to add or change
target roles. Matching is a simple case-insensitive substring check
against the job title and tags, so keep entries lowercase and
specific enough to avoid false positives (e.g. `"analyst"` alone would
match "Business Analyst", "Data Analyst", etc. — `"data analyst"` is
more precise).

## Schedule

Runs daily at **5:00 AM UTC (6:00 AM WAT)** via the cron in
`.github/workflows/daily-job-alert-email.yml`. Edit the `cron` line
there to change the time — GitHub Actions cron is always in UTC.

## Local testing

```bash
pip install -r requirements.txt
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=you@gmail.com
export SMTP_PASSWORD=your_app_password
export EMAIL_TO=you@gmail.com
python main.py
```

## Notes

- RemoteOK's public feed returns roughly the latest 100 postings
  site-wide, so very old matching jobs (if RemoteOK's feed cycles
  past them before your keywords catch them) may be missed — this is
  a snapshot of what's live and recent, not a full historical search.
- All RemoteOK listings are remote-only by definition, so no extra
  location filtering is needed.

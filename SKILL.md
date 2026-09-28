---
name: linkedin-to-email
description: Turn a CSV of LinkedIn profile URLs into verified work emails through one pay-per-call API, with a per-row cost ledger. Use when the user has a list of LinkedIn URLs (or a CSV with a linkedin_url column) and wants emails found, verified, or priced.
---

# LinkedIn URL to verified email

Runs the whole list through `scripts/enrich.py` in one call. Do not loop over rows yourself with separate tool calls; the script handles concurrency, retries and the ledger, and prints a summary you can read back to the user.

## Setup (once)

- `TREG_TOKEN` must be set in the environment. If it is missing, stop and ask the user to export it. Never print it or write it to a file.
- Python 3.9+, standard library only.

## Input

A CSV with a `linkedin_url` column. `company_domain` is optional; when present the output flags rows where the email domain differs from it (usually a job change).

## Run

```bash
python3 scripts/enrich.py INPUT.csv --out OUTPUT.csv --max-spend 5
```

- `--max-spend` is a hard stop in dollars. Default 5. Ask the user before raising it.
- `--workers` defaults to 5.
- Re-running with the same `--out` skips rows already done, so an interrupted run can resume.

## What it does per row

1. Find the email from the LinkedIn URL. The router tries providers in order and a miss usually costs nothing.
2. Verify, only if an email came back.

It does not scrape the profile first. The finder only needs the URL, and scraping added cost and time without changing the result.

## Output

`OUTPUT.csv` columns: `linkedin_url, email, verify_status, domain_match, find_provider, cost_usd, seconds`.
A `OUTPUT.ledger.jsonl` next to it keeps one line per API call (endpoint, status, cost, provider, call id).

After the run, report the summary block the script prints: rows, emails found, verified, total spend, cost per verified email, wall time. Mention `domain_match = no` rows separately.

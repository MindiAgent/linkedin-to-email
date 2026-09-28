# linkedin-to-email

Claude Code skill that turns a CSV of LinkedIn profile URLs into verified work emails, with a per-row cost ledger.

One `SKILL.md` and one Python script. Standard library only. The script calls [treg.to](https://treg.to), a pay-per-call router in front of email-finder providers. A miss usually costs nothing. You pay for what comes back.

## Install

Drop this folder into `.claude/skills/linkedin-to-email/`, then:

```bash
export TREG_TOKEN=your-token
```

Never commit the token or write it into a file.

## Run

Input CSV needs a `linkedin_url` column. `company_domain` is optional; when it is present, the output flags rows where the email domain does not match (usually a job change).

```bash
python3 scripts/enrich.py INPUT.csv --out OUTPUT.csv --max-spend 5
```

- `--max-spend` is a hard stop in dollars. Default is 5.
- `--workers` defaults to 5.
- Re-running with the same `--out` skips rows already done.

Ask Claude to run the script once over the whole CSV. Do not have it loop over rows with separate tool calls.

## Output

`OUTPUT.csv` columns: `linkedin_url, email, verify_status, domain_match, find_provider, cost_usd, seconds`.

A `OUTPUT.ledger.jsonl` next to it keeps one line per API call.

#!/usr/bin/env python3
"""LinkedIn URL -> work email -> verify, via treg.to. Stdlib only. Resumable. Hard spend cap."""
import argparse, csv, json, os, sys, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://treg.to/call/"
OK_STATUSES = {"ok", "valid"}


def call(endpoint, body, token, timeout=90):
    req = urllib.request.Request(
        BASE + endpoint, data=json.dumps(body).encode(), method="POST",
        headers={"X-Treg-Token": token, "Content-Type": "application/json",
                 "Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    t0 = time.monotonic()
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw, status, h = r.read(), r.status, r.headers
            break
        except urllib.error.HTTPError as e:
            raw, status, h = e.read(), e.code, e.headers
            if status not in (429, 502, 503, 504):
                break
        except Exception as e:  # timeouts, resets
            raw, status, h = b"", 0, {}
        time.sleep(2 * (attempt + 1))
    try:
        body_json = json.loads(raw or b"{}")
    except ValueError:
        body_json = {}
    get = (lambda k: h.get(k)) if h else (lambda k: None)
    return {
        "endpoint": endpoint, "status": status, "ms": int((time.monotonic() - t0) * 1000),
        "cost_micro": int(get("x-treg-cost-micro") or 0), "served_by": get("x-treg-served-by") or "",
        "call_id": get("x-treg-call-id") or "", "output": body_json.get("output") or {},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-spend", type=float, default=5.0)
    ap.add_argument("--workers", type=int, default=5)
    a = ap.parse_args()

    token = os.environ.get("TREG_TOKEN")
    if not token:
        sys.exit("TREG_TOKEN is not set")

    with open(a.input, newline="") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("linkedin_url") or "").strip()]
    cols = ["linkedin_url", "email", "verify_status", "domain_match", "find_provider", "cost_usd", "seconds"]
    done = set()
    if os.path.exists(a.out):
        with open(a.out, newline="") as f:
            done = {r["linkedin_url"] for r in csv.DictReader(f)}
    todo = [r for r in rows if r["linkedin_url"].strip() not in done]
    ledger_path = os.path.splitext(a.out)[0] + ".ledger.jsonl"
    new_file = not os.path.exists(a.out)
    out_f = open(a.out, "a", newline="")
    writer = csv.DictWriter(out_f, fieldnames=cols)
    if new_file:
        writer.writeheader()
    lock, spent, stop = threading.Lock(), [0], threading.Event()

    def log(rec):
        with lock:
            spent[0] += rec["cost_micro"]
            with open(ledger_path, "a") as g:
                g.write(json.dumps({k: v for k, v in rec.items() if k != "output"}) + "\n")
            if spent[0] / 1e6 >= a.max_spend:
                stop.set()

    def one(r):
        if stop.is_set():
            return None
        url, t0 = r["linkedin_url"].strip(), time.monotonic()
        f = call("treg.people.email.find", {"linkedin_url": url}, token); log(f)
        email, vstatus, cost = f["output"].get("email") or "", "", f["cost_micro"]
        if email and not stop.is_set():
            v = call("treg.people.email.verify", {"email": email}, token); log(v)
            vstatus, cost = v["output"].get("status") or "", cost + v["cost_micro"]
        dom = (r.get("company_domain") or "").strip().lower()
        match = "" if not (email and dom) else ("yes" if email.split("@")[-1].lower() == dom else "no")
        return {"linkedin_url": url, "email": email, "verify_status": vstatus, "domain_match": match,
                "find_provider": f["served_by"], "cost_usd": f"{cost/1e6:.4f}",
                "seconds": f"{time.monotonic()-t0:.1f}"}

    t_start = time.monotonic()
    with ThreadPoolExecutor(a.workers) as ex:
        for fut in as_completed([ex.submit(one, r) for r in todo]):
            res = fut.result()
            if res:
                with lock:
                    writer.writerow(res); out_f.flush()
    out_f.close()

    with open(a.out, newline="") as f:
        allrows = list(csv.DictReader(f))
    found = [r for r in allrows if r["email"]]
    ok = [r for r in found if r["verify_status"] in OK_STATUSES]
    total = sum(float(r["cost_usd"]) for r in allrows)
    print(f"rows: {len(allrows)}  found: {len(found)}  verified: {len(ok)}")
    print(f"spend: ${total:.2f}  per verified email: ${total/max(len(ok),1):.4f}")
    print(f"wall time this run: {time.monotonic()-t_start:.0f}s for {len(todo)} rows")
    print(f"domain mismatches: {sum(r['domain_match']=='no' for r in allrows)}")
    if stop.is_set():
        print(f"STOPPED at --max-spend ${a.max_spend}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Discover the ATS + board slug for every company in config/watchlist.json.

For each company, tries slug guesses (hints + name-derived variants) against
the public job-board APIs of Ashby, Greenhouse, Lever, and SmartRecruiters,
in that order. First hit wins. Writes results back into watchlist.json as
`ats` / `slug` / `job_count` fields, plus a `sample_title` for spot-checking
that the board actually belongs to the right company (generic slugs like
"linear" or "gamma" can collide with an unrelated company's board).

Run:  python3 automation/watchlist_discover.py [--only-missing]
"""

import json
import re
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CONFIG = Path(__file__).resolve().parent / "config" / "watchlist.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
TIMEOUT = 8


def fetch_json(url, _retry=True):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        # 429/5xx may be transient rate limiting — one retry so a real board
        # isn't misclassified and a worse fallback ATS claims the company
        if _retry and e.code in (429, 500, 502, 503):
            import time
            time.sleep(1.5)
            return fetch_json(url, _retry=False)
        return None
    except Exception:
        if _retry:
            import time
            time.sleep(1.0)
            return fetch_json(url, _retry=False)
        return None


def try_ashby(slug):
    data = fetch_json(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        jobs = data["jobs"]
        sample = jobs[0].get("title", "") if jobs else ""
        return {"ats": "ashby", "slug": slug, "job_count": len(jobs), "sample_title": sample}
    return None


def try_greenhouse(slug):
    data = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        jobs = data["jobs"]
        sample = jobs[0].get("title", "") if jobs else ""
        # board endpoint exposes the company display name — grab it for verification
        board = fetch_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}")
        boardname = (board or {}).get("name", "")
        return {"ats": "greenhouse", "slug": slug, "job_count": len(jobs),
                "sample_title": sample, "board_name": boardname}
    return None


def try_lever(slug):
    data = fetch_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    if isinstance(data, list):
        sample = data[0].get("text", "") if data else ""
        return {"ats": "lever", "slug": slug, "job_count": len(data), "sample_title": sample}
    return None


def try_smartrecruiters(slug):
    data = fetch_json(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings")
    if isinstance(data, dict) and "content" in data:
        jobs = data.get("content") or []
        # SmartRecruiters answers 200 + totalFound:0 for ANY slug, even
        # nonexistent companies — only a board with live postings is a real hit
        if data.get("totalFound", 0) == 0:
            return None
        sample = jobs[0].get("name", "") if jobs else ""
        return {"ats": "smartrecruiters", "slug": slug,
                "job_count": data.get("totalFound", len(jobs)), "sample_title": sample}
    return None


PROBES = [try_ashby, try_greenhouse, try_lever, try_smartrecruiters]


def slug_variants(company):
    """hints first (ordered, most-likely first), then name-derived guesses."""
    out = list(company.get("hints", []))
    name = company["name"].lower()
    base = re.sub(r"[^a-z0-9 ]", "", name).strip()
    for v in (base.replace(" ", ""), base.replace(" ", "-"), base.split(" ")[0]):
        if v and v not in out:
            out.append(v)
    return out


def discover_one(company):
    for slug in slug_variants(company):
        for probe in PROBES:
            hit = probe(slug)
            if hit is not None:
                return {**company, **hit}
    return {**company, "ats": "not_found", "slug": "", "job_count": 0, "sample_title": ""}


def main():
    only_missing = "--only-missing" in sys.argv
    cfg = json.loads(CONFIG.read_text())
    companies = cfg["companies"]

    todo = [c for c in companies if not only_missing or c.get("ats") in (None, "", "not_found")]
    done = {c["name"]: c for c in companies if c not in todo}
    print(f"Discovering ATS boards for {len(todo)} companies "
          f"({len(done)} already resolved, skipped)..." if only_missing
          else f"Discovering ATS boards for {len(todo)} companies...")

    results = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(discover_one, c): c["name"] for c in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            results[r["name"]] = r
            mark = "OK " if r["ats"] != "not_found" else "?? "
            print(f"[{i}/{len(todo)}] {mark}{r['name']:<26} {r['ats']:<15} "
                  f"{r['slug']:<24} jobs={r['job_count']}")

    merged = [results.get(c["name"], done.get(c["name"], c)) for c in companies]
    cfg["companies"] = merged
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n")

    found = [c for c in merged if c.get("ats") not in (None, "", "not_found")]
    print(f"\nResolved {len(found)}/{len(merged)} companies.")
    by_ats = {}
    for c in found:
        by_ats[c["ats"]] = by_ats.get(c["ats"], 0) + 1
    for ats, n in sorted(by_ats.items(), key=lambda kv: -kv[1]):
        print(f"  {ats}: {n}")
    missing = [c["name"] for c in merged if c.get("ats") in (None, "", "not_found")]
    if missing:
        print(f"\nNot found ({len(missing)}): {', '.join(missing)}")


if __name__ == "__main__":
    main()

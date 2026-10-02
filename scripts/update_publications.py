#!/usr/bin/env python3
"""Refresh the recent-publications block in README.md.

Source: the public ORCID API (no key needed). Shows the 5 most recent works.
Retracted works are never shown: each DOI is checked against OpenAlex's
is_retracted flag, and titles that mark a retraction/withdrawal are skipped.
If the retraction check cannot run, README.md is left unchanged.
Only the text between <!-- PUBLICATIONS:START --> and <!-- PUBLICATIONS:END --> changes.
Uses the standard library only.
"""
import json
import re
import sys
import urllib.parse
import urllib.request

ORCID_ID = "0000-0001-7493-1914"
README = "README.md"
MAX_ITEMS = 5
START, END = "<!-- PUBLICATIONS:START -->", "<!-- PUBLICATIONS:END -->"
UA = {"User-Agent": "profile-readme-updater"}

# Titles that mark a retracted/withdrawn paper or a retraction notice.
RETRACTED_TITLE = re.compile(
    r"^\W*(retracted|retraction|withdrawn)\b|\[retracted\]|\(retracted\)", re.I
)


def get_json(url, accept=None):
    headers = dict(UA)
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_works():
    return get_json(f"https://pub.orcid.org/v3.0/{ORCID_ID}/works", "application/json")


def parse(data):
    works = []
    for group in data.get("group", []):
        summaries = group.get("work-summary") or []
        if not summaries:
            continue
        w = summaries[0]  # ORCID lists the preferred version first
        title = ((w.get("title") or {}).get("title") or {}).get("value", "").strip()
        if not title:
            continue
        date = w.get("publication-date") or {}
        year = ((date.get("year") or {}) or {}).get("value") or ""
        venue = ((w.get("journal-title") or {}) or {}).get("value") or ""
        doi = ""
        for ext in ((w.get("external-ids") or {}).get("external-id") or []):
            if ext.get("external-id-type") == "doi":
                doi = ext.get("external-id-value", "").strip()
                break
        works.append({"title": title, "year": year, "venue": venue, "doi": doi})
    works.sort(key=lambda x: x["year"] or "0", reverse=True)
    return works


def drop_retracted(works):
    """Drop retracted works. Raises if the OpenAlex check fails."""
    works = [w for w in works if not RETRACTED_TITLE.search(w["title"])]
    dois = sorted({w["doi"].lower() for w in works if w["doi"]})
    retracted = set()
    for i in range(0, len(dois), 40):
        chunk = dois[i : i + 40]
        params = {
            "filter": "doi:" + "|".join(f"https://doi.org/{d}" for d in chunk),
            "per-page": "50",
            "select": "doi,is_retracted",
        }
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params, safe=":/|,")
        for r in get_json(url).get("results", []):
            if r.get("is_retracted") and r.get("doi"):
                retracted.add(r["doi"].lower().replace("https://doi.org/", ""))
    return [w for w in works if w["doi"].lower() not in retracted]


def render(works):
    lines = []
    for w in works[:MAX_ITEMS]:
        head = f"[{w['title']}](https://doi.org/{w['doi']})" if w["doi"] else w["title"]
        tail = ", ".join(p for p in (w["venue"], w["year"]) if p)
        lines.append(f"- {head}" + (f" — {tail}" if tail else ""))
    lines += ["", "<sub>Most recent works from ORCID · updated automatically</sub>"]
    return "\n".join(lines)


def main():
    try:
        works = drop_retracted(parse(fetch_works()))
    except Exception as exc:  # network error, rate limit, bad JSON
        print(f"Could not fetch or verify works ({exc}); leaving README unchanged.")
        return 0
    if not works:
        print("No public works returned; leaving README unchanged.")
        return 0
    text = open(README, encoding="utf-8").read()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        print("Markers not found in README.md", file=sys.stderr)
        return 1
    new = pattern.sub(f"{START}\n{render(works)}\n{END}", text)
    if new != text:
        open(README, "w", encoding="utf-8").write(new)
        print("README updated.")
    else:
        print("No changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

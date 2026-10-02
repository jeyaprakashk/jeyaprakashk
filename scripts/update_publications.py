#!/usr/bin/env python3
"""Refresh the publications block in README.md from the public ORCID API.

Only the text between <!-- PUBLICATIONS:START --> and <!-- PUBLICATIONS:END -->
is rewritten. Uses the standard library only.
"""
import json
import re
import sys
import urllib.request

ORCID_ID = "0000-0001-7493-1914"
README = "README.md"
MAX_ITEMS = 8
START, END = "<!-- PUBLICATIONS:START -->", "<!-- PUBLICATIONS:END -->"


def fetch_works():
    req = urllib.request.Request(
        f"https://pub.orcid.org/v3.0/{ORCID_ID}/works",
        headers={"Accept": "application/json", "User-Agent": "profile-readme-updater"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


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


def render(works):
    lines = []
    for w in works[:MAX_ITEMS]:
        title = f"[{w['title']}](https://doi.org/{w['doi']})" if w["doi"] else w["title"]
        tail = ", ".join(p for p in (w["venue"], w["year"]) if p)
        lines.append(f"- {title}" + (f" — {tail}" if tail else ""))
    total = len(works)
    lines.append("")
    lines.append(f"<sub>{total} works on ORCID · updated automatically</sub>")
    return "\n".join(lines)


def main():
    works = parse(fetch_works())
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

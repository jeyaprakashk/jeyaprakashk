#!/usr/bin/env python3
"""Refresh the publications block in README.md.

Preferred: the 5 most-cited works from OpenAlex (free, no key, ORCID-linked).
Fallback: the 5 most recent works from ORCID, used when the citation data
looks unreliable (request fails, too few works, or too few with citations).
Only the text between <!-- SELECTED:START --> and <!-- SELECTED:END --> changes.
"""
import json
import re
import sys
import urllib.parse
import urllib.request

import update_publications as orcid  # ORCID fetch/parse helpers (same folder)

ORCID_URL = "https://orcid.org/0000-0001-7493-1914"
README = "README.md"
TOP_N = 5
MIN_CITED = 3  # at least this many of the top works must have >= 1 citation
START, END = "<!-- SELECTED:START -->", "<!-- SELECTED:END -->"


def fetch_openalex():
    params = {
        "filter": f"author.orcid:{ORCID_URL},type:article|review|book-chapter|book",
        "sort": "cited_by_count:desc",
        "per-page": "25",
        "select": "title,publication_year,cited_by_count,doi,primary_location",
    }
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params, safe=":/|,")
    req = urllib.request.Request(url, headers={"User-Agent": "profile-readme-updater"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp).get("results", [])


def norm(title):
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def pick(results):
    seen, out = set(), []
    for w in results:
        key = norm(w.get("title"))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(w)
        if len(out) == TOP_N:
            break
    return out


def citations_reliable(works):
    if len(works) < TOP_N:
        return False
    return sum(1 for w in works if (w.get("cited_by_count") or 0) > 0) >= MIN_CITED


def render_cited(works):
    lines = ["**Most cited**", ""]
    for w in works:
        title = w["title"].strip()
        doi = w.get("doi")  # full https://doi.org/... URL
        head = f"[{title}]({doi})" if doi else title
        src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        tail = ", ".join(p for p in (src, str(w.get("publication_year") or "")) if p)
        lines.append(f"- {head}" + (f" — {tail}" if tail else "") + f" · {w.get('cited_by_count', 0)} citations")
    lines += ["", "<sub>Ranked by citation count (OpenAlex) · updated automatically</sub>"]
    return "\n".join(lines)


def render_recent(works):
    lines = ["**Recent**", ""]
    for w in works[:TOP_N]:
        head = f"[{w['title']}](https://doi.org/{w['doi']})" if w["doi"] else w["title"]
        tail = ", ".join(p for p in (w["venue"], w["year"]) if p)
        lines.append(f"- {head}" + (f" — {tail}" if tail else ""))
    lines += ["", "<sub>Most recent works from ORCID · updated automatically</sub>"]
    return "\n".join(lines)


def build_block():
    try:
        cited = pick(fetch_openalex())
        if citations_reliable(cited):
            print("Using OpenAlex most-cited list.")
            return render_cited(cited)
        print("Citation data not reliable enough; falling back to recent works.")
    except Exception as exc:  # network error, rate limit, bad JSON
        print(f"OpenAlex unavailable ({exc}); falling back to recent works.")
    try:
        recent = orcid.parse(orcid.fetch_works())
    except Exception as exc:
        print(f"ORCID unavailable too ({exc}); leaving README unchanged.")
        return None
    return render_recent(recent) if recent else None


def main():
    block = build_block()
    if not block:
        return 0
    text = open(README, encoding="utf-8").read()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        print("Markers not found in README.md", file=sys.stderr)
        return 1
    new = pattern.sub(f"{START}\n{block}\n{END}", text)
    if new != text:
        open(README, "w", encoding="utf-8").write(new)
        print("README updated.")
    else:
        print("No changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Generate assets/stats.svg: a self-hosted activity card for the profile README.

GitHub numbers come from the GitHub GraphQL API (GITHUB_TOKEN, supplied
automatically inside GitHub Actions). The publication count comes from the
public ORCID API with retracted works removed (see update_publications.py).
If GitHub cannot be reached, the existing card is left untouched.
Uses the standard library only.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import update_publications as pubs

USER = "jeyaprakashk"
OUT = "assets/stats.svg"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection { totalCommitContributions }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) { totalCount }
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) { nodes { stargazerCount } }
  }
}
"""


def github_stats():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set (it is provided automatically in Actions)")
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"Bearer {token}", "User-Agent": "profile-readme-updater"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    u = (payload.get("data") or {}).get("user")
    if not u:
        raise RuntimeError(f"unexpected GraphQL response: {payload.get('errors')}")
    return {
        "stars": sum(n["stargazerCount"] for n in u["repositories"]["nodes"]),
        "commits": u["contributionsCollection"]["totalCommitContributions"],
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "contributed": u["repositoriesContributedTo"]["totalCount"],
    }


def publication_count():
    try:
        return len(pubs.drop_retracted(pubs.parse(pubs.fetch_works())))
    except Exception as exc:  # card still renders without it
        print(f"Publication count unavailable ({exc}).")
        return None


# Small 16x16 icons, drawn in the accent colour.
ICONS = {
    "stars": '<path d="M8 1.5l1.9 4 4.4.5-3.3 3 .9 4.4L8 11.2 4.1 13.4 5 9l-3.3-3 4.4-.5z" fill="none" stroke="#22d3ee" stroke-width="1.4" stroke-linejoin="round"/>',
    "commits": '<circle cx="8" cy="8" r="2.6" fill="none" stroke="#22d3ee" stroke-width="1.4"/><path d="M1 8h4.4M10.6 8H15" stroke="#22d3ee" stroke-width="1.4"/>',
    "prs": '<circle cx="4" cy="3.5" r="1.7" fill="none" stroke="#22d3ee" stroke-width="1.4"/><circle cx="4" cy="12.5" r="1.7" fill="none" stroke="#22d3ee" stroke-width="1.4"/><circle cx="12" cy="12.5" r="1.7" fill="none" stroke="#22d3ee" stroke-width="1.4"/><path d="M4 5.2v5.6M12 10.8V6.5C12 5 11 4.5 9.5 4.5H8" fill="none" stroke="#22d3ee" stroke-width="1.4"/>',
    "issues": '<circle cx="8" cy="8" r="6" fill="none" stroke="#22d3ee" stroke-width="1.4"/><circle cx="8" cy="8" r="1.4" fill="#22d3ee"/>',
    "contributed": '<rect x="2.5" y="1.8" width="11" height="12.4" rx="1.6" fill="none" stroke="#22d3ee" stroke-width="1.4"/><path d="M5.5 5h5M5.5 8h5" stroke="#22d3ee" stroke-width="1.4"/>',
}
ROWS = [
    ("stars", "Stars earned"),
    ("commits", "Commits (last year)"),
    ("prs", "Pull requests"),
    ("issues", "Issues"),
    ("contributed", "Repositories contributed to"),
]
FONT = "Segoe UI, Helvetica, Arial, sans-serif"


def render(stats, works):
    month = datetime.now(timezone.utc).strftime("%b %Y")
    p = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="560" height="236" viewBox="0 0 560 236" role="img" aria-labelledby="t">',
        '<title id="t">GitHub activity and publication count</title>',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0a1020"/><stop offset="1" stop-color="#0d3446"/></linearGradient>'
        '<linearGradient id="ac" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#22d3ee"/><stop offset="1" stop-color="#34d399"/></linearGradient></defs>',
        '<rect width="560" height="236" rx="14" fill="url(#bg)"/>',
        f'<text x="28" y="40" font-family="{FONT}" font-size="18" font-weight="700" fill="#ffffff">GitHub activity</text>',
        '<rect x="28" y="50" width="40" height="3" rx="1.5" fill="url(#ac)"/>',
    ]
    for i, (key, label) in enumerate(ROWS):
        y = 84 + i * 30
        p.append(f'<g transform="translate(28,{y - 13})">{ICONS[key]}</g>')
        p.append(f'<text x="54" y="{y}" font-family="{FONT}" font-size="14" fill="#cbd5e1">{label}</text>')
        p.append(f'<text x="290" y="{y}" text-anchor="end" font-family="{FONT}" font-size="15" font-weight="700" fill="#ffffff">{stats[key]:,}</text>')
    # right panel: publications
    p.append('<rect x="326" y="28" width="206" height="170" rx="12" fill="#ffffff" fill-opacity="0.05" stroke="#22d3ee" stroke-opacity="0.35"/>')
    if works is not None:
        p.append(f'<text x="429" y="112" text-anchor="middle" font-family="{FONT}" font-size="54" font-weight="700" fill="url(#ac)">{works}</text>')
        p.append(f'<text x="429" y="140" text-anchor="middle" font-family="{FONT}" font-size="15" fill="#e2e8f0">publications</text>')
        p.append(f'<text x="429" y="162" text-anchor="middle" font-family="Consolas, Menlo, monospace" font-size="11" fill="#94a3b8">from ORCID</text>')
    else:
        p.append(f'<text x="429" y="118" text-anchor="middle" font-family="{FONT}" font-size="15" fill="#e2e8f0">ECE faculty</text>')
    p.append(f'<text x="532" y="222" text-anchor="end" font-family="Consolas, Menlo, monospace" font-size="10" fill="#64748b">updated {month}</text>')
    p.append("</svg>")
    return "\n".join(p)


def main():
    try:
        stats = github_stats()
    except Exception as exc:  # network error, rate limit, no token
        print(f"Could not fetch GitHub stats ({exc}); leaving card unchanged.")
        return 0
    svg = render(stats, publication_count())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    if svg != old:
        open(OUT, "w", encoding="utf-8").write(svg)
        print("Card updated.")
    else:
        print("No changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

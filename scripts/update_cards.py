#!/usr/bin/env python3
"""Refresh the two profile cards in README.md: "Recent projects" and "GitHub activity".

Both are self-hosted SVG images written to assets/ (content-hashed file names,
so GitHub never shows a stale image) and shown side by side on wide screens,
stacked on narrow ones.

- Projects: the 5 most recently pushed public repos that are yours (owned by
  USER, or in ORCS with at least one commit by USER). Forks, archived repos,
  the profile repo and anything in EXCLUDE are skipped.
- GitHub activity: GitHub numbers only (GraphQL, GITHUB_TOKEN supplied
  automatically in Actions). Research and publications are a separate section.

If GitHub cannot be reached, nothing is changed. Standard library only.
Only text between <!-- CARDS:START --> and <!-- CARDS:END --> is rewritten.
"""
import glob
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from html import escape as h
from xml.sax.saxutils import escape as x

USER = "jeyaprakashk"
ORGS = ["ece-kalasalingam"]
README = "README.md"
MAX_ITEMS = 5
START, END = "<!-- CARDS:START -->", "<!-- CARDS:END -->"

EXCLUDE = {
    "jeyaprakashk/jeyaprakashk",
    "ece-kalasalingam/ece-kalasalingam.github.io",
}
DESCRIPTIONS = {  # your own wording, used instead of the GitHub description
    "capstone-project-system": "Workflow for capstone team intake, guide approval, review and evaluation",
    "fa-mentoring": "Student progress tracking by faculty mentors",
    "cotas": "FOCUS (Framework for Outcome Computation and Unification System), a desktop tool for outcome-based education workflows",
    "vlab": "Virtual laboratory for ECE experiments",
}


# ---------------------------------------------------------------- data
def api(url, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-updater"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def candidates():
    repos = api(f"https://api.github.com/users/{USER}/repos?type=owner&sort=pushed&per_page=50")
    for org in ORGS:
        for r in api(f"https://api.github.com/orgs/{org}/repos?type=public&sort=pushed&per_page=50"):
            if api(f"https://api.github.com/repos/{r['full_name']}/commits?author={USER}&per_page=1"):
                repos.append(r)
    return repos


def pick(repos):
    seen, out = set(), []
    for r in sorted(repos, key=lambda a: a.get("pushed_at") or "", reverse=True):
        name, full = r["name"], r["full_name"]
        if full in seen or full in EXCLUDE or r.get("fork") or r.get("archived") or r.get("private"):
            continue
        desc = DESCRIPTIONS.get(name) or (r.get("description") or "").strip()
        if not desc:
            continue
        seen.add(full)
        out.append({"name": name, "url": r["html_url"], "desc": desc, "pushed": (r.get("pushed_at") or "")[:10]})
        if len(out) == MAX_ITEMS:
            break
    return out


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
    if not os.environ.get("GITHUB_TOKEN"):
        raise RuntimeError("GITHUB_TOKEN not set (it is provided automatically in Actions)")
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    u = (api("https://api.github.com/graphql", body).get("data") or {}).get("user")
    if not u:
        raise RuntimeError("unexpected GraphQL response")
    return {
        "stars": sum(n["stargazerCount"] for n in u["repositories"]["nodes"]),
        "commits": u["contributionsCollection"]["totalCommitContributions"],
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "contributed": u["repositoriesContributedTo"]["totalCount"],
    }


# ---------------------------------------------------------------- drawing
FONT = "Segoe UI, Helvetica, Arial, sans-serif"
MONO = "Consolas, Menlo, monospace"
M, W, H = 6, 420, 300  # margin, card width, card height; canvas is (W+2M) x (H+2M)
LEFT = M + 24
RIGHT = M + W - 24
ACC = "#22d3ee"


def shell(title, label, body, footer):
    cw, ch = W + 2 * M, H + 2 * M
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{cw}" height="{ch}" viewBox="0 0 {cw} {ch}" role="img" aria-label="{x(title)}">',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0a1020"/><stop offset="1" stop-color="#0d3446"/></linearGradient>'
        '<linearGradient id="ac" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#22d3ee"/><stop offset="1" stop-color="#34d399"/></linearGradient>'
        f'<clipPath id="c"><rect x="{M}" y="{M}" width="{W}" height="{H}" rx="14"/></clipPath></defs>',
        f'<g clip-path="url(#c)"><rect x="{M}" y="{M}" width="{W}" height="{H}" fill="url(#bg)"/>'
        f'<rect x="{M}" y="{M}" width="{W}" height="4" fill="url(#ac)"/></g>',
        f'<rect x="{M + .5}" y="{M + .5}" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{ACC}" stroke-opacity="0.28"/>',
        f'<text x="{LEFT}" y="{M + 34}" font-family="{MONO}" font-size="11" letter-spacing="1.5" fill="{ACC}">{x(label.upper())}</text>',
        f'<text x="{LEFT}" y="{M + 60}" font-family="{FONT}" font-size="18" font-weight="700" fill="#ffffff">{x(title)}</text>',
        body,
        (f'<text x="{RIGHT}" y="{M + H - 14}" text-anchor="end" font-family="{MONO}" font-size="10" fill="#64748b">{x(footer)}</text>' if footer else ""),
        "</svg>",
    ])


def short(text, n):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def projects_svg(items, month):
    rows = []
    top, step = M + 92, 44
    for i, p in enumerate(items):
        y = top + i * step
        when = datetime.strptime(p["pushed"], "%Y-%m-%d").strftime("%b %Y") if p["pushed"] else ""
        if i:
            rows.append(f'<line x1="{LEFT}" y1="{y - 20}" x2="{RIGHT}" y2="{y - 20}" stroke="#ffffff" stroke-opacity="0.08"/>')
        rows += [
            f'<circle cx="{LEFT + 4}" cy="{y - 5}" r="3.5" fill="url(#ac)"/>',
            f'<text x="{LEFT + 16}" y="{y}" font-family="{FONT}" font-size="14" font-weight="700" fill="#ffffff">{x(short(p["name"], 30))}</text>',
            f'<text x="{RIGHT}" y="{y}" text-anchor="end" font-family="{FONT}" font-size="11" fill="#94a3b8">{x(when)}</text>',
            f'<text x="{LEFT + 16}" y="{y + 18}" font-family="{FONT}" font-size="12" fill="#cbd5e1">{x(short(p["desc"], 54))}</text>',
        ]
    return shell("Recent projects", "Repositories", "\n".join(rows), "")


ICONS = {
    "stars": '<path d="M8 1.5l1.9 4 4.4.5-3.3 3 .9 4.4L8 11.2 4.1 13.4 5 9l-3.3-3 4.4-.5z" fill="none" stroke="#22d3ee" stroke-width="1.4" stroke-linejoin="round"/>',
    "commits": '<circle cx="8" cy="8" r="2.6" fill="none" stroke="#22d3ee" stroke-width="1.4"/><path d="M1 8h4.4M10.6 8H15" stroke="#22d3ee" stroke-width="1.4"/>',
    "prs": '<circle cx="4" cy="3.5" r="1.7" fill="none" stroke="#22d3ee" stroke-width="1.4"/><circle cx="4" cy="12.5" r="1.7" fill="none" stroke="#22d3ee" stroke-width="1.4"/><circle cx="12" cy="12.5" r="1.7" fill="none" stroke="#22d3ee" stroke-width="1.4"/><path d="M4 5.2v5.6M12 10.8V6.5C12 5 11 4.5 9.5 4.5H8" fill="none" stroke="#22d3ee" stroke-width="1.4"/>',
    "issues": '<circle cx="8" cy="8" r="6" fill="none" stroke="#22d3ee" stroke-width="1.4"/><circle cx="8" cy="8" r="1.4" fill="#22d3ee"/>',
    "contributed": '<rect x="2.5" y="1.8" width="11" height="12.4" rx="1.6" fill="none" stroke="#22d3ee" stroke-width="1.4"/><path d="M5.5 5h5M5.5 8h5" stroke="#22d3ee" stroke-width="1.4"/>',
}
LABELS = [("stars", "Stars earned"), ("commits", "Commits (last year)"), ("prs", "Pull requests"),
          ("issues", "Issues"), ("contributed", "Repositories contributed to")]


def stats_svg(stats, month):
    data = dict(stats)
    rows = []
    for i, (key, label) in enumerate(LABELS):
        y = M + 96 + i * 34
        rows += [
            f'<g transform="translate({LEFT},{y - 13})">{ICONS[key]}</g>',
            f'<text x="{LEFT + 26}" y="{y}" font-family="{FONT}" font-size="14" fill="#cbd5e1">{x(label)}</text>',
            f'<text x="{RIGHT}" y="{y}" text-anchor="end" font-family="{FONT}" font-size="15" font-weight="700" fill="#ffffff">{data[key]:,}</text>',
        ]
    return shell("GitHub activity", "GitHub", "\n".join(rows), f"updated {month}")


def save(name, svg):
    digest = hashlib.sha1(svg.encode("utf-8")).hexdigest()[:8]
    path = f"assets/{name}-{digest}.svg"
    for old in glob.glob(f"assets/{name}-*.svg"):
        if old != path:
            os.remove(old)
    os.makedirs("assets", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    return path


def block(items, stats):
    month = datetime.now(timezone.utc).strftime("%b %Y")
    p_path = save("projects", projects_svg(items, month))
    s_path = save("stats", stats_svg(stats, month))
    links = " · ".join(f'<a href="{p["url"]}">{h(p["name"])}</a>' for p in items)
    return (
        '<p align="center">\n'
        f'<a href="https://github.com/{USER}?tab=repositories"><img src="{p_path}" width="432" alt="Recent projects: {h(", ".join(p["name"] for p in items))}"></a>\n'
        f'<a href="https://github.com/{USER}"><img src="{s_path}" width="432" alt="GitHub activity"></a>\n'
        "</p>\n\n"
        f'<p align="center"><sub>{links}</sub></p>'
    )


def main():
    text = open(README, encoding="utf-8").read()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        print("Markers not found in README.md", file=sys.stderr)
        return 1
    try:
        items = pick(candidates())
        stats = github_stats()
    except Exception as exc:  # network error, rate limit, no token
        print(f"Could not fetch GitHub data ({exc}); leaving everything unchanged.")
        return 0
    if not items:
        print("No eligible repositories found; leaving everything unchanged.")
        return 0
    new = pattern.sub(lambda _: f"{START}\n{block(items, stats)}\n{END}", text)
    if new != text:
        open(README, "w", encoding="utf-8").write(new)
        print("README updated.")
    else:
        print("No changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

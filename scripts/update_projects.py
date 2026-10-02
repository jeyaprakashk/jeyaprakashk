#!/usr/bin/env python3
"""Refresh the "Recent projects" table in README.md from the GitHub API.

Lists the 5 most recently pushed public repositories that are yours:
  - repositories owned by USER, and
  - repositories in ORGS where USER has authored at least one commit.
Forks, archived repositories, the profile repo and anything in EXCLUDE are skipped.
Only the text between <!-- PROJECTS:START --> and <!-- PROJECTS:END --> changes.
If the GitHub API cannot be reached, README.md is left unchanged.
Uses the standard library only; GITHUB_TOKEN is used if present (no setup needed).
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime

USER = "jeyaprakashk"
ORGS = ["ece-kalasalingam"]
README = "README.md"
MAX_ITEMS = 5
START, END = "<!-- PROJECTS:START -->", "<!-- PROJECTS:END -->"

# Repos never shown (profile repo, department website, event sites, ...).
EXCLUDE = {
    "jeyaprakashk/jeyaprakashk",
    "ece-kalasalingam/ece-kalasalingam.github.io",
}
# Your own wording; used instead of the GitHub description for these repos.
DESCRIPTIONS = {
    "capstone-project-system": "Workflow for capstone team intake, guide approval, review and evaluation",
    "fa-mentoring": "Student progress tracking by faculty mentors",
    "cotas": "FOCUS (Framework for Outcome Computation and Unification System), a desktop tool for outcome-based education workflows",
    "vlab": "Virtual laboratory for ECE experiments",
}


def get_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-readme-updater"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.load(r)


def candidates():
    repos = get_json(f"https://api.github.com/users/{USER}/repos?type=owner&sort=pushed&per_page=50")
    for org in ORGS:
        for r in get_json(f"https://api.github.com/orgs/{org}/repos?type=public&sort=pushed&per_page=50"):
            commits = get_json(
                f"https://api.github.com/repos/{r['full_name']}/commits?author={USER}&per_page=1"
            )
            if commits:  # you have contributed to this repo
                repos.append(r)
    return repos


def pick(repos):
    seen, out = set(), []
    for r in sorted(repos, key=lambda x: x.get("pushed_at") or "", reverse=True):
        name, full = r["name"], r["full_name"]
        if full in seen or full in EXCLUDE:
            continue
        if r.get("fork") or r.get("archived") or r.get("private"):
            continue
        desc = DESCRIPTIONS.get(name) or (r.get("description") or "").strip()
        if not desc:
            continue  # skip repos with no description rather than show a blank row
        seen.add(full)
        out.append({"name": name, "url": r["html_url"], "desc": desc, "pushed": r.get("pushed_at") or ""})
        if len(out) == MAX_ITEMS:
            break
    return out


def render(items):
    lines = ["| Project | What it does |", "|---|---|"]
    for p in items:
        when = ""
        if p["pushed"]:
            when = datetime.strptime(p["pushed"][:10], "%Y-%m-%d").strftime("%b %Y")
        cell = p["desc"] + (f"<br><sub>Updated {when}</sub>" if when else "")
        lines.append(f"| [**{p['name']}**]({p['url']}) | {cell} |")
    return "\n".join(lines)


def main():
    try:
        items = pick(candidates())
    except Exception as exc:  # network error, rate limit, bad JSON
        print(f"Could not fetch repositories ({exc}); leaving README unchanged.")
        return 0
    if not items:
        print("No eligible repositories found; leaving README unchanged.")
        return 0
    text = open(README, encoding="utf-8").read()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        print("Markers not found in README.md", file=sys.stderr)
        return 1
    new = pattern.sub(f"{START}\n{render(items)}\n{END}", text)
    if new != text:
        open(README, "w", encoding="utf-8").write(new)
        print("README updated.")
    else:
        print("No changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

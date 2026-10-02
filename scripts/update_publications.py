name: Update profile

on:
  schedule:
    - cron: "30 1 * * 1"   # Mondays, 07:00 IST
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Refresh recent publications from ORCID
        run: python scripts/update_publications.py
      - name: Refresh recent projects from GitHub
        run: python scripts/update_projects.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - name: Refresh activity card
        run: python scripts/update_stats_card.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - name: Commit if changed
        run: |
          if [ -n "$(git status --porcelain README.md assets/stats.svg)" ]; then
            git config user.name "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git add README.md assets/stats.svg
            git commit -m "Update publications"
            git push
          fi

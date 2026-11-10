#!/usr/bin/env python3
"""Update the profile README with the past week's GitHub activity.

Collects commit contributions (public + private, based on the token's scope)
for the last 7 days and rewrites the section between the WEEKLY markers in
README.md. Runs on a schedule from .github/workflows/update-weekly-readme.yml.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

OWNER = "RohanKhatua"
README = "README.md"
START = "<!-- WEEKLY-START -->"
END = "<!-- WEEKLY-END -->"
HEADINGS_BEFORE = ("## What I work with", "## What I Work With")

QUERY = """
query ($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      commitContributionsByRepository(maxRepositories: 10) {
        repository {
          nameWithOwner
          url
          primaryLanguage { name }
        }
        contributions { totalCount }
      }
    }
  }
}
"""


def gh(*args):
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True
    )
    if result.returncode != 0:
        sys.exit(f"gh {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout


def commit_messages(repo: str, since: str, limit: int = 3) -> list[str]:
    out = json.loads(
        gh(
            "api",
            f"repos/{repo}/commits?since={since}&per_page=20",
            "--jq", "."
        )
    )
    seen: list[str] = []
    for item in out:
        subject = item["commit"]["message"].splitlines()[0].strip()
        if subject and not subject.lower().startswith("merge") and subject not in seen:
            seen.append(subject)
        if len(seen) >= limit:
            break
    return seen


def fmt_date(dt: datetime) -> str:
    return f"{dt.strftime('%b')} {dt.day}"


def main() -> None:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    from_iso = since.strftime("%Y-%m-%dT00:00:00Z")
    to_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    data = json.loads(
        gh(
            "api", "graphql",
            "-f", f"query={QUERY}",
            "-F", f"login={OWNER}",
            "-F", f"from={from_iso}",
            "-F", f"to={to_iso}",
        )
    )
    collection = data["data"]["user"]["contributionsCollection"]
    total = collection["totalCommitContributions"]
    repos = [
        {
            "name": e["repository"]["nameWithOwner"],
            "url": e["repository"]["url"],
            "lang": (e["repository"]["primaryLanguage"] or {}).get("name"),
            "count": e["contributions"]["totalCount"],
        }
        for e in collection["commitContributionsByRepository"]
    ]

    period = f"{fmt_date(since)} – {fmt_date(now)}"
    lines = [
        "## This week on GitHub",
        "",
        f"*Week of {period} · {total} commit{'s' if total != 1 else ''}*",
        "",
    ]

    if repos:
        for repo in repos:
            lang = f" · {repo['lang']}" if repo["lang"] else ""
            lines.append(
                f"- **[{repo['name']}]({repo['url']})** — {repo['count']} commit{'s' if repo['count'] != 1 else ''}{lang}"
            )
            messages = commit_messages(repo["name"], from_iso)
            for msg in messages[:3]:
                lines.append(f"  - `{msg}`")
    else:
        lines.append("_No commits this week._")

    section = "\n".join(lines) + "\n"

    with open(README, "r", encoding="utf-8") as f:
        content = f.read()

    if START in content and END in content:
        pre, rest = content.split(START, 1)
        _, post = rest.split(END, 1)
        content = pre + START + "\n" + section + END + post
    else:
        anchor = next((h for h in HEADINGS_BEFORE if f"\n{h}" in content), None)
        if anchor:
            content = content.replace(f"\n{anchor}", f"\n{section}\n{anchor}", 1)
        else:
            content += f"\n{section}"

    with open(README, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Updated README: {total} commits across {len(repos)} repo(s) for {period}")


if __name__ == "__main__":
    main()

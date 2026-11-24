"""Build the profile's language card from GitHub's public language-byte counts."""

import json
import subprocess
import sys
from collections import Counter
from html import escape
from pathlib import Path


# Plandillo was transferred from this account. Its node ID survives transfers.
PLANDILLO = "R_kgDOVjuwng"
LANGUAGES = """
query($id: ID!, $endCursor: String) {
  node(id: $id) {
    ... on Repository {
      nameWithOwner visibility isFork
      languages(first: 100, after: $endCursor) {
        edges { size node { name color } }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}
"""


def pages(*arguments):
    result = subprocess.check_output(
        ["gh", "api", "--paginate", "--slurp", *arguments], text=True
    )
    return json.loads(result)


def language_totals(profile_repo):
    owner = profile_repo.split("/")[0]
    repo_ids = {PLANDILLO}
    for page in pages(f"users/{owner}/repos?type=owner&per_page=100"):
        for repo in page:
            if not repo["fork"] and not repo["private"] and repo["full_name"].lower() != profile_repo.lower():
                repo_ids.add(repo["node_id"])

    totals = Counter()
    colors = {}
    for repo_id in sorted(repo_ids):
        for page in pages("graphql", "-f", f"query={LANGUAGES}", "-f", f"id={repo_id}"):
            repo = page["data"]["node"]
            if not repo or repo["visibility"] != "PUBLIC" or repo["isFork"]:
                raise ValueError("A source repository is unavailable or no longer public and original")
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                totals[name] += edge["size"]
                colors[name] = edge["node"]["color"] or "#8b949e"
            if repo_id == PLANDILLO and not repo["languages"]["edges"]:
                raise ValueError("GitHub returned no language data for Plandillo")
    return totals, colors


def render(totals, colors):
    total = sum(totals.values())
    if total <= 0:
        raise ValueError("No language bytes to publish")
    top = sorted(totals, key=lambda name: (-totals[name], name))[:8]
    percentages = {name: f"{totals[name] / total:.2%}" for name in top}
    description = ", ".join(f"{name} {percentages[name]}" for name in top)
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="340" height="190" viewBox="0 0 340 190" '
        'role="img" aria-labelledby="title desc" font-family="Segoe UI,Arial,sans-serif">',
        '<title id="title">Most Used Languages</title>',
        f'<desc id="desc">Public non-fork projects including Plandillo, by code size. {escape(description)}.</desc>',
        '<rect x=".5" y=".5" width="339" height="189" rx="5" fill="#0d1117" stroke="#30363d"/>',
        '<text x="22" y="31" font-size="18" font-weight="600" fill="#64ffda">Most Used Languages</text>',
        '<text x="22" y="51" font-size="11" fill="#a0acb8">Public projects · by code size</text>',
        '<defs><clipPath id="bar"><rect x="22" y="65" width="296" height="9" rx="4.5"/></clipPath></defs>',
        '<g clip-path="url(#bar)"><rect x="22" y="65" width="296" height="9" fill="#687582"/>',
    ]
    offset = 22.0
    for name in top:
        width = 296 * totals[name] / total
        svg.append(f'<rect x="{offset:.4f}" y="65" width="{width:.4f}" height="9" fill="{colors[name]}"/>')
        offset += width
    svg.append('</g>')
    rows = (len(top) + 1) // 2
    for index, name in enumerate(top):
        x = 26 + 150 * (index // rows)
        y = 97 + 22 * (index % rows)
        svg.append(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{colors[name]}"/>')
        svg.append(f'<text x="{x + 10}" y="{y + 4}" fill="#c9d1d9" font-size="12">'
                   f'{escape(name)} {percentages[name]}</text>')
    return "\n".join([*svg, "</svg>", ""])


if __name__ == "__main__":
    profile_repo, destination = sys.argv[1:]
    card = render(*language_totals(profile_repo))
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(card, encoding="utf-8")

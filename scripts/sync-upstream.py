#!/usr/bin/env python3
"""Refresh the upstream part of skills/japanese-tech-writing/SKILL.md.

The skill embeds k16shikano's gist (Unlicense) verbatim between two marker
comments. This fetches the gist's latest revision and replaces only what lies
between the markers; ccwrite's own sections stay as they are. Review the diff
before committing.

Usage: sync-upstream.py [--check]
    --check   exit 1 when the embedded copy differs from the gist, change nothing
"""
import json
import os
import re
import sys
import urllib.request

GIST = "fd287c3133457c4fd8f5601d34aa817d"
SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                     "skills", "japanese-tech-writing", "SKILL.md")
BLOCK = re.compile(r"<!-- 上流ここから[^\n]*-->\n.*?<!-- 上流ここまで -->", re.S)


def fetch():
    with urllib.request.urlopen(f"https://api.github.com/gists/{GIST}", timeout=30) as r:
        gist = json.load(r)
    body = gist["files"]["SKILL.md"]["content"]
    body = re.sub(r"\A---\n.*?\n---\n+", "", body, flags=re.S)  # drop its frontmatter
    return gist["history"][0]["version"], body.rstrip("\n") + "\n"


def main():
    rev, body = fetch()
    with open(SKILL, encoding="utf-8") as f:
        text = f.read()
    block = (f"<!-- 上流ここから: https://gist.github.com/k16shikano/{GIST} "
             f"revision {rev[:7]}。この行と「上流ここまで」の間は scripts/sync-upstream.py が置き換える -->\n"
             f"{body}<!-- 上流ここまで -->")
    if not BLOCK.search(text):
        sys.exit("markers not found in " + SKILL)
    new = BLOCK.sub(lambda _: block, text)
    if "--check" in sys.argv[1:]:
        print("up to date" if new == text else f"upstream changed (revision {rev[:7]})")
        return 0 if new == text else 1
    with open(SKILL, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"embedded revision {rev[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

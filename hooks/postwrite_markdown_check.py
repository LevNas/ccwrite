#!/usr/bin/env python3
"""PostToolUse hook: warn about Markdown that renders differently from its source.

Runs scripts/mdcheck.py on the lines a Write or Edit added to a .md file and
tells Claude what it found. It never blocks: the edit has already happened, and
the point is to fix it in the next step.

Only added lines are checked, so editing a file with old problems does not
bring them all up. Edit: the lines that now hold `new_string`. Write: the lines
that differ from HEAD, or every line for a file git does not track.

Environment (set it in the repository's .claude/settings.json "env"):
    CCWRITE_LINEBREAKS=1   also check trailing two spaces (off by default)
    CCWRITE_EMPHASIS=0     skip the emphasis check (on by default; needs pandoc)

Any error ends the hook silently with exit 0.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import mdcheck  # noqa: E402

TRUE = {"1", "true", "yes", "on"}
FALSE = {"0", "false", "no", "off"}


def edit_lines(content, tool_input):
    """Line numbers that now hold the Edit's new_string."""
    new = tool_input.get("new_string") or ""
    if not new.strip():
        return set()
    span = new.count("\n")
    lines, start = set(), 0
    while True:
        idx = content.find(new, start)
        if idx < 0:
            break
        first = content.count("\n", 0, idx) + 1
        lines.update(range(first, first + span + 1))
        if not tool_input.get("replace_all"):
            break
        start = idx + len(new)
    return lines


def write_lines(path):
    """Lines that differ from HEAD; None (= all) when git does not track the file."""
    cwd = os.path.dirname(path) or "."

    def git(*args):
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, timeout=5)

    if git("ls-files", "--error-unmatch", "--", path).returncode != 0:
        return None
    diff = git("diff", "-U0", "HEAD", "--", path)
    if diff.returncode != 0:
        return None
    changed = mdcheck.added_lines(diff.stdout)
    return set().union(*changed.values()) if changed else set()


def main():
    data = json.load(sys.stdin)
    tool, tool_input = data.get("tool_name"), data.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    if tool not in ("Write", "Edit") or not path.endswith(".md") or not os.path.isfile(path):
        return

    linebreaks = os.environ.get("CCWRITE_LINEBREAKS", "").lower() in TRUE
    emphasis = os.environ.get("CCWRITE_EMPHASIS", "").lower() not in FALSE
    if not linebreaks and not (emphasis and mdcheck.has_pandoc()):
        return

    with open(path, encoding="utf-8") as f:
        content = f.read()
    wanted = edit_lines(content, tool_input) if tool == "Edit" else write_lines(path)
    if wanted is not None and not wanted:
        return

    found = mdcheck.check(content.split("\n"), wanted, linebreaks, emphasis)
    if not found:
        return

    hints = []
    if any(kind == "linebreak" for kind, _, _ in found):
        hints.append("end the line with two spaces, or leave a blank line for a new paragraph")
    if any(kind == "emphasis" for kind, _, _ in found):
        hints.append("make the first and last characters inside ** letters, not punctuation "
                     "(**A（B）まで**で), or put a space outside the ** (は **「重要」** の)")
    message = (f"[ccwrite] Markdown that will not render as written, on lines this edit added:\n"
               f"{mdcheck.report(path, found)}\nFix: " + "; ".join(hints) + ".")
    json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                      "additionalContext": message}},
              sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # fail open: a broken check must not get in the way of editing
        pass
    sys.exit(0)

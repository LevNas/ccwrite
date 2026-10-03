#!/usr/bin/env python3
"""Markdown checks for Japanese text that renders differently from its source.

Two checks about breakage that raises no error and that the writer cannot see
in the source, and one hint about rhythm:

linebreaks
    A line inside a paragraph that has no trailing two spaces. GFM treats such a
    newline as a soft break and joins the lines when rendering, so one-sentence-
    per-line text collapses into one line. This only matters for repositories
    that write one sentence per line, so it is opt-in.

emphasis
    `**` that GFM does not accept as emphasis and renders as literal asterisks.
    CommonMark's flanking rules refuse an opening `**` preceded by a letter and
    followed by punctuation, and a closing `**` preceded by punctuation and
    followed by a letter. Japanese hits this whenever emphasis ends in 」 or ）
    and a particle follows. pandoc renders each paragraph and decides; the rules
    are not re-implemented here. Without pandoc the check is skipped.

endings
    Three sentences in a row in one paragraph whose last three characters before
    。！？ are the same (〜します。〜します。〜します。). Comparing classes of endings
    such as です or ます would fire on most polite text; three characters keep
    設定します and 確認できます apart. A hint, not an error, so it is opt-in here; the hook turns it
    on. The idea comes from yomiyasu (https://github.com/nanaism/yomiyasu).

Usage:
    mdcheck.py [--linebreaks] [--endings] [--no-emphasis] FILE...    # every line
    mdcheck.py [--linebreaks] [--endings] [--no-emphasis] --staged    # added lines in the index

Exit status: 1 when something is found, 0 otherwise, 2 on bad usage.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

# A line starting with one of these is a block of its own, so the newline after
# it does not need trailing spaces.
BLOCK = re.compile(r"^(\||[-*+]\s|\d+\.\s|#|>{2,}|---\s*$|===|<[a-zA-Z!/])")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _is_block(body):
    return not body or bool(BLOCK.match(body))


def linebreak_misses(lines):
    """Return [(lineno, text)] for paragraph lines that lack trailing spaces."""
    misses = []
    in_code = False
    in_front = bool(lines) and lines[0].strip() == "---"
    for i, line in enumerate(lines):
        if in_front:
            if i > 0 and line.strip() == "---":
                in_front = False
            continue
        if line.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        # A change between quoted and unquoted text ends the paragraph.
        if line.lstrip().startswith(">") != nxt.lstrip().startswith(">"):
            continue
        body = re.sub(r"^\s*>\s?", "", line).strip()
        nbody = re.sub(r"^\s*>\s?", "", nxt).strip()
        if _is_block(body) or _is_block(nbody):
            continue
        if line.rstrip().endswith(("<br>", "<br/>", "<br />", "\\")):
            continue
        if line.endswith("  "):
            continue
        misses.append((i + 1, body))
    return misses


def _blank_hidden(lines):
    """Blank out code fences and HTML comments, keeping line numbers.

    Inline code stays: removing it would turn **`code`** into ****, and the
    flanking rules look at the backticks.
    """
    out, in_fence, in_comment = [], False, False
    for line in lines:
        if not in_fence and not in_comment and "<!--" in line and "-->" not in line:
            in_comment = True
            out.append("")
            continue
        if in_comment:
            if "-->" in line:
                in_comment = False
            out.append("")
            continue
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return out


def _paragraphs(lines):
    """Yield (first_lineno, last_lineno, lines) for each blank-line separated block.

    Emphasis never crosses a paragraph, and checking line by line would split an
    emphasis that opens on one line and closes on the next.
    """
    buf, start = [], 0
    for i, line in enumerate(lines, 1):
        if line.strip() == "":
            if buf:
                yield start, i - 1, buf
            buf = []
        else:
            if not buf:
                start = i
            buf.append(line)
    if buf:
        yield start, len(lines), buf


def has_pandoc():
    return shutil.which("pandoc") is not None


def emphasis_misses(lines, wanted=None):
    """Return [(lineno, text)] for paragraphs where `**` survives rendering.

    `wanted` limits the check to paragraphs that contain one of these line
    numbers. Returns [] when pandoc is not installed.
    """
    if not has_pandoc():
        return []
    misses = []
    for first, last, block in _paragraphs(_blank_hidden(lines)):
        if wanted is not None and not any(first <= n <= last for n in wanted):
            continue
        if not any("**" in line for line in block):
            continue
        try:
            html = subprocess.run(["pandoc", "-f", "gfm", "-t", "html"],
                                  input="\n".join(block), capture_output=True,
                                  text=True, timeout=10).stdout
        except (OSError, subprocess.SubprocessError):
            return misses
        html = re.sub(r"<code.*?</code>", "", html, flags=re.S)
        if "**" in html:
            offset = next(k for k, line in enumerate(block) if "**" in line)
            misses.append((first + offset, block[offset].strip()))
    return misses


# A sentence ends at one of these, optionally followed by closing brackets.
SENTENCE_END = re.compile(r"[。！？][」』）)]*")
# Quotations and code are someone else's sentences, not the writer's endings.
QUOTED = re.compile(r"「[^「」]*」|『[^『』]*』|`[^`]*`")
ENDING_LEN = 3


def _prose_lines(lines):
    """Blank out front matter and every line that is not paragraph prose.

    Lists, headings, tables, quotes and indented continuation lines are left
    out: their endings follow the list or table, not the writer's rhythm.
    """
    out = _blank_hidden(lines)
    if out and out[0].strip() == "---":
        for i in range(1, len(out)):
            done = out[i].strip() == "---"
            out[i] = ""
            if done:
                out[0] = ""
                break
    return ["" if not line.strip() or line[:1] in " \t>" or _is_block(line.strip())
            else line for line in out]


def _ending(sentence):
    """The last three characters before the final punctuation, or None.

    Only endings that close on hiragana count (します, ました, である): a sentence
    that ends on a noun, a symbol or code has no ending to repeat.
    """
    body = re.sub(r"\*\*|__", "", SENTENCE_END.sub("", sentence.strip()))
    if len(body) < ENDING_LEN or not "ぁ" <= body[-1] <= "ん":
        return None
    return body[-ENDING_LEN:]


def ending_runs(lines, wanted=None):
    """Return [(lineno, text)] for the third sentence of each run of equal endings.

    A run never crosses a paragraph. `wanted` keeps a run when one of its
    sentences touches these line numbers.
    """
    runs = []
    for first, _, block in _paragraphs(_prose_lines(lines)):
        run, key = [], None
        carry, start = "", None  # a sentence that continues on the next line
        for lineno, line in enumerate(block, first):
            line, pos = QUOTED.sub("", line), 0
            for m in SENTENCE_END.finditer(line):
                if start is None:
                    start = lineno
                sentence = (carry + line[pos:m.end()]).strip()
                span = range(start, lineno + 1)
                carry, start, pos = "", None, m.end()
                k = _ending(sentence)
                if k is None or k != key:
                    run, key = [], k
                if k is None:
                    continue
                run.append(span)
                if len(run) == 3 and (wanted is None
                                      or any(n in wanted for s in run for n in s)):
                    runs.append((lineno, f"「{k}」: {sentence}"))
            rest = line[pos:].strip()
            if rest:
                carry += rest
                if start is None:
                    start = lineno
    return runs


def added_lines(diff_text):
    """Map each file in a `git diff -U0` output to the set of added line numbers."""
    result, current = {}, None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path = line[4:]
            current = None if path == "/dev/null" else path[2:] if path.startswith("b/") else path
            if current is not None:
                result.setdefault(current, set())
            continue
        m = HUNK.match(line)
        if m and current is not None:
            start, count = int(m.group(1)), int(m.group(2) or "1")
            result[current].update(range(start, start + count))
    return result


def with_previous(numbers):
    """Add the line before each run of lines.

    Inserting a line inside a paragraph makes the unchanged line above it need
    trailing spaces, and that line is not part of the diff.
    """
    return set(numbers) | {n - 1 for n in numbers if n > 1}


def check(lines, wanted=None, linebreaks=False, emphasis=True, endings=False):
    """Run the enabled checks and keep findings on `wanted` lines (None = all)."""
    found = []
    if linebreaks:
        scope = None if wanted is None else with_previous(wanted)
        found += [("linebreak", n, t) for n, t in linebreak_misses(lines)
                  if scope is None or n in scope]
    if emphasis:
        found += [("emphasis", n, t) for n, t in emphasis_misses(lines, wanted)]
    if endings:
        found += [("ending", n, t) for n, t in ending_runs(lines, wanted)]
    return sorted(found, key=lambda f: f[1])


LABELS = {
    "linebreak": "no trailing two spaces (the next line joins this one when rendered)",
    "emphasis": "** renders as literal asterisks (flanking rule)",
    "ending": "third sentence in a row with the same ending",
}


def report(path, found):
    out = [f"{path}:"]
    out += [f"  L{n} {LABELS[kind]}: {text[:70]}" for kind, n, text in found]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--staged", action="store_true",
                    help="check lines added in the index of the current repository")
    ap.add_argument("--linebreaks", action="store_true",
                    help="also check trailing two spaces (one-sentence-per-line repositories)")
    ap.add_argument("--endings", action="store_true",
                    help="also report three sentences in a row with the same ending")
    ap.add_argument("--no-emphasis", action="store_true", help="skip the emphasis check")
    args = ap.parse_args(argv)
    if bool(args.files) == args.staged:
        ap.error("give either FILE... or --staged")

    if args.staged:
        diff = subprocess.run(["git", "diff", "--cached", "-U0", "--diff-filter=AM",
                               "--", "*.md"], capture_output=True, text=True).stdout
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True).stdout.strip()
        targets = [(os.path.join(top, p), n) for p, n in added_lines(diff).items()]
    else:
        targets = [(p, None) for p in args.files]

    if not args.no_emphasis and not has_pandoc():
        print("mdcheck: pandoc not found, emphasis check skipped", file=sys.stderr)

    status = 0
    for path, wanted in targets:
        if args.staged:
            text = subprocess.run(["git", "show", f":{os.path.relpath(path, top)}"],
                                  capture_output=True, text=True, cwd=top).stdout
        else:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        found = check(text.split("\n"), wanted, args.linebreaks, not args.no_emphasis,
                      args.endings)
        if found:
            print(report(path, found))
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())

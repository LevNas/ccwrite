import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import mdcheck  # noqa: E402

HOOK = os.path.join(ROOT, "hooks", "postwrite_markdown_check.py")
PANDOC = shutil.which("pandoc") is not None


class Linebreaks(unittest.TestCase):
    def misses(self, text):
        return [n for n, _ in mdcheck.linebreak_misses(text.split("\n"))]

    def test_missing_spaces_inside_paragraph(self):
        self.assertEqual(self.misses("一文目。\n二文目。\n"), [1])

    def test_trailing_spaces_br_and_backslash_pass(self):
        self.assertEqual(self.misses("一文目。  \n二文目。<br>\n三文目。\\\n四文目。\n"), [])

    def test_blocks_and_paragraph_ends_pass(self):
        text = "# 見出し\n本文。\n\n- 項目\n- 項目\n\n| a |\n|---|\n\n最後の行。\n"
        self.assertEqual(self.misses(text), [])

    def test_code_fence_and_frontmatter_ignored(self):
        text = "---\ntitle: x\nid: y\n---\n```\na\nb\n```\n"
        self.assertEqual(self.misses(text), [])

    def test_quote_boundary_ends_paragraph(self):
        self.assertEqual(self.misses("> 引用。\n本文。\n"), [])
        self.assertEqual(self.misses("> 一文目。\n> 二文目。\n"), [1])


@unittest.skipUnless(PANDOC, "pandoc not installed")
class Emphasis(unittest.TestCase):
    def misses(self, text, wanted=None):
        return [n for n, _ in mdcheck.emphasis_misses(text.split("\n"), wanted)]

    def test_punctuation_inside_emphasis_breaks(self):
        self.assertEqual(self.misses("これは**「重要」**の話です。\n"), [1])
        self.assertEqual(self.misses("前置き。\n\nこれを**A（B）**で認証する。\n"), [3])

    def test_working_emphasis_passes(self):
        text = ("これを**A（B）まで**で認証する。\n\nこれは **「重要」** の話。\n\n"
                "**強調です。**\n")
        self.assertEqual(self.misses(text), [])

    def test_code_and_comments_ignored(self):
        text = "`a**b` は **`code`** だ。\n\n<!--\n**「x」**の\n-->\n\n```\n**「x」**の\n```\n"
        self.assertEqual(self.misses(text), [])

    def test_code_span_next_to_letter_breaks(self):
        # A backtick is punctuation for the flanking rules, so this does not open.
        self.assertEqual(self.misses("は**`code`**だ。\n"), [1])

    def test_emphasis_across_two_lines(self):
        self.assertEqual(self.misses("**一行目から\n二行目まで**です。\n"), [])

    def test_wanted_limits_paragraphs(self):
        text = "は**「a」**の\n\nは**「b」**の\n"
        self.assertEqual(self.misses(text, {3}), [3])
        self.assertEqual(self.misses(text, {2}), [])


class AddedLines(unittest.TestCase):
    def test_parse_hunks(self):
        diff = ("diff --git a/x.md b/x.md\n--- a/x.md\n+++ b/x.md\n"
                "@@ -1,0 +2,3 @@\n+a\n+b\n+c\n@@ -9 +12 @@\n-x\n+y\n@@ -20,2 +22,0 @@\n-p\n-q\n"
                "+++ /dev/null\n")
        self.assertEqual(mdcheck.added_lines(diff), {"x.md": {2, 3, 4, 12}})

    def test_previous_line_added_for_linebreaks(self):
        lines = "一文目。  \n二文目。\n挿入した文。  \n三文目。\n".split("\n")
        found = mdcheck.check(lines, {3}, linebreaks=True, emphasis=False)
        self.assertEqual([n for _, n, _ in found], [2])


class Hook(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.dir, check=True, capture_output=True)

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def run_hook(self, payload, **env):
        full = dict(os.environ, CCWRITE_LINEBREAKS="", CCWRITE_EMPHASIS="")
        full.update(env)
        r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                           capture_output=True, text=True, env=full)
        self.assertEqual(r.returncode, 0)
        if not r.stdout:
            return ""
        out = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "PostToolUse")
        return out["additionalContext"]

    def test_edit_checks_only_new_string(self):
        path = self.write("a.md", "古い文。\n古い文。\n\n新しい文。\n新しい文。\n")
        payload = {"tool_name": "Edit",
                   "tool_input": {"file_path": path, "new_string": "新しい文。\n新しい文。"}}
        msg = self.run_hook(payload, CCWRITE_LINEBREAKS="1")
        self.assertIn("L4", msg)
        self.assertNotIn("L1", msg)

    def test_linebreaks_off_by_default(self):
        path = self.write("a.md", "一文目。\n二文目。\n")
        payload = {"tool_name": "Write", "tool_input": {"file_path": path}}
        self.assertEqual(self.run_hook(payload, CCWRITE_EMPHASIS="0"), "")
        self.assertIn("L1", self.run_hook(payload, CCWRITE_LINEBREAKS="1", CCWRITE_EMPHASIS="0"))

    def test_write_checks_lines_changed_since_head(self):
        path = self.write("a.md", "古い文。\n古い文。\n")
        self.git("add", "a.md")
        self.git("commit", "-qm", "init")
        self.write("a.md", "古い文。\n古い文。\n\n新しい文。\n新しい文。\n")
        payload = {"tool_name": "Write", "tool_input": {"file_path": path}}
        msg = self.run_hook(payload, CCWRITE_LINEBREAKS="1")
        self.assertIn("L4", msg)
        self.assertNotIn("L1", msg)

    def test_ignores_other_files_and_tools(self):
        path = self.write("a.txt", "一文目。\n二文目。\n")
        self.assertEqual(self.run_hook({"tool_name": "Write", "tool_input": {"file_path": path}},
                                       CCWRITE_LINEBREAKS="1"), "")
        md = self.write("b.md", "一文目。\n二文目。\n")
        self.assertEqual(self.run_hook({"tool_name": "Read", "tool_input": {"file_path": md}},
                                       CCWRITE_LINEBREAKS="1"), "")

    def test_bad_input_fails_open(self):
        r = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    @unittest.skipUnless(PANDOC, "pandoc not installed")
    def test_emphasis_on_by_default(self):
        path = self.write("a.md", "これは**「重要」**の話です。\n")
        msg = self.run_hook({"tool_name": "Write", "tool_input": {"file_path": path}})
        self.assertIn("L1 ** renders as literal asterisks", msg)

    def test_emphasis_silent_without_pandoc(self):
        path = self.write("a.md", "これは**「重要」**の話です。\n")
        payload = {"tool_name": "Write", "tool_input": {"file_path": path}}
        bin_dir = os.path.join(self.dir, "bin")  # a PATH holding git and nothing else
        os.mkdir(bin_dir)
        os.symlink(shutil.which("git"), os.path.join(bin_dir, "git"))
        self.assertEqual(self.run_hook(payload, PATH=bin_dir), "")


class BudouxWrap(unittest.TestCase):
    @unittest.skipUnless(subprocess.run([sys.executable, "-c", "import budoux"],
                                        capture_output=True).returncode == 0,
                         "budoux not installed")
    def test_wraps_at_phrase_boundaries(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "budoux-wrap"),
                            "--width", "6", "--sep", "|", "今日は天気です。"],
                           capture_output=True, text=True, check=True)
        self.assertEqual(r.stdout.strip(), "今日は|天気です。")

    def test_missing_budoux_explains(self):
        env = dict(os.environ, PYTHONPATH="")
        r = subprocess.run([sys.executable, "-S", os.path.join(ROOT, "scripts", "budoux-wrap"),
                            "--venv", "/nonexistent", "テキスト"],
                           capture_output=True, text=True, env=env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("setup-budoux", r.stderr)


if __name__ == "__main__":
    unittest.main()

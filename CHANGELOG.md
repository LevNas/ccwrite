# Changelog

## 0.1.0

First release.

### Added

- `japanese-tech-writing` skill: k16shikano's writing norms (embedded verbatim, refreshed with `scripts/sync-upstream.py`) plus two ccwrite sections, the scope note and the formatting rules the upstream dropped.
- `japanese-writing-router` skill: channel and recipient routing, honorific levels and disclosure, Markdown line breaks and paragraphs, BudouX line wrapping, and message templates stored in the `templates_dir` user setting (default: the plugin data directory).
- `markdown-style` skill: Markdown that renders differently from its source in Japanese text, and how to check it.
- `jp-copy-editor` agent: edits several drafts at once and returns questions instead of guessing the recipient.
- PostToolUse hook (`Write|Edit` on `.md`): warns Claude about lines the edit added where `**` will render literally (needs pandoc) or, with `CCWRITE_LINEBREAKS=1`, where a paragraph line has no trailing two spaces. Never blocks.
- `hooks/pre-commit.sample`: the same checks on lines added in staged `.md` files.
- `scripts/budoux-wrap` and `scripts/setup-budoux`: wrap Japanese text at phrase boundaries; BudouX goes into `${CLAUDE_PLUGIN_DATA}/venv` after the user agrees.

### Known

- The emphasis check is silent without pandoc.
- For an Edit, the checked lines are found by searching the file for `new_string`; when the same text also appears earlier in the file, the earlier place is checked instead.

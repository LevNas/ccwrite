# Changelog

## 0.2.0

### Added

- Same-ending hint (`scripts/mdcheck.py --endings`, on in the hook, `CCWRITE_ENDINGS=0` turns it off): three sentences in a row in one paragraph whose last three characters before 。！？ match. Lists, tables, quotes, 「」, code and front matter are not counted, and a run never crosses a paragraph. Not run by `pre-commit.sample`. Measured before choosing three characters: a class-level check (です vs ます) fires on polite text that reads fine, while three characters fired 0 times on 16 human-written texts and once in 313 knowledge-base notes, and 7 times in 24 raw LLM texts.
- `japanese-tech-writing`: a third ccwrite section, examples of calques and LLM phrasing common in tech blogs and business documents (silently fail, the moment, 〜側に倒す, 時間を溶かす, 解像度を上げる, closing formulas), keeping the nuance a metaphor carried, and the rule for monotonous endings.
- `jp-copy-editor`: guardrails that keep a draft's claim, weight, strength of assertion and the job of each sentence, and add no facts; output now lists what changed and why, LLM-like phrasing kept because it carries meaning, and questions.

Examples, guardrails and the idea of the ending check come from [yomiyasu](https://github.com/nanaism/yomiyasu) (MIT, Copyright (c) 2026 nanaism).

### Known

- A sentence that spans a 「」 opened on one line and closed on the next is counted with the quotation in it.
- The same-ending check can miss a run, never reports more: a sentence that ends in a bracket, a link or `~~` before 。 has no ending and breaks the run; only `**` and `__` are stripped; a one-line `<!-- -->` comment hides the prose after it on that line; a line indented by spaces is skipped; and a fourth sentence added to an existing run of three is not reported, because a run is reported once, at its third sentence.

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

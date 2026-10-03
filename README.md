# ccwrite

Japanese writing for Claude Code. ccwrite gives Claude a set of writing norms for Japanese technical and business text, a router that adapts a text to its channel and recipient, a copy-editor agent for batches of drafts, and warn-only checks for Markdown that renders differently from its source.

The skills are written in Japanese, because they are norms for Japanese text.

## What it contains

| Component | Name | What it does |
|---|---|---|
| Skill | `japanese-tech-writing` | Writing norms: paragraph structure, rigor of argument, reader load, point of view, restraint in rhetoric, no empty LLM phrasing, no calques of English idioms, no redundancy. Embeds [k16shikano's norms](https://gist.github.com/k16shikano/fd287c3133457c4fd8f5601d34aa817d) verbatim and adds a scope note and formatting rules. |
| Skill | `japanese-writing-router` | Chooses which norms apply per channel (documents, chat, boards, email, review of a given text), sets honorifics and disclosure per recipient (internal, community, customer, partner), asks before guessing a recipient, handles Markdown line breaks and BudouX wrapping, and keeps message templates. |
| Skill | `markdown-style` | Markdown that GFM renders differently in Japanese text: `**` next to 」 or ）, lost trailing spaces, line breaks in table cells, auto-links. |
| Agent | `jp-copy-editor` | Edits several drafts at once against the two skills above and returns open questions about recipients instead of guessing. |
| Hook | PostToolUse on `Write\|Edit` | Checks the lines an edit added to a `.md` file and warns Claude. Never blocks. |
| Sample | `hooks/pre-commit.sample` | The same checks on lines added in staged `.md` files, for repositories that want a commit gate. |
| Scripts | `scripts/budoux-wrap`, `scripts/setup-budoux` | Wrap Japanese text at [BudouX](https://github.com/google/budoux) phrase boundaries. |

ccwrite does not choose between polite (です・ます) and plain (だ・である) style. That belongs to each repository's own rules, for example the tone template of [ccharness](https://github.com/LevNas/ccharness). The router only raises honorifics above that floor for customers and partners.

## Install

```text
/plugin marketplace add LevNas/claudecode-plugins
/plugin install ccwrite@levnas-plugins
```

## Settings

### Markdown checks

The hook reads two environment variables. Set them per repository in `.claude/settings.json`:

```json
{
  "env": {
    "CCWRITE_LINEBREAKS": "1"
  }
}
```

| Variable | Default | Effect |
|---|---|---|
| `CCWRITE_EMPHASIS` | on | `0` turns off the emphasis check. The check needs [pandoc](https://pandoc.org/); without it, it stays silent. |
| `CCWRITE_LINEBREAKS` | off | `1` also reports paragraph lines without trailing two spaces. Turn it on in repositories that write one sentence per line. |

Only lines the edit added are checked (Edit: the lines holding `new_string`; Write: lines that differ from `HEAD`, or the whole file if git does not track it), so old problems in a file are not reported.

To check a whole file by hand:

```bash
python3 scripts/mdcheck.py [--linebreaks] FILE.md
```

### Templates

`japanese-writing-router` saves message templates in the `templates_dir` user setting (`/config`). Left empty, it uses `${CLAUDE_PLUGIN_DATA}/templates`, which is deleted when the plugin is uninstalled. Templates name your recipients and topics, so point the setting at a private repository rather than a public one.

### BudouX

`budoux-wrap` needs the `budoux` Python package. The router asks before running `scripts/setup-budoux`, which installs it into `${CLAUDE_PLUGIN_DATA}/venv`. A `budoux` already importable by `python3` is used as is.

## Updating the embedded norms

```bash
python3 scripts/sync-upstream.py --check   # is the embedded copy current?
python3 scripts/sync-upstream.py           # replace the text between the markers
```

Review the diff, bump `version` in `.claude-plugin/plugin.json`, and commit.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The emphasis tests are skipped without pandoc, and the BudouX test without budoux.

## License

MIT, except the embedded upstream norms in `skills/japanese-tech-writing/SKILL.md`, which are under the Unlicense. See [LICENSE](LICENSE).

# /backlog — a plain-Markdown task backlog for Claude Code

A [Claude Code](https://claude.com/claude-code) skill that keeps a project's task list in one file, `docs/backlog.md`, and lets you drive it with a slash command:

```
/backlog next
/backlog add Dark mode; Location search. Type a city name.
/backlog start W-004
/backlog done W-004 Search uses the geocoding API.
```

The backlog stays a readable Markdown file that lives in your repo next to the code. You can edit it by hand, diff it, and review it in pull requests. The skill makes sure Claude edits it the same careful way every time.

## Why a script and not just a prompt

Asking a model to "move B-042 to Done" usually means it re-types the whole line, and long lines come back slightly changed. Here every edit goes through `backlog.py`, a small standard-library Python script that:

- moves and re-marks lines without retyping them,
- hands out IDs from the footer and never reuses an ID already in the file,
- keeps the **Now** section in step (start adds a pointer, done and drop remove it),
- refuses to guess: an ambiguous ID, text, or section name stops with a list of matches.

Claude only decides *what* to do; the script does the editing. That is also why the skill can run on Haiku (`model: haiku` in `SKILL.md`), so it is fast and cheap.

## Install

Clone the repo into your personal skills folder:

```sh
git clone https://github.com/rave-altfred/claude-backlog-skill.git ~/.claude/skills/backlog
```

Start a new Claude Code session and type `/backlog`. To update later:

```sh
git -C ~/.claude/skills/backlog pull
```

The folder must be named `backlog` and sit at `~/.claude/skills/backlog`, because `SKILL.md` calls the script by that path.

### Requirements

- Python 3.9 or newer (`python3` on your `PATH`). No packages to install.
- macOS or Linux. The script uses `fcntl` file locking, so it does not run on native Windows (WSL works).
- git is optional. The script uses it to find the repo root; without git it uses the current folder.

## Getting started

In a project, run:

```
/backlog init W
```

This creates `docs/backlog.md` with IDs starting at `W-001` (the default prefix is `B`). It never overwrites an existing file.

## Commands

| Command | What it does |
|---|---|
| `/backlog` or `/backlog status` | What is in Now, what is in progress, open counts per section, next free ID |
| `/backlog next` | Now, in-progress tasks, and the top 3 open tasks per section, plus a suggestion for what to pick |
| `/backlog add <items>` | One task per item (split on new lines, `;`, or a list). Goes to Inbox, or `add --bug …` for Bugs, or `add to <section>: …` |
| `/backlog start <id>` | Mark `[~]` and add a pointer in Now |
| `/backlog done <id> [note]` | Mark `[x]` with today's date and the note, move it to the top of Done |
| `/backlog drop <id> <why>` | Mark `[-]` with the reason and leave it where it is |
| `/backlog move <id> <section>` | Move to another section. Moving an idea out of the Inbox gives it an ID if it has none |
| `/backlog split <id> <parts>` | Replace a task with smaller tasks right under it |
| `/backlog show <id or text>` | Matching lines, their section, and which other tasks mention the ID |

Section names match loosely: `bugs`, `phase 2`, and `inbox` all work.

You can also just ask in plain words ("what's next on the backlog?", "mark W-006 done") and Claude will use the skill.

## The file format

```markdown
## Now

- [ ] W-006 Temperature line.

## Backlog

- [-] W-002 Hourly chart. Split into W-006, W-007 2026-10-12.
- [~] W-006 Temperature line.
- [ ] W-007 Rain bars.

## Bugs

- [ ] W-005 Chart clips the last hour.

## Inbox

- [ ] W-003 Dark mode.

## Done

- [x] 2026-10-12 W-001 Fetch the forecast from the API. Ten-minute cache in place.

---

Next free ID: W-008.
```

- One line per task: `- [ ] <PFX>-nnn Title. Context.`
- Marks: `[ ]` open, `[~]` in progress, `[x]` done, `[-]` dropped.
- Order inside a section is priority order, top first.
- **Now** holds pointers to tasks that live in other sections.
- **Done** is newest first, with the date.
- You can rename `## Backlog` or add more sections (for example one per milestone). The skill finds sections by their headings.
- If the file has a `## How to use this file` section, Claude reads it and follows your rules there before adding or moving tasks.

## Things to know

- **It commits.** After an edit, if `docs/backlog.md` is the *only* changed file in the repo, the skill commits it on its own with a message like `docs: W-006 done`. If anything else is changed, it leaves the backlog uncommitted so it can go into the same commit as the work. Remove the "After every edit" section from `SKILL.md` if you don't want this.
- **Another path.** The script takes `--file <path>` if your backlog lives somewhere other than `docs/backlog.md`. You can run it by hand too: `python3 ~/.claude/skills/backlog/backlog.py --help`.

## License

MIT. See [LICENSE](LICENSE).

---
name: backlog
description: Read and update the project's task backlog in docs/backlog.md — init, next, add, start, done, drop, move, split, show, status. Use when the user runs /backlog, asks what's next on the backlog, or asks to add, start, finish, split, or cut a backlog task.
argument-hint: "[init [prefix] | next | add <items> | start <id> | done <id> [note] | drop <id> <why> | move <id> <section> | split <id> <parts> | show <id|text> | status]"
---

# /backlog

Drive the project's task list at `docs/backlog.md`. The first word of the arguments is the verb; no arguments means `status`.

## Use the script for every read and edit

```
python3 ~/.claude/skills/backlog/backlog.py <command> [args]
```

It finds `docs/backlog.md` under the git root (`--file <path>` overrides), assigns IDs from the footer (never reusing one already in the file), moves lines without retyping them, and prints what it changed. Quote every argument that has spaces. If it exits non-zero, show its message and stop: do not fall back to editing the file by hand.

| Command | Does |
|---|---|
| `status` | Now, `[~]` tasks, open counts per section, stray `[x]` lines, stale Now pointers, next free ID |
| `next` | Now, `[~]` tasks, top 3 open tasks per work section |
| `show <id\|text> [--full]` | matching lines with their section; for an ID, the tasks that mention it |
| `add "<task>" ["<task>" …] [--bug \| --section <s>] [--top]` | one new task per argument, Inbox by default, appended unless `--top` |
| `start <id>` | mark `[~]`, clear stale Now pointers, add a Now pointer |
| `now <id>` | add a Now pointer only |
| `done <id> ["<note>"]` | mark `[x]` with today's date and the note, move to the top of Done, drop the Now pointer |
| `drop <id> "<why>"` | mark `[-]`, append `Dropped <date>: <why>.`, leave in place, drop the Now pointer |
| `move <id\|text> "<section>" [--top]` | move to the end (or top) of a section; leaving the Inbox gives an ID-less idea its ID; a dated `[x]` line moving to Done lands by date |
| `split <id> "<part>" ["<part>" …]` | new tasks right under the original, original marked `[-] Split into …`, Now pointer replaced |

Sections are matched loosely (`"phase 4"`, `bugs`); the script lists the headings when a name is ambiguous. A target that is not an ID is a unique text fragment, which is how an Inbox idea without an ID is named.

## Conventions the script does not decide

- One line per task: `- [ ] <PFX>-nnn Title. Context.` When adding, write a short title sentence plus any context the user gave; do not invent context.
- Order inside a section is priority order, top first. Add at the end unless the user says top.
- Lines in **Now** are pointers to tasks that live elsewhere.
- If the file has its own "How to use this file" section, its rules win (for example a test an idea must pass to leave the Inbox). Read it before any `add` or `move` (`grep -n -A12 '^## How to use' docs/backlog.md`). If a move out of the Inbox does not obviously pass the file's test, ask the user before running it.

## Verbs

- **status** (also no arguments): run `status` and relay it in a few lines.
- **next**: run `next` and show its output, one block per section. If it reports a stale pointer, say Now is stale. End with a one-line recommendation: which single task to pick first and why. Do not start any task. If the file tracks open tasks as table rows instead of checkbox lines, read those rows yourself and take the top ones per category, preferring `Now` over `Next` over `Later`.
- **add <items>**: split the items on new lines, `;`, or numbered or bulleted lists, then pass each as its own argument in one `add` call. `add --bug …` goes to Bugs, `add to <section>: …` uses `--section`.
- **start**, **done**, **drop**, **move**, **split**, **show**: run the command of the same name. `drop` needs a reason; ask for one if none was given. After `done`, if the script prints `Now is empty.`, run `next`, pick the next task as the `next` verb would, run `now <id>` on it, and say which.

## init [prefix]

If `docs/backlog.md` exists, say so and stop. Never overwrite it.

Otherwise create `docs/` if needed and write this template, with `<PFX>` the given prefix (default `B`) and the purpose line taken from the first line of the README or CLAUDE.md if one exists (else leave a placeholder):

```markdown
# Backlog

<One line: what this project is.>

This file says what is being worked on, in what order, and what is done.

## How to use this file

- One line per task: `- [ ] <PFX>-nnn Title. Context.`
- Status marks: `[ ]` open, `[~]` in progress, `[x]` done, `[-]` dropped (say why in the line).
- IDs are permanent. Never reuse or renumber. Next free ID is noted at the end of the file.
- Order inside a section is priority order. Finished tasks move to **Done**, newest first, with the date.
- New ideas land in **Inbox** first.
- Update this file whenever a task starts, finishes, splits, or gets cut. Keep lines short; detail belongs in other docs.

## Now

## Backlog

## Bugs

## Inbox

Ideas not yet committed to.

## Done

---

Next free ID: <PFX>-001.
```

Tell the user they can rename `## Backlog` or add phase sections; the skill finds sections by heading.

## Anything the script cannot do

Reordering inside a section, rewording a task, or other one-off edits: use the Edit tool with a short anchor (the ID plus a few words) and change only the words that differ. Never paste a whole task line into `old_string` or `new_string`, never Read the whole file (start from `grep -n -E '^#|Next free ID' docs/backlog.md`), and never rewrite the file with Write.

## After every edit

- Commit only when the backlog is the sole change. Run `git status --porcelain`: if the backlog file is the only line, commit it alone with a `docs:` message naming the IDs (for example `docs: B-256 done`). If any other file is modified, staged, or untracked, do not commit: the backlog change goes into the same commit as the work it describes.
- Print one summary line: what changed, which IDs, which section, and the new footer if it moved.

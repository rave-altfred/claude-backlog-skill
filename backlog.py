#!/usr/bin/env python3
"""Mechanical edits to docs/backlog.md for the /backlog skill.

Every command that changes the file reads it, touches only the lines it
names, and writes it back, so nobody retypes a long task line by hand.
IDs come from the footer and are checked against every ID already used.
Standard library only; runs on the macOS system Python (3.9).
"""
import argparse
import datetime
import fcntl
import os
import re
import subprocess
import sys
import tempfile

TASK = re.compile(r'^- (?:\[(.)\] )?(?:(\d{4}-\d{2}-\d{2}) )?(.*)$')
HEADING = re.compile(r'^(#{2,3}) +(.*?)\s*$')
FOOTER = re.compile(r'Next free ID: ([A-Z]+)-(\d+)')
ID_ARG = re.compile(r'[A-Za-z]+-\d+')
CUT = 200


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def cut(line, full=False):
    return line if full or len(line) <= CUT else line[:CUT] + '…'


class Section:
    def __init__(self, name, start, end):
        self.name, self.start, self.end = name, start, end
        low = name.lower()
        if low.startswith('how to use'):
            self.kind = 'howto'
        elif low.startswith('now'):
            self.kind = 'now'
        elif low.startswith('inbox'):
            self.kind = 'inbox'
        elif low.startswith('done'):
            self.kind = 'done'
        elif 'checkpoint' in low:
            self.kind = 'checkpoint'
        else:
            self.kind = 'work'


class Backlog:
    def __init__(self, path, today):
        self.path, self.today = path, today
        with open(path, encoding='utf-8') as f:
            self.lines = f.read().split('\n')

    def save(self):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), prefix='.backlog-')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.lines))
        os.chmod(tmp, os.stat(self.path).st_mode & 0o777)
        os.replace(tmp, self.path)

    # Structure

    def sections(self):
        heads = [(i, m.group(2)) for i, l in enumerate(self.lines) for m in [HEADING.match(l)] if m]
        out = []
        for k, (i, name) in enumerate(heads):
            end = heads[k + 1][0] if k + 1 < len(heads) else len(self.lines)
            for j in range(i + 1, end):
                if self.lines[j].strip() == '---':
                    end = j
                    break
            out.append(Section(name, i, end))
        return out

    def section_at(self, i):
        for s in self.sections():
            if s.start <= i < s.end:
                return s
        return None

    def section(self, query):
        secs = [s for s in self.sections() if s.kind != 'howto']
        q = query.lower().strip()
        for test in (lambda n: n == q, lambda n: n.startswith(q), lambda n: q in n):
            hits = [s for s in secs if test(s.name.lower())]
            if len(hits) == 1:
                return hits[0]
            if len(hits) > 1:
                die('"%s" matches several sections: %s' % (query, '; '.join(s.name for s in hits)))
        die('no section matches "%s". Sections: %s' % (query, '; '.join(s.name for s in secs)))

    def kind(self, kind):
        return next((s for s in self.sections() if s.kind == kind), None)

    def tasks_in(self, s):
        return [i for i in range(s.start + 1, s.end) if TASK.match(self.lines[i])]

    # Tasks

    @staticmethod
    def has_id(line, tid):
        m = TASK.match(line)
        return bool(m and re.match(re.escape(tid) + r'(?!\d)', m.group(3)))

    def find(self, target):
        """Index of the task's own line: never a Now pointer, never a How-to bullet."""
        is_id = ID_ARG.fullmatch(target)
        tid = target.upper() if is_id else None
        hits, pointers = [], []
        for s in self.sections():
            if s.kind == 'howto':
                continue
            for i in self.tasks_in(s):
                line = self.lines[i]
                if self.has_id(line, tid) if is_id else target.lower() in line.lower():
                    (pointers if s.kind == 'now' else hits).append(i)
        if len(hits) == 1:
            return hits[0]
        if hits:
            die('"%s" matches several lines:\n%s' % (target, '\n'.join(
                'L%d %s' % (i + 1, cut(self.lines[i])) for i in hits)))
        if pointers:
            die('"%s" appears only as a Now pointer; its task line is missing.' % target)
        die('no task matches "%s".' % target)

    def task_id(self, i):
        m = TASK.match(self.lines[i])
        idm = re.match(r'([A-Z]+-\d+)(?!\d)', m.group(3))
        return idm.group(1) if idm else None

    def remark(self, i, mark, date=None, append=None):
        m = TASK.match(self.lines[i])
        d = date or m.group(2)
        line = '- [%s] %s%s' % (mark, d + ' ' if d else '', m.group(3))
        if append:
            line = line.rstrip() + ' ' + append
        self.lines[i] = line
        return line

    def ensure_id(self, i):
        """Give an Inbox idea without an ID its ID and checkbox."""
        if self.task_id(i):
            return None
        m = TASK.match(self.lines[i])
        tid = self.allocate(1)[0]
        self.lines[i] = '- [%s] %s%s %s' % (m.group(1) or ' ', m.group(2) + ' ' if m.group(2) else '', tid, m.group(3))
        return tid

    # Lines

    def insert(self, s, line, top=False):
        idx = self.tasks_in(s)
        if idx:
            at = idx[0] if top else idx[-1] + 1
            self.lines.insert(at, line)
            return at
        p = max(i for i in range(s.start, s.end) if self.lines[i].strip())
        self.lines[p + 1:p + 1] = ['', line]
        if p + 3 < len(self.lines) and self.lines[p + 3].strip():
            self.lines.insert(p + 3, '')
        return p + 2

    def remove(self, i):
        line = self.lines.pop(i)
        if 0 < i < len(self.lines) and not self.lines[i - 1].strip() and not self.lines[i].strip():
            self.lines.pop(i)
        return line

    # IDs

    def footer(self):
        for i in range(len(self.lines) - 1, -1, -1):
            m = FOOTER.search(self.lines[i])
            if m:
                return i, m
        die('no "Next free ID: <PFX>-nnn" footer found.')

    def allocate(self, n):
        i, m = self.footer()
        pfx, digits = m.group(1), m.group(2)
        body = '\n'.join(l for k, l in enumerate(self.lines) if k != i)
        used = [int(x) for x in re.findall(r'\b%s-(\d+)(?!\d)' % pfx, body)]
        start = max([int(digits)] + [u + 1 for u in used])
        width = len(digits)
        self.lines[i] = self.lines[i][:m.start(2)] + '%0*d' % (width, start + n) + self.lines[i][m.end(2):]
        return ['%s-%0*d' % (pfx, width, start + k) for k in range(n)]

    def next_free(self):
        return 'Next free ID: %s-%s.' % self.footer()[1].groups()

    # Now pointers

    def pointer(self, i):
        tid = self.task_id(i)
        text = TASK.match(self.lines[i]).group(3)[len(tid):].strip().replace('**', '')
        short = re.split(r'(?<=[.!?:])\s', text, 1)[0].rstrip('.:!? ')
        if len(short) > 80:
            short = short[:80].rsplit(' ', 1)[0] + '…'
        return '- [ ] %s %s.' % (tid, short)

    def now_pointers(self, tid):
        s = self.kind('now')
        return [i for i in self.tasks_in(s) if self.has_id(self.lines[i], tid)] if s else []

    def drop_pointers(self, tid):
        removed = 0
        for i in reversed(self.now_pointers(tid)):
            self.remove(i)
            removed += 1
        return removed

    def add_pointer(self, i):
        tid = self.task_id(i)
        now = self.kind('now')
        if not now:
            die('no Now section.')
        if self.now_pointers(tid):
            return None
        line = self.pointer(i)
        self.insert(now, line)
        return line

    def stale_pointers(self):
        """Now pointers whose task is finished or dropped."""
        now = self.kind('now')
        out = []
        for p in self.tasks_in(now) if now else []:
            tid = self.task_id(p)
            if not tid:
                continue
            for s in self.sections():
                if s.kind in ('now', 'howto'):
                    continue
                for i in self.tasks_in(s):
                    if self.has_id(self.lines[i], tid) and TASK.match(self.lines[i]).group(1) in ('x', '-'):
                        out.append((p, tid))
        return out


# Commands

def say(*lines):
    for l in lines:
        print(cut(l))


def cmd_status(b, a):
    now = b.kind('now')
    print('Now:')
    say(*['  ' + b.lines[i] for i in b.tasks_in(now)] if now and b.tasks_in(now) else ['  (empty)'])
    wip = [(s, i) for s in b.sections() if s.kind not in ('now', 'howto')
           for i in b.tasks_in(s) if TASK.match(b.lines[i]).group(1) == '~']
    print('In progress:')
    say(*['  %s  [%s]' % (b.lines[i], s.name) for s, i in wip] or ['  (none)'])
    print('Open:')
    total = 0
    for s in b.sections():
        if s.kind in ('now', 'howto', 'done'):
            continue
        n = sum(1 for i in b.tasks_in(s) if TASK.match(b.lines[i]).group(1) in (' ', None))
        if n:
            total += n
            print('  %-60s %d' % (s.name[:60], n))
    print('  %-60s %d' % ('total', total))
    stray = [b.task_id(i) or 'L%d' % (i + 1) for s in b.sections() if s.kind not in ('done', 'howto', 'now')
             for i in b.tasks_in(s) if TASK.match(b.lines[i]).group(1) == 'x']
    if stray:
        print('Done lines outside Done (%d): %s' % (len(stray), ', '.join(stray)))
    stale = b.stale_pointers()
    if stale:
        print('Stale Now pointers: %s' % ', '.join(t for _, t in stale))
    print(b.next_free())


def cmd_next(b, a):
    shown = set()
    now = b.kind('now')
    print('Now:')
    ptrs = b.tasks_in(now) if now else []
    say(*['  ' + b.lines[i] for i in ptrs] or ['  (empty)'])
    for i in ptrs:
        tid = b.task_id(i)
        if tid:
            shown.add(tid)
    for _, tid in b.stale_pointers():
        print('  Stale: %s is already done or dropped.' % tid)
    wip = [i for s in b.sections() if s.kind not in ('now', 'howto')
           for i in b.tasks_in(s) if TASK.match(b.lines[i]).group(1) == '~' and b.task_id(i) not in shown]
    if wip:
        print('In progress:')
        say(*['  ' + b.lines[i] for i in wip])
        shown.update(b.task_id(i) for i in wip)
    for s in b.sections():
        if s.kind != 'work':
            continue
        top = [i for i in b.tasks_in(s) if TASK.match(b.lines[i]).group(1) == ' '
               and b.task_id(i) not in shown][:3]
        if top:
            print('## ' + s.name)
            say(*['  ' + b.lines[i] for i in top])


def cmd_show(b, a):
    is_id = ID_ARG.fullmatch(a.target)
    found = False
    for i, line in enumerate(b.lines):
        if b.has_id(line, a.target.upper()) if is_id else a.target.lower() in line.lower():
            s = b.section_at(i)
            print(cut('L%d [%s] %s' % (i + 1, s.name if s else '-', line), a.full))
            found = True
    if not found:
        die('no line matches "%s".' % a.target)
    if is_id:
        ref = re.compile(r'\b%s(?!\d)' % re.escape(a.target.upper()))
        others = [b.task_id(i) or 'L%d' % (i + 1) for i, line in enumerate(b.lines)
                  if TASK.match(line) and not b.has_id(line, a.target.upper()) and ref.search(line)]
        if others:
            print('Mentioned in: ' + ', '.join(others))


def cmd_add(b, a):
    s = b.section(a.section or ('Bugs' if a.bug else 'Inbox'))
    ids = b.allocate(len(a.text))
    lines = ['- [ ] %s %s' % (tid, t.strip()) for tid, t in zip(ids, a.text)]
    if a.top:
        lines.reverse()
    for line in lines:
        b.insert(b.section(s.name), line, a.top)
    b.save()
    print('Added to %s:' % s.name)
    say(*['  ' + l for l in (reversed(lines) if a.top else lines)])
    print(b.next_free())


def cmd_start(b, a):
    i = b.find(a.target)
    m = TASK.match(b.lines[i])
    if m.group(1) in ('x', '-'):
        die('%s is already %s.' % (a.target, 'done' if m.group(1) == 'x' else 'dropped'))
    tid = b.ensure_id(i)
    line = b.remark(i, '~')
    stale = b.stale_pointers()
    for p, _ in sorted(stale, reverse=True):
        b.remove(p)
    ptr = b.add_pointer(b.find(b.task_id(i)))
    b.save()
    say('Started: ' + line)
    if stale:
        print('Removed stale Now pointers: %s' % ', '.join(t for _, t in stale))
    if ptr:
        say('Now: ' + ptr)
    if tid:
        print(b.next_free())


def cmd_now(b, a):
    i = b.find(a.target)
    tid = b.ensure_id(i)
    ptr = b.add_pointer(b.find(b.task_id(i)))
    b.save()
    say('Now: ' + ptr if ptr else '%s is already in Now.' % b.task_id(i))
    if tid:
        print(b.next_free())


def cmd_done(b, a):
    i = b.find(a.target)
    if TASK.match(b.lines[i]).group(1) == 'x':
        die('%s is already done.' % a.target)
    from_section = b.section_at(i).name
    b.remark(i, 'x', date=b.today, append=a.note)
    tid = b.task_id(i)
    line = b.remove(i)
    done = b.kind('done')
    if not done:
        die('no Done section.')
    b.insert(done, line, top=True)
    removed = b.drop_pointers(tid) if tid else 0
    now = b.kind('now')
    b.save()
    say('Done (from %s): %s' % (from_section, line))
    if removed:
        print('Removed %s from Now.' % tid)
    if now and not b.tasks_in(now):
        print('Now is empty.')


def cmd_drop(b, a):
    i = b.find(a.target)
    why = a.why.strip().rstrip('.')
    line = b.remark(i, '-', append='Dropped %s: %s.' % (b.today, why))
    tid = b.task_id(i)
    removed = b.drop_pointers(tid) if tid else 0
    b.save()
    say('Dropped: ' + line)
    if removed:
        print('Removed %s from Now.' % tid)


def cmd_move(b, a):
    i = b.find(a.target)
    src = b.section_at(i)
    dest = b.section(a.section)
    if dest.kind == 'now':
        die('Now holds pointers; use `now <id>` instead.')
    m = TASK.match(b.lines[i])
    if dest.kind == 'done' and (m.group(1) != 'x' or not m.group(2)):
        die('only a dated [x] line moves to Done; use `done <id>` to finish a task.')
    tid = b.ensure_id(i) if src.kind == 'inbox' and dest.kind != 'inbox' else None
    line = b.remove(i)
    dest = b.section(dest.name)
    if dest.kind == 'done' and not a.top:
        # Done is newest first: go above the first entry older than this one.
        older = [k for k in b.tasks_in(dest) if (TASK.match(b.lines[k]).group(2) or '') < m.group(2)]
        if older:
            b.lines.insert(older[0], line)
        else:
            b.insert(dest, line)
    else:
        b.insert(dest, line, a.top)
    b.save()
    say('Moved %s → %s%s: %s' % (src.name, dest.name, ' (top)' if a.top else '', line))
    if tid:
        print('Promoted with new ID %s. %s' % (tid, b.next_free()))


def cmd_split(b, a):
    i = b.find(a.target)
    tid = b.task_id(i)
    if not tid:
        die('give the line an ID first (move it out of the Inbox).')
    ids = b.allocate(len(a.parts))
    parts = ['- [ ] %s %s' % (n, p.strip()) for n, p in zip(ids, a.parts)]
    line = b.remark(i, '-', append='Split into %s %s.' % (', '.join(ids), b.today))
    b.lines[i + 1:i + 1] = parts
    ptrs = b.now_pointers(tid)
    for p in reversed(ptrs):
        b.lines[p:p + 1] = [b.pointer(b.find(n)) for n in ids]
    b.save()
    say('Split: ' + line, *['  ' + p for p in parts])
    if ptrs:
        print('Now: %s replaced by %s.' % (tid, ', '.join(ids)))
    print(b.next_free())


def locate(arg):
    if arg:
        return arg
    try:
        root = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        root = os.getcwd()
    return os.path.join(root, 'docs', 'backlog.md')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--file', help='backlog path (default: <git root>/docs/backlog.md)')
    ap.add_argument('--date', help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status', help='Now, in progress, open counts, next free ID')
    sub.add_parser('next', help='Now, in progress, top 3 open per work section')
    p = sub.add_parser('show', help='lines matching an ID or text, with their section')
    p.add_argument('target')
    p.add_argument('--full', action='store_true', help='do not truncate long lines')
    p = sub.add_parser('add', help='new tasks with fresh IDs (Inbox by default)')
    p.add_argument('text', nargs='+', help='one argument per task: "Title. Context."')
    p.add_argument('--section', help='target section, matched loosely')
    p.add_argument('--bug', action='store_true', help='add to Bugs')
    p.add_argument('--top', action='store_true', help='insert at the top of the section')
    for name, helptext in (('start', 'mark [~] and point Now at it'), ('now', 'point Now at a task')):
        sub.add_parser(name, help=helptext).add_argument('target')
    p = sub.add_parser('done', help='mark [x] with the date, move to the top of Done')
    p.add_argument('target')
    p.add_argument('note', nargs='?')
    p = sub.add_parser('drop', help='mark [-] with the reason, leave in place')
    p.add_argument('target')
    p.add_argument('why')
    p = sub.add_parser('move', help='move to another section (end, or --top)')
    p.add_argument('target')
    p.add_argument('section')
    p.add_argument('--top', action='store_true')
    p = sub.add_parser('split', help='replace a task with new parts right under it')
    p.add_argument('target')
    p.add_argument('parts', nargs='+')
    a = ap.parse_args()

    path = locate(a.file)
    if not os.path.isfile(path):
        die('%s does not exist. Run /backlog init.' % path, 2)
    today = a.date or datetime.date.today().isoformat()
    lock = os.open(os.path.dirname(os.path.abspath(path)), os.O_RDONLY)
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        globals()['cmd_' + a.cmd](Backlog(path, today), a)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        os.close(lock)


if __name__ == '__main__':
    main()

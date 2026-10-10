'''Changing tiles.toml by hand-surgery on its text. Pure.

tomllib only reads. Writing the file back from data would lose every
comment and the user's layout, so each change touches the few lines it is
about and nothing else: the block of one tile, its `size` or `group` line,
the `groups` list. Every operation returns the new text together with
what the data should look like afterwards; verify() reads the new text
and compares. Anything unexpected -- an inline table, a value spread over
lines -- fails that check, and then nothing is written.
'''

import copy
import re
import tomllib

TILE = re.compile(r'^\s*\[\[\s*tile\s*\]\]')
SHORTCUT = re.compile(r'^\s*\[\[\s*tile\s*\.\s*shortcut\s*\]\]')
TABLE = re.compile(r'^\s*\[')
QUIET = re.compile(r'^\s*(#.*)?$')          # blank or comment only
VALUE = re.compile(r'^(\s*{key}\s*=\s*)("(?:[^"\\]|\\.)*"|\'[^\']*\')(.*)$')


class EditError(Exception):
    '''A change that cannot be made safely; the message says why.'''


def toml_string(text):
    '''A basic TOML string: "…" with \\, " and control characters escaped.'''
    out = text.replace('\\', '\\\\').replace('"', '\\"')
    out = out.replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')
    return f'"{out}"'


def _lines(text):
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith('\n'):
        lines[-1] += '\n'
    return lines


def blocks(text):
    '''[(start, end)] for every [[tile]], as line indexes, end exclusive.

    A block runs from its header to the next table that is not one of its
    own shortcuts, without the blank and comment lines right before that:
    those introduce the next one.'''
    lines = _lines(text)
    starts = [i for i, line in enumerate(lines) if TILE.match(line)]
    found = []
    for start in starts:
        end = len(lines)
        for i in range(start + 1, len(lines)):
            if TABLE.match(lines[i]) and not SHORTCUT.match(lines[i]):
                end = i
                break
        while end > start + 1 and QUIET.match(lines[end - 1]):
            end -= 1
        found.append((start, end))
    return found


def _block(lines, text, line):
    '''(index in the tile list, start, end) for the tile whose header is on
    1-based `line`.'''
    for index, (start, end) in enumerate(blocks(text)):
        if start + 1 == line:
            return index, start, end
    raise EditError(f'keine Kachel in Zeile {line}')


def _own_end(lines, start, end):
    '''Where the tile's own keys end: at its first shortcut.'''
    for i in range(start + 1, end):
        if SHORTCUT.match(lines[i]):
            return i
    return end


def _find_key(lines, start, stop, key):
    pattern = re.compile(rf'^\s*{key}\s*=')
    for i in range(start, stop):
        if pattern.match(lines[i]):
            return i
    return None


def _key_line(lines, start, stop, key, value):
    '''A new `key = value` line, its = lined up with the group line's.'''
    width, indent = len(key), ''
    near = _find_key(lines, start, stop, 'group')
    if near is not None:
        line = lines[near]
        indent = line[:len(line) - len(line.lstrip())]
        width = max(width, line.index('=') - len(indent) - 1)
    return f'{indent}{key.ljust(width)} = {value}\n'


def _replace_value(line, key, value):
    match = re.match(VALUE.pattern.format(key=key), line.rstrip('\n'))
    if match is None:
        raise EditError(f'{key} hat eine Schreibweise, die ich nicht '
                        'sicher ändern kann')
    return f'{match[1]}{value}{match[3]}\n'


def _data(text):
    return tomllib.loads(text)


# -- the operations --------------------------------------------------------

def set_size(text, line, size):
    lines = _lines(text)
    index, start, end = _block(lines, text, line)
    own = _own_end(lines, start, end)
    at = _find_key(lines, start + 1, own, 'size')
    if at is not None:
        lines[at] = _replace_value(lines[at], 'size', toml_string(size))
    else:
        after = _find_key(lines, start + 1, own, 'app')
        if after is None:
            after = _find_key(lines, start + 1, own, 'group')
        if after is None:
            after = start
        lines.insert(after + 1, _key_line(lines, start + 1, own, 'size',
                                          toml_string(size)))

    def expect(data):
        data['tile'][index]['size'] = size
    return ''.join(lines), expect


def set_group(text, line, group):
    '''Another group, and no `pos`: the old place rarely fits there.'''
    lines = _lines(text)
    index, start, end = _block(lines, text, line)
    own = _own_end(lines, start, end)
    at = _find_key(lines, start + 1, own, 'group')
    if at is None:
        raise EditError('die Kachel hat keine group-Zeile')
    lines[at] = _replace_value(lines[at], 'group', toml_string(group))
    pos = _find_key(lines, start + 1, own, 'pos')
    if pos is not None:
        if lines[pos].count('[') != lines[pos].count(']'):
            raise EditError('pos steht über mehrere Zeilen')
        del lines[pos]

    def expect(data):
        data['tile'][index]['group'] = group
        data['tile'][index].pop('pos', None)
    return ''.join(lines), expect


def remove_tile(text, line):
    '''The tile and every shortcut of it. Comments around stay.'''
    lines = _lines(text)
    index, start, end = _block(lines, text, line)
    del lines[start:end]
    # Two blank lines meeting where the block was: one is enough.
    if 0 < start < len(lines) and not lines[start].strip() \
            and not lines[start - 1].strip():
        del lines[start]

    def expect(data):
        del data['tile'][index]
        if not data['tile']:
            del data['tile']
    return ''.join(lines), expect


def add_tile(text, group, app):
    '''A new tile for `app` in `group`: behind the group's last tile, or at
    the end of the file.'''
    lines = _lines(text)
    data = _data(text) if text.strip() else {}
    tiles = data.get('tile', [])
    found = blocks(text)
    if len(found) != len(tiles):
        raise EditError('die Kacheln in der Datei sind nicht eindeutig')
    last = None
    for index, raw in enumerate(tiles):
        if isinstance(raw, dict) and raw.get('group') == group:
            last = index
    new = ['\n', '[[tile]]\n', f'group = {toml_string(group)}\n',
           f'app   = {toml_string(app)}\n', 'size  = "medium"\n']
    if last is not None:
        at = found[last][1]
        position = last + 1
    else:
        at = len(lines)
        position = len(tiles)
        while at > 0 and not lines[at - 1].strip():
            at -= 1
        if at == 0:
            new = new[1:]
    lines[at:at] = new

    def expect(data):
        data.setdefault('tile', []).insert(
            position, {'group': group, 'app': app, 'size': 'medium'})
    return ''.join(lines), expect


def _list_span(text, start):
    '''(open, close) offsets of the [...] that starts at or after `start`,
    with brackets inside strings not counting.'''
    open_at = text.index('[', start)
    depth, i, quote = 0, open_at, None
    while i < len(text):
        c = text[i]
        if quote:
            if c == '\\' and quote == '"':
                i += 1
            elif c == quote:
                quote = None
        elif c in '"\'':
            quote = c
        elif c == '#':
            i = text.find('\n', i)
            if i < 0:
                break
        elif c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                return open_at, i
        i += 1
    raise EditError('die groups-Liste ist nicht geschlossen')


def _blank_comments(text):
    '''`text` with every # comment turned into spaces, same length; a #
    inside a string is not a comment.'''
    out, quote, i = list(text), None, 0
    while i < len(text):
        c = text[i]
        if quote:
            if c == '\\' and quote == '"':
                i += 1
            elif c == quote:
                quote = None
        elif c in '"\'':
            quote = c
        elif c == '#':
            while i < len(text) and text[i] != '\n':
                out[i] = ' '
                i += 1
            continue
        i += 1
    return ''.join(out)


def add_group(text, name):
    '''`name` at the end of `groups = [...]`, however that list is laid
    out; or a new `groups` line if there is none.'''
    match = re.search(r'^[ \t]*groups[ \t]*=', text, re.MULTILINE)
    first_table = re.search(r'^\s*\[', text, re.MULTILINE)
    if match and first_table and match.start() > first_table.start():
        match = None   # a 'groups' key inside some table is not ours
    quoted = toml_string(name)
    if match is None:
        new = f'groups = [{quoted}]\n'
        at = first_table.start() if first_table else len(text)
        if text and at == len(text) and not text.endswith('\n'):
            new = '\n' + new
        out = text[:at] + new + ('\n' if first_table else '') + text[at:]
    else:
        open_at, close = _list_span(text, match.end())
        inside = text[open_at + 1:close]
        # Comments as spaces, so offsets in `body` are offsets in `inside`.
        body = _blank_comments(inside)
        last = len(body.rstrip())          # end of the last element or ','
        if not body.strip():
            insertion, at = quoted, open_at + 1
            out = text[:at] + insertion + text[close:]
        else:
            at = open_at + 1 + last
            trailing = body.rstrip().endswith(',')
            if '\n' in inside[last:]:
                # One element per line: a new line, indented like the last.
                line_start = text.rfind('\n', 0, at) + 1
                indent = re.match(r'[ \t]*', text[line_start:])[0]
                insertion = ('' if trailing else ',') + \
                    f'\n{indent}{quoted}' + (',' if trailing else '')
            else:
                insertion = (' ' if trailing else ', ') + quoted
            out = text[:at] + insertion + text[at:]

    def expect(data):
        data.setdefault('groups', []).append(name)
    return out, expect


# -- checking --------------------------------------------------------------

def verify(old_text, new_text, *expectations):
    '''None if `new_text` reads as `old_text` with exactly the expected
    changes, otherwise what is wrong.'''
    try:
        expected = _data(old_text) if old_text.strip() else {}
    except tomllib.TOMLDecodeError:
        return 'tiles.toml ist gerade kein gültiges TOML'
    expected = copy.deepcopy(expected)
    for expect in expectations:
        try:
            expect(expected)
        except (KeyError, IndexError, TypeError):
            return 'die Datei sieht anders aus als erwartet'
    try:
        got = _data(new_text)
    except tomllib.TOMLDecodeError as error:
        return f'die Änderung ergäbe kein gültiges TOML ({error})'
    if got != expected:
        return 'die Änderung hätte mehr verändert als gewollt'
    return None


def apply(text, *operations):
    '''Run operations one after the other -> (new text, None) or
    (None, why not). Each operation is (function, args...). Line numbers
    refer to the text as it is then, so a change to the `groups` list,
    which may add a line above the tiles, goes last.'''
    new, expectations = text, []
    try:
        for function, *args in operations:
            new, expect = function(new, *args)
            expectations.append(expect)
    except (EditError, ValueError, tomllib.TOMLDecodeError) as error:
        return None, str(error)
    problem = verify(text, new, *expectations)
    return (None, problem) if problem else (new, None)

"""C6T - C version 6 by Troy - Preprocessor"""

from pathlib import Path, PurePosixPath
from collections import deque
from typing import Iterable, Iterator
import re

import util


def strip_comments(text: str) -> str:
    """Return a version of the text with C6T comments stripped out."""
    out = ''
    i = 0
    while i < len(text):
        if text[i:].startswith('/*'):
            i += 2
            while i < len(text) and not text[i:].startswith('*/'):
                i += 1
            i += 2
        else:
            out += text[i]
            i += 1
    return out


class Includer(Iterable[str]):
    """Returns lines from a given source, with support for singular-depth
    includes.
    """

    def __init__(self, source: str):
        self._lines = deque(source.splitlines(
            keepends=True))  # type:deque[str]
        self.errs = 0
        self.in_include = False

    def include(self, line: int, filename: str) -> None:
        """Try to include the given filename."""
        if self.in_include:
            util.error(self, 'includes only support one depth', line)
            return
        path = Path(PurePosixPath(filename))
        if not path.exists:
            util.error(self,
                       f'unable to open file "{PurePosixPath(filename)}"',
                       line)
        self._lines = deque(['@'] + path.read_text('utf8').splitlines(
            keepends=True) + ['@'] + list(self._lines))

    def insert(self, line: str) -> None:
        """Insert the line to the front of our list."""
        self._lines.insert(0, line)

    def __next__(self) -> str:
        """Return the next line from the input.
        """
        try:
            line = self._lines.popleft()
        except IndexError as error:
            raise StopIteration from error
        if line == '@':
            self.in_include = not self.in_include
        return line

    def __iter__(self) -> Iterator[str]:
        return self


def replace(line: str, macros: dict[str, str]) -> str:
    """Return a version of the line with macros replaced.
    """
    out = ''
    keys = sorted(macros.keys(), key=len, reverse=True)

    i = 0
    while i < len(line):
        found = False
        for key in keys:
            if line[i:].startswith(key):
                out += macros[key]
                i += len(key)
                found = True
                break
        if not found:
            out += line[i]
            i += 1
    return out


def preproc(source: str) -> str:  # pylint:disable=too-many-branches
    r"""Return a preprocessed version of the source code.

    >>> path = Path('test.c')
    >>> preproc(path.read_text())
    '\n\n/* testing */\n\n\n\n\n@int foo, bar;\n@\nint foobar[]  foo  ,  bar ;\n'
    """
    if source[0] != '#':
        return source
    macros = {}  # type:dict[str, str]
    lines = Includer(source)
    out = ''
    curline = 0
    countlines = True

    for line in lines:
        if line == '@':
            countlines = not countlines
        if countlines:
            curline += line.count('\n')
        if line.startswith('#'):
            out += '\n'
            line = line[1:].strip()
            if line.startswith('define'):
                elems = line.split(maxsplit=2)
                if len(elems) < 3:
                    util.error(lines, 'bad define', curline)
                    continue
                if elems[1] in macros:
                    util.error(lines, f'macro {elems[1]} already defined')
                else:
                    macros[elems[1]] = ' ' + strip_comments(elems[2]) + ' '
            elif line.startswith('include'):
                match = re.match(r'^include\s+"([^"]*)"\s*$', line)
                if match:
                    lines.include(curline, match[1])
                else:
                    util.error(lines, 'bad include', curline)
        else:
            out += replace(line, macros)
    return out


if __name__ == "__main__":
    import doctest
    doctest.testmod()

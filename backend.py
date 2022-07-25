"""C6T - C version 6 by Troy - Universal Backend Section"""

from __future__ import annotations
from pathlib import Path
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable, Sequence
from pprint import pp

AtomType = str | int | float

NODECHILDREN: dict[str, int] = {
    'register': 0,
    'auto': 0,
    'load': 1,
    'store': 2,
    'extern': 0,
    'call': 0,
    'con': 0,
    'add': 2,
    'great': 2,
    'arg': 1,
    'sub': 2,
    'lognot': 1,
    'uless': 2,
    'postinc': 2,
    'cstore': 2,
    'logor': 2,
    'logand': 2,
    'equ': 2,
    'mult': 2,
    'cond': 3,
    'gequ': 2,
    'lequ': 2,
    'cload': 1,
    'nequ': 2,
    'less': 2,
}


@dataclass
class Command(Sequence):
    """An assembly instruction."""
    cmd: str
    args: list[str | int] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.args)

    def __getitem__(self, key) -> AtomType:
        return self.args[key]


@dataclass
class Label:
    """A defined assembly label."""
    lab: str


@dataclass
class Node:
    """A backend node."""
    label: str
    children: list[Node] = field(default_factory=list)
    value: AtomType | None | list[AtomType] = None
    info: dict = field(default_factory=dict)

    def __iter__(self):
        return iter(self.children)

    def __len__(self):
        return len(self.children)

    def __getitem__(self, key):
        return self.children[key]


class CodeGen(ABC):
    """Contains specific codegen details for your platform."""
    @abstractmethod
    def reset(self) -> None:
        """Reset the codegen backend for a new runthru on a new IR."""
        raise NotImplementedError

    @abstractmethod
    def getasm(self) -> str:
        """Return the assembled output."""
        raise NotImplementedError

    @abstractmethod
    def command(self, command: Command, nodestk: list[Node]) -> None:
        """Run an assembly command."""
        raise NotImplementedError

    @abstractmethod
    def deflabel(self, lab: str) -> None:
        """Define the given label here."""
        raise NotImplementedError


class IRParser(Iterable[Node | Command | Label]):
    """Parses IR representation."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.i = 0

    @property
    def linenum(self) -> int:
        """Current input line number."""
        return 1 + self.source[:self.i].count('\n')

    @property
    def text(self) -> str:
        """Return the IR source from the given index position on."""
        return self.source[self.i:]

    def __iter__(self):
        return self

    def skipws(self) -> bool:
        """Skip leading whitespace, NOT including newlines. Return a flag for
        if we saw any.
        """
        if match := re.match(r'(([^\S\n]+)|(;[^\n]*))+', self.text,
                             re.MULTILINE):
            assert '\n' not in match[0]
            self.i += len(match[0])
            return True
        return False

    def skipws_nl(self) -> None:
        """Skip leading whitespace INCLUDING newlines."""
        while True:
            if not self.skipws():
                if match := re.match('\n+', self.text):
                    self.i += len(match[0])
                else:
                    break

    def atom(self) -> AtomType:
        """Remove the next atom from the source, returning it."""
        self.skipws()
        if match := re.match(r'[^\s,\n:]+', self.text):
            self.i += len(match[0])
            try:
                return int(match[0])
            except ValueError:
                try:
                    return float(match[0])
                except ValueError:
                    return match[0]
        raise ValueError('no atom here')

    def match(self, text: str) -> bool:
        """If we match the given text, skip past it and return Ture. Else,
        skip nothing and return False. Skips leading whitespace first.
        """
        self.skipws()
        if self.text.startswith(text):
            self.i += len(text)
            return True
        return False

    def __next__(self) -> Node | Command | Label:
        self.skipws_nl()
        if not self.text:
            raise StopIteration
        atom = str(self.atom())
        if self.match(':'):
            return Label(atom)
        args = []
        if not self.match('\n'):
            args = [self.atom()]
            while self.match(','):
                args.append(self.atom())
        if atom in NODECHILDREN:
            if len(args) == 0:
                val = None
            elif len(args) == 1:
                val = args[0]
            else:
                val = args
            return Node(atom, [], val)
        return Command(atom, args)


def backend(source: str, codegen: CodeGen) -> str:
    """Perform backend codegen from the given source Intermediate
    Representation.
    """
    codegen.reset()
    nodestk: list[Node] = []

    parser = IRParser(source)
    for elem in parser:
        if isinstance(elem, Node):
            if elem.label in NODECHILDREN:
                if elem.label == 'call':
                    assert isinstance(elem.value, int)
                    count = elem.value + 1
                else:
                    count = NODECHILDREN[elem.label]
                if count:
                    if len(nodestk) < count:
                        raise ValueError('not enough nodes')
                    elem.children.extend(nodestk[-count:])
                    del nodestk[-count:]
            nodestk.append(elem)
        elif isinstance(elem, Label):
            codegen.deflabel(elem.lab)
        elif isinstance(elem, Command):
            codegen.command(elem, nodestk)
        else:
            raise TypeError('bad parse elem')

    return codegen.getasm()


def test():
    """Test the IR parser."""
    path = Path('wrap.ir')
    with open('wrap.parsed', 'w', encoding='utf8') as outfile:
        pp(list(IRParser(path.read_text('utf8'))), stream=outfile)


if __name__ == "__main__":
    test()

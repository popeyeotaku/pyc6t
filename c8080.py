"""C6T - C version 6 by Troy - Intel 8080 Backend"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, IntEnum, auto
from typing import Any, Iterator, Mapping
from pathlib import Path
import json

from backend import CodeGen, Command, Node as BackNode, backend as dobackend
import c6t

PathType = Path | str

SEGMENTS = (
    '.text', '.data', '.string', '.bss'
)


def newsegs() -> dict[str, str]:
    """Construct a new segs dictionary."""
    segs = {}
    for seg in SEGMENTS:
        segs[seg] = ''
    return segs


class Reg(IntEnum):
    """Intel 8080 physical registers."""
    HL = 0
    DE = 1


class TRegs(Enum):
    """Specifies which registers results and operand are from.
    """
    HL = auto()
    DE_HL = auto()
    DE_DE = auto()
    ANY = auto()
    BINARY = auto()
    SPECIAL = auto()


@dataclass(frozen=True)
class Node:
    """An expression node."""
    label: str
    left: Node | None = None
    right: Node | None = None
    value: Any | None = field(default=None, hash=False, compare=False)


@dataclass
class CodeState:
    """Codegen state."""
    curtemp: int = 0
    segs: dict[str, str] = field(default_factory=newsegs)
    curseg: str = '.text'

    def temp(self) -> str:
        """Return the next temporary label."""
        self.curtemp += 1
        return f"LL{self.curtemp}"


@dataclass(frozen=True)
class Require:
    """Requirements for a code-gen template to match a node."""
    label: str | None = None
    value: Any | None = field(default=None, hash=False, compare=False)

    def __post_init__(self):
        if self.label is not None and not isinstance(self.label, str):
            raise TypeError('label', self.label)

    def match(self, node: Node | None) -> bool:
        """Return a flag for if we match the node."""
        if node is None:
            return True
        if not isinstance(node, Node):
            raise TypeError
        if self.label is None:
            return True
        if self.label != node.label:
            return False
        if self.value is None:
            return True
        return self.value == node.value


@dataclass(frozen=True)
class Template:
    """A code-gen template."""
    require: Require
    action: str
    regs: TRegs = TRegs.BINARY
    leftreq: Require = Require
    rightreq: Require = Require

    def __post_init__(self):
        for req in 'require', 'leftreq', 'rightreq':
            reqlist = getattr(self, req)
            if isinstance(reqlist, list):
                # pylint:disable=not-an-iterable
                object.__setattr__(self, req, Require(*reqlist))
        if isinstance(self.action, list):
            actstr = ''
            for elem in self.action:
                actstr += elem + '\n'
            if actstr.endswith('\n'):
                actstr = actstr[:-1]
            object.__setattr__(self, 'action', actstr)
        if not isinstance(self.regs, TRegs):
            object.__setattr__(self, 'regs', TRegs(self.regs))
        if self.require.label is None:
            raise ValueError('main Require for a Template (template.require) '
                             'cannot be None')

    def match(self, node: Node) -> bool:
        """Try to match this template against a given node."""
        return all((require.match(node) for require in
                    (self.require, self.leftreq, self.rightreq)))

    def expand(self, state: CodeState, node: Node, reg: Reg = Reg.HL) -> str:
        """Return an expanded version of the node."""
        temp1 = None

        action = self.action
        if 'T1' in action:
            temp1 = state.temp()

        action.replace('LV', node.left.value)
        action.replace('RV', node.right.value)
        action.removeprefix('V', node.value)
        action.replace('R', Reg(reg).name[0].lower())

        out = ''
        for line in action.splitlines():
            line = f'\t{line}\n'
            if 'DT1' in line:
                out += f'{temp1}:\n'
            else:
                out += line
        return out


class Scheme(Mapping[str, tuple[Template, ...]]):
    """A collection of codegen templates."""

    def __init__(self, *templates: Template):
        self._templs: dict[str, list[Template]] = {}
        for template in templates:
            self.add(template)

    def add(self, template: Template) -> None:
        """Add the template to this scheme."""
        if not isinstance(template, Template):
            raise TypeError
        label = template.require.label
        assert label is not None
        if label not in self._templs:
            self._templs[label] = []
        tlist = self._templs[label]
        if template in tlist:
            raise ValueError('template already in scheme')
        tlist.append(template)

    def __getitem__(self, key: str) -> tuple[Template, ...]:
        return tuple(self._templs[key])

    def __iter__(self) -> Iterator[str]:
        return iter(self._templs)

    def __len__(self) -> int:
        return len(self._templs)

    @staticmethod
    def from_json(source: str) -> Scheme:
        """Generate a Scheme from a json spec."""
        templs = json.loads(source)
        scheme = Scheme()
        if not isinstance(templs, list):
            raise TypeError
        for templ in templs:
            if not isinstance(templ, dict):
                raise TypeError
            scheme.add(Template(**templ))


class Code80(CodeGen):
    """Code generator for Intel 8080."""

    def __init__(self, templates: PathType = 'c8080.json') -> None:
        super().__init__()
        self.state: CodeState = CodeState()
        path = Path(templates)
        scheme = path.read_text('utf8')
        self.scheme: Scheme = Scheme.from_json(scheme)

    def reset(self) -> None:
        self.state = CodeState()

    def getasm(self) -> str:
        out = ''
        for seg in SEGMENTS:
            out += self.state.segs[seg]
        return out

    def asm(self, code: str) -> None:
        """Add the assembly to the current segment."""
        assert self.state.curseg in SEGMENTS
        self.state.segs[self.state.curseg] += code

    def asmlines(self, *lines: str) -> None:
        """Assemble to output the lines with leading tabs."""
        for line in lines:
            self.asm(f'\t{line}\n')

    def deflabel(self, lab: str) -> None:
        self.asm(f'{lab}:\n')

    def command(self, command: Command, nodestk: list[BackNode]) -> None:
        if command.cmd in self.scheme:
            if command.args:
                arg = command.args[0]
            else:
                arg = None
            fakenode = Node(command.cmd, value=arg)
            out = self.scheme[command.cmd][0].expand(self.state, fakenode)
            self.asm(out)
        match command.cmd:
            case _:
                raise ValueError(command)


def test(source: PathType):
    """Run a test program."""
    path = Path(source)
    irsrc = c6t.compile_c6t(path.read_text('utf8'))
    path.with_suffix('.ir').write_text(irsrc, 'utf8')
    codegen = Code80()
    asm = dobackend(irsrc, codegen)
    path.with_suffix('.s').write_text(asm, 'ascii')


if __name__ == "__main__":
    test('hello.c')

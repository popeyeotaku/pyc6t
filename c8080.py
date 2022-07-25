"""C6T - C version 6 by Troy - Intel 8080 Backend"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, IntEnum, auto
from typing import Any, Iterator, Mapping
from pathlib import Path
import json

from backend import CodeGen, Command, Node as BackNode, backend as dobackend
import c6t

ASM_HEADER = """
    .target "8080"
    .format "bin"
    .setting "CaseSensitiveMode",true
    .setting "Debug",true
    .setting "DebugFile","hello.sym"
    
    
    .org 0
; C6T Standard Header for Intel 8080

start:
    lxi sp,$F000
    call _main
_exit:
    hlt
    jmp _exit

cret:
    mov l,c
    mov h,b
    sphl
    pop h
    shld reg2
    pop h
    shld reg1
    pop h
    shld reg0
    pop b
    ret

reg0: .word 0
reg1: .word 0
reg2: .word 0

cextend:
    mvi h,0
    mov a,l
    rlc
    jnc noextend
    dcr h
noextend:
    ret

_in80:
    lxi h,2
    dad sp
    mov a,m
    sta inrel+1
inrel:
    in 0
    mov l,a
    call cextend
    ret

_out80:
    lxi h,2
    dad sp
    mov a,m
    sta outrel+1
    lxi h,4
    dad sp
    mov a,m
outrel:
    out 0
    ret


"""

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
    HL = 1
    DE = 2


class TRegs(Enum):
    """Specifies which registers results and operand are from.
    """
    HL = auto()
    DE = auto()
    ANY = auto()
    BINARY = auto()
    SPECIAL = auto()


@dataclass(frozen=True)
class Node:
    """An expression node."""
    label: str
    left: Node | None = None
    right: Node | None = None
    value: Any | None = None

    @property
    def children(self) -> tuple[Node | None, Node | None]:
        """Return this node's children."""
        return self.left, self.right

    @classmethod
    def join(cls, label: str, *nodes: Node) -> Node:
        """Join a bunch of nodes binarily using the given label.

        Each node of that label will have its value as the left child (one of
        the nodes), and either another node of that label as its right child,
        or None if end of the list.
        """
        if len(nodes) == 0:
            return Node(label)
        start = Node(label, nodes[0])
        for node in nodes[1:]:
            start = cls._joinrep(start, node)
        return start

    @classmethod
    def _joinrep(cls, node: Node, append: Node) -> Node:
        """Append the given node to the end of the chain, returning the new
        one, recursively.
        """
        if node.right:
            return Node(node.label, node.left,
                        cls._joinrep(node.right, append), node.value)
        return Node(node.label, node.left, append, node.value)


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
    leftreq: Require = field(default_factory=Require)
    rightreq: Require = field(default_factory=Require)
    commutative: bool = False
    flags:tuple[str] = ()

    def __post_init__(self):
        if not isinstance(self.flags, tuple):
            object.__setattr__(self, 'flags', tuple(self.flags))
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
            object.__setattr__(self, 'regs', TRegs[self.regs])
        if self.require.label is None:
            raise ValueError('main Require for a Template (template.require) '
                             'cannot be None')

    def match(self, node: Node) -> bool:
        """Try to match this template against a given node."""
        return self.require.match(node) and self.leftreq.match(node.left) \
            and self.rightreq.match(node.right)

    def expand(self, state: CodeState, node: Node, reg: Reg = Reg.HL) -> str:
        """Return an expanded version of the node."""
        temp1 = None

        action = self.action
        if 'T1' in action or 'D1' in action:
            temp1 = state.temp()

        action = action.replace('T1', str(temp1))
        action = action.replace('RLOW', Reg(reg).name[1].lower())
        if node.left:
            action = action.replace('LV', str(node.left.value))
        if node.right:
            action = action.replace('RV', str(node.right.value))
        action = action.replace('V', str(node.value))
        action = action.replace('R', Reg(reg).name[0].lower())

        out = ''
        for line in action.splitlines():
            line = f'\t{line}\n'
            if 'D1' in line:
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
        return scheme


class CachedMatcher:
    """Caches matches from nodes to templates."""

    def __init__(self, scheme: Scheme) -> None:
        self._scheme = scheme
        self._cache: dict[tuple[Node, Reg], Template] = {}

    def match(self, node: Node, reg: Reg) -> Template:
        """Match the given node and register to a template."""
        try:
            return self._cache[(node, reg)]
        except KeyError:
            matched = self._match(node, reg)
            self._cache[(node, reg)] = matched
            return matched

    def require(self, node: Node, *templs: Template) -> list[Template]:
        """Return only those templates whose requirements match the node."""
        return [templ for templ in templs if templ.match(node)]

    def _match(self, node: Node, reg: Reg) -> Template:
        """Find a new matching template."""
        templs = self.require(node, *self._scheme[node.label])
        # Try to match unarily DE or HL first
        if reg == Reg.DE:
            checks = [templ for templ in templs if templ.regs in (TRegs.DE,
                                                                  TRegs.ANY)]
            if checks:
                return checks[0]
            return self.match(node, Reg.HL)
        if reg == Reg.HL:
            checks = [templ for templ in templs if templ.regs in (TRegs.HL,
                                                                  TRegs.ANY)]
            if checks:
                return checks[0]
        # Finally, try a SPECIAL or BINARY
        if templs:
            return templs[0]
        raise ValueError('no match', node, reg)


class Code80(CodeGen):
    """Code generator for Intel 8080."""

    def __init__(self, templates: PathType = 'c8080.json') -> None:
        super().__init__()
        self.state: CodeState = CodeState()
        path = Path(templates)
        scheme = path.read_text('utf8')
        self.scheme: Scheme = Scheme.from_json(scheme)
        self.matcher = CachedMatcher(self.scheme)

    def reset(self) -> None:
        self.state = CodeState()

    def getasm(self) -> str:
        out = ASM_HEADER
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

    def convert(self, node: BackNode | Node) -> Node:
        """Convert the backend nodes to new nodes."""
        if isinstance(node, Node):
            return node

        assert isinstance(node, BackNode)
        children = [self.convert(child) for child in node.children] + [None,
                                                                       None]
        label = node.label
        value = node.value
        match node.label:
            case 'register':
                label = 'extern'
                value = f'reg{node.value}'
            case 'call':
                children = children[:-2]  # Remove Nones
                func, args = children[-1], children[:-1]
                args = Node.join('comma', *args)
                children = [func, args, None, None]

        return Node(label, children[0], children[1], value)

    def eval(self, node: Node) -> None:
        """Evaluate the given node, assembling it."""
        self.evalnode(node, Reg.HL)

    def evalnode(self, node: Node | None, reg: Reg) -> None:
        """Recursively assemble the given node into the given register.

        If the node is SPECIAL, special case it. If it's BINARY (2 register),
        then either the right node can be computed in one chain of DE/HL
        operations (no SPECIAL or BINARY) or not. If it can compute it as such
        into DE, then compute the left node into HL, then the right into DE.
        If the right node can be computed into HL unarily, and the left node
        as well, then compute the right node first, xchg it into DE, then the
        left node. In the default case, do the right node, push it, then the
        left node.
        """
        if node is None:
            return
        match = self.match(node, reg)
        left, right = self.subreq(node, match)
        match match.regs:
            case TRegs.HL | TRegs.DE | TRegs.ANY:
                assert not (left and right)
                self.evalnode(left, reg)
                self.evalnode(right, reg)
            case TRegs.BINARY:
                assert reg == Reg.HL
                assert left and right
                uleft = self.unarily(node.left, Reg.HL)
                uright = self.unarily(node.right, Reg.DE)
                if uright == Reg.DE:
                    self.evalnode(node.left, Reg.HL)
                    self.evalnode(node.right, Reg.DE)
                elif match.commutative and self.unarily(node.left,
                                                        Reg.DE) == Reg.DE:
                    self.evalnode(node.right, Reg.HL)
                    self.evalnode(node.left, Reg.DE)
                elif uright == Reg.HL and uleft is not None:
                    self.evalnode(node.right, Reg.HL)
                    self.asm('xchg')
                    self.evalnode(node.left, Reg.HL)
                else:
                    self.evalnode(node.right, Reg.HL)
                    self.asm('push h')
                    self.evalnode(node.left, Reg.HL)
                    self.asm('pop d')
            case TRegs.SPECIAL:
                match node.label:
                    case 'call':
                        self.evalnode(right, Reg.HL)
                        self.evalnode(left, Reg.HL)
                    case 'comma' | 'brz':
                        if 'leftleft' in match.flags:
                            self.evalnode(node.left.left, Reg.HL)
                        self.evalnode(left, Reg.HL)
                        self.evalnode(right, Reg.HL)
                    case _:
                        raise ValueError(node.label)
            case _:
                raise ValueError(match.regs)
        self.expand(match, node, reg)

    def expand(self, match: Template, node: Node, reg: Reg) -> None:
        """Assemble the matched template."""
        self.asm(match.expand(self.state, node, reg))

    def match(self, node: Node, reg: Reg) -> Template:
        """Try to match the given node into the given register."""
        return self.matcher.match(node, reg)

    def unarily(self, node: Node | None, reg: Reg) -> Reg | None:
        """If we can match the node recursively such that it only computes
        into the given reg or HL, with no binary or special matches, return
        the register matched. Else, return None.
        """
        if node is None:
            return reg
        match = self.match(node, reg)
        match match.regs:
            case TRegs.DE:
                matchreg = Reg.DE
            case TRegs.HL:
                matchreg = Reg.HL
            case TRegs.ANY:
                matchreg = reg
            case _:
                return None
        if reg == Reg.DE and matchreg != reg:
            return self.unarily(node, Reg.HL)
        left, right = self.subreq(node, match)
        if right:
            assert left is None
            left = right
        if left:
            child = self.unarily(left, reg)
            if child == reg:
                return reg
            if child == Reg.HL:
                return self.unarily(node, Reg.HL)
            return None
        return reg

    def subreq(self, node: Node, match: Template) -> tuple[Node | None,
                                                           Node | None]:
        """Return a version of the node with its children removed if they were
        matched by the given template via their requirements.
        """
        left, right = node.children
        if match.leftreq.label:
            left = None
        if match.rightreq.label:
            right = None
        return left, right

    def command(self, command: Command, nodestk: list[BackNode]) -> None:
        match command.cmd:
            case '.text' | '.data' | '.string' | '.bss':
                self.state.curseg = command.cmd
            case '.export' | 'useregs':
                pass
            case 'eval':
                self.eval(self.convert(nodestk.pop()))
            case 'brz':
                self.eval(Node('brz', self.convert(nodestk.pop()),
                               value=command.args[0]))
            case '.dc':
                line = f".byte {','.join((str(arg) for arg in command.args))}"
                self.asmlines(line)
            case 'retnull':
                self.asmlines('jmp cret')
            case 'ret':
                self.eval(self.convert(nodestk.pop()))
                self.asmlines('jmp cret')
            case _:
                if command.cmd in self.scheme:
                    if command.args:
                        arg = command.args[0]
                    else:
                        arg = None
                    fakenode = Node(command.cmd, value=arg)
                    self.expand(self.scheme[command.cmd][0],
                                fakenode, Reg.HL)
                else:
                    raise ValueError(command)


def test(source: PathType):
    """Run a test program."""
    path = Path(source)
    irsrc = c6t.compile_c6t(path.read_text('utf8'))
    path.with_suffix('.ir').write_text(irsrc, 'utf8')
    codegen = Code80()
    try:
        dobackend(irsrc, codegen)
    finally:
        path.with_suffix('.s').write_text(codegen.getasm(), 'ascii')


if __name__ == "__main__":
    test('hello.c')

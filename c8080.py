"""C6T - C version 6 by Troy - Intel 8080 Backend"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, IntEnum, auto
from typing import Any, Iterator, Mapping
from pathlib import Path
import json
import re

from backend import CodeGen, Command, Node as BackNode, backend as dobackend
import c6t

ASM_HEADER = """
; C6T Standard Header for Intel 8080
    .text
start:
    .export start
    lxi sp,$FF00
    call _main
_exit:
    .export _exit
    hlt
    jmp _exit

csave:
    .export csave
    pop d
    push b
    lhld reg0
    push h
    lhld reg1
    push h
    lhld reg2
    push h
    lxi h,0
    dad sp
    mov c,l
    mov b,h
    xchg
    pchl

cret:
    .export cret
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

ccall:
    .export ccall
    pop d
    pchl

    .bss
reg0: .storage 2
reg1: .storage 2
reg2: .storage 2
    .export reg0,reg1,reg2

    .text
cextend:
    .export cextend
    mvi h,0
    mov a,l
    rlc
    jnc noextend
    dcr h
noextend:
    ret

_in80:
    .export _in80
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
    .export _out80
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
            append = Node(label, node)
            start = cls._joinrep(start, append)
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
    flags: tuple[str] = ()

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
        temp1, temp2 = None, None

        action = self.action
        if 'T1' in action or 'D1' in action:
            temp1 = state.temp()
        if 'T2' in action or 'D2' in action:
            temp2 = state.temp()

        out = ''
        matcher = re.compile(
            r'([_a-zA-Z][_a-zA-Z0-9]*)|([^_a-zA-Z]+)', re.DOTALL)
        for line in action.splitlines(keepends=False):
            outline = ''
            for match in matcher.finditer(line, 0):
                name, other = match.groups(default=None)
                if name is None:
                    assert other is not None
                    outline += other
                else:
                    match name:
                        case 'T1':
                            outline += str(temp1)
                        case 'T2':
                            outline += str(temp2)
                        case 'RLOW':
                            outline += Reg(reg).name[1].lower()
                        case 'LV':
                            assert node.left and node.left.value is not None
                            outline += str(node.left.value)
                        case 'RV':
                            assert node.right and node.right.value is not None
                            outline += str(node.right.value)
                        case 'V':
                            assert node.value is not None
                            outline += str(node.value)
                        case 'R':
                            outline += str(Reg(reg).name[0].lower())
                        case 'D1':
                            out += f'{temp1}:\n'
                            outline = ''
                            break
                        case 'D2':
                            out += f'{temp2}:\n'
                            outline = ''
                            break
                        case _:
                            outline += name
            out += f'\t{outline}\n'

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
            raise ValueError('template already in scheme', template)
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
        out = ''
        for seg in SEGMENTS:
            if seg != '.string':
                out += '\t' + seg + '\n'
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
        children: list[Node | None] = [
            self.convert(child) for child in node.children] + [None, None]
        label = node.label
        value = node.value
        match label:
            case 'cond':
                children[0] = Node.join('comma', *children[0:3])
                children[1] = None
            case 'asnadd' | 'asnsub' | 'asnmult' | 'asndiv' | 'asnmod' \
                    | 'asnrshift' | 'asnlshift' | 'asnand' | 'asneor' | 'asnor' \
                    | 'casnadd' | 'casnsub' | 'casnmult' | 'casndiv' | 'casnmod' \
                    | 'casnrshift' | 'casnlshift' | 'casnand' | 'casneor' | 'casnor':
                if label[0] == 'c':
                    prefix = 'c'
                    label = label[1:]
                else:
                    prefix = ''
                label = label.removeprefix('asn')
                return Node(f'{prefix}store',
                            children[0],
                            Node(label,
                                 Node(f'{prefix}load', children[0]),
                                 children[1]))
            case 'equ' | 'nequ':
                children[0] = Node('sub', children[0], children[1])
                children[1] = None
                label = 'log' if label == 'nequ' else 'lognot'
            case 'great' | 'less' | 'ugreat' | 'uless' \
                    | 'gequ' | 'lequ' | 'ugequ' | 'ulequ':
                children[0] = Node(
                    'cmp', children[0], children[1]
                )
                children[1] = None
            case 'postinc' | 'preinc' | 'predec' | 'postdec':
                assert isinstance(children[1], Node)
                value = children[1].value
                assert isinstance(value, int)
                assert value is not None
                children[1] = None
            case 'register':
                label = 'extern'
                value = f'reg{value}'
            case 'call':
                children = children[:-2]  # Remove Nones
                func, args = children[-1], children[:-1]
                args = Node.join('comma', *args)
                children = [func, args, None, None]
            case 'logand' | 'logor':
                if children[0].label == 'log':
                    children[0] = children[0].left
                if children[1].label == 'log':
                    children[1] = children[1].left
                children[0] = Node(label, children[0], children[1], value)
                children[1] = None
                label = 'log'
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
                    self.asmlines('xchg')
                    self.evalnode(node.left, Reg.HL)
                else:
                    self.evalnode(node.right, Reg.HL)
                    self.asmlines('push h')
                    self.evalnode(node.left, Reg.HL)
                    self.asmlines('pop d')
            case TRegs.SPECIAL:
                match node.label:
                    case 'cond':
                        expr, left, right = node.left.left, \
                            node.left.right.left, node.left.right.right.left
                        assert None not in (expr, left, right)
                        self.evalnode(expr, Reg.HL)
                        lab1, lab2 = self.state.temp(), self.state.temp()
                        self.asmlines('mov a,l', 'ora h', f'jnz {lab1}')
                        self.evalnode(left, Reg.HL)
                        self.asmlines(f'jmp {lab2}')
                        self.deflabel(lab1)
                        self.evalnode(right, Reg.HL)
                        self.deflabel(lab2)
                    case 'logor':
                        lab = self.state.temp()
                        self.evalnode(left, Reg.HL)
                        self.asmlines('mov a,l', 'ora h', f'jnz {lab}')
                        self.evalnode(right, Reg.HL)
                        self.deflabel(lab)
                    case 'logand':
                        lab = self.state.temp()
                        self.evalnode(left, Reg.HL)
                        self.asmlines('mov a,l', 'ora h', f'jz {lab}')
                        self.evalnode(right, Reg.HL)
                        self.deflabel(lab)
                    case 'call':
                        self.evalnode(right, Reg.HL)
                        self.evalnode(left, Reg.HL)
                    case _:
                        if 'leftleft' in match.flags:
                            self.evalnode(node.left.left, Reg.HL)
                        self.evalnode(left, Reg.HL)
                        self.evalnode(right, Reg.HL)
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
                out = reg
            elif child == Reg.HL:
                assert reg != Reg.HL
                out = self.unarily(node, Reg.HL)
            else:
                out = None
            return out
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

    def doswitch(self, expr: BackNode, brklab: BackNode,
                 cases: BackNode, tablab: BackNode) -> None:
        """Assemble a switch statement."""
        node = Node(
            'call',
            Node(
                'extern', value='doswitch'
            ),
            Node(
                'comma',
                Node(
                    'extern', value=brklab.value
                ),
                Node(
                    'comma',
                    Node(
                        'con', value=cases.value
                    ),
                    Node(
                        'comma',
                        Node(
                            'extern', value=tablab.value
                        ),
                        Node(
                            'comma',
                            self.convert(expr)
                        )
                    )
                )
            ),
            value=4
        )
        self.eval(node)

    def command(self, command: Command, nodestk: list[BackNode]) -> None:
        match command.cmd:
            case 'ijmp':
                self.eval(Node('ijmp', self.convert(nodestk.pop())))
            case 'doswitch':
                tablab = nodestk.pop()
                cases = nodestk.pop()
                brklab = nodestk.pop()
                expr = nodestk.pop()
                self.doswitch(expr, brklab, cases, tablab)
            case '.text' | '.data' | '.string' | '.bss':
                self.state.curseg = command.cmd
            case '.export':
                for arg in command.args:
                    self.asmlines(f'.export {arg}')
            case 'useregs':
                pass
            case 'eval':
                self.eval(self.convert(nodestk.pop()))
            case 'brz':
                self.eval(Node('brz', self.convert(nodestk.pop()),
                               value=command.args[0]))
            case '.dc' | '.dw':
                cmd = '.byte' if command.cmd == '.dc' else '.word'
                line = f"{cmd} {','.join((str(arg) for arg in command.args))}"
                self.asmlines(line)
            case 'retnull':
                self.asmlines('jmp cret')
            case 'ret':
                self.eval(self.convert(nodestk.pop()))
                self.asmlines('jmp cret')
            case '.common':
                oldseg = self.state.curseg
                self.state.curseg = '.bss'
                self.deflabel(command.args[0])
                self.asmlines(f'.storage {command.args[1]},0')
                self.state.curseg = oldseg
            case _:
                if command.cmd in self.scheme:
                    if command.args:
                        arg = command.args[0]
                    else:
                        arg = None
                    fakenode = Node(command.cmd, value=arg)
                    match = self.scheme[command.cmd][0]
                    assert match.regs == TRegs.SPECIAL
                    self.expand(self.scheme[command.cmd][0],
                                fakenode, Reg.HL)
                else:
                    raise ValueError(command)


def test(source: PathType):
    """Run a test program."""
    path = Path(source)
    irsrc, _ = c6t.compile_c6t(path.read_text('utf8'))
    path.with_suffix('.ir').write_text(irsrc, 'utf8')
    codegen = Code80()
    try:
        dobackend(irsrc, codegen)
    finally:
        path.with_suffix('.s').write_text(codegen.getasm(), 'ascii')


if __name__ == "__main__":
    test('ed.c')

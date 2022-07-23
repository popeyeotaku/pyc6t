"""C6T - C version 6 by Troy - Intel 8080 codegen
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from functools import cached_property
from pathlib import Path
from typing import Any, Sequence
from backend import CodeGen, Command, Node as BackNode, backend
from c6t import compile_c6t



class Reg(IntEnum):
    """An Intel 8080 register.
    """
    HL = 1
    DE = 2
    BC = 3


MAXREGS = 2

SEGMENTS = ('.text', '.data', '.string', '.bss')

USER_REGS = 3

START_BASE = Reg.HL


@dataclass(frozen=True)
class Node:
    """Represents a converted, code generation expression node."""
    label: str
    left: Node | None = None
    right: Node | None = None
    value: Any = field(default=None, hash=False, compare=False)

    def __post_init__(self):
        assert self.right is None if self.left is None else True

    @cached_property
    def regs_used(self) -> int:
        """The number of registers used recursively by this node."""
        if self.left and self.right:
            if self.left.regs_used == self.right.regs_used:
                return self.left.regs_used + 1
            return max(self.left.regs_used, self.right.regs_used)
        elif self.left:
            return self.left.regs_used
        else:
            return 1

    @property
    def children(self) -> tuple[Node | None, Node | None]:
        """Return a tuple of this node's children."""
        return self.left, self.right

    @cached_property
    def biggest(self) -> Sequence[Node | None, Node | None]:
        """Return this node's children ordered by most registers used
        first.
        """
        return sorted(filter(None, self.children), key=lambda n: n.regs_used,
                      reverse=True)


class Code80(CodeGen):
    """Code generation for C6T on the Intel 8080 CPU."""

    def __init__(self) -> None:
        super().__init__()
        self.segs: dict[str, str] = {seg: '' for seg in SEGMENTS}
        self.curseg = '.text'

    def reset(self) -> None:
        self.segs: dict[str, str] = {seg: '' for seg in SEGMENTS}
        self.curseg = '.text'

    def getasm(self) -> str:
        out = ''
        for seg in SEGMENTS:
            out += f"{self.segs[seg]}\n"
        return out

    def reserve(self, size):
        """Assemble to reserve size bytes."""
        self.asm(f'.ds {size}')

    def loadext(self, reg: Reg, extern: str) -> None:
        """Assemble to load the given extern into the given register."""
        match reg:
            case reg.HL:
                self.asm(f'lhld {extern}')
            case reg.DE:
                self.asm(f'lda {extern}', 'mov e,a')
                self.asm(f'lda {extern}+1', 'mov d,a')
            case _:
                raise ValueError(reg)

    def immed(self, reg: Reg, value) -> None:
        """Load the value immediate into the register."""
        self.asm(f'lxi {Reg(reg).name[0]}, {value}')

    def move(self, src: Reg, dest: Reg) -> None:
        """Assemble to move the given register."""
        src = Reg(src)
        dest = Reg(dest)
        if src == dest:
            return
        if (src, dest) in ((Reg.HL, Reg.DE), (Reg.DE, Reg.HL)):
            self.asm('xchg')
        self.asm(f'mov {dest.name[0]}, {src.name[0]}')
        self.asm(f'mov {dest.name[1]}, {src.name[1]}')

    def funchead(self):
        """Output assembly for a new function header."""
        self.push(Reg.BC)
        for i in range(USER_REGS):
            self.loadext(Reg.HL, f"reg{i}")
            self.push(Reg.HL)
        self.immed(Reg.HL, 0)
        self.asm('dad sp')
        self.move(Reg.HL, Reg.BC)

    def join(self, label: str, *nodes: Node) -> Node | None:
        """Join the nodes by the given label into a list."""
        if len(nodes) < 1:
            return None
        nodestk = deque(nodes)
        first = Node(label, nodestk.popleft(), None)
        last = first
        while nodestk:
            last.right = Node(label, nodestk.popleft(), None)
            last = last.right
        return first

    def convert(self, node: BackNode | Node | None) -> Node:
        """Perform necessary conversions on the backend nodes."""
        if node is None or isinstance(node, Node):
            return Node  # Already converted
        assert isinstance(node, BackNode)
        children: list[Node | None] = [self.convert(child)
                                       for child in node.children]
        while len(children) < 2:
            children.append(None)
        match node.label:
            case 'register':
                return Node('extern', value=f"reg{node.value}")
            case 'load' | 'cload':
                if children[0].label == 'extern':
                    return Node(f'ext{node.label}',
                                value=children[0].value)
            case 'store' | 'cstore':
                if children[0].label == 'extern':
                    return Node(f'ext{node.label}', left=children[1],
                                value=children[0].value)
            case 'call':
                filtered = list(filter(None, children))
                func, args = filtered[-1], filtered[:-1]
                args = [arg.left for arg in args]
                left = func
                right = self.join('arg', *args)
                return Node('call', left, right, value=node.value)
            case 'great' | 'less' | 'uless' | 'ugreat':
                return Node(node.label, Node('sub', children[0], children[1]))
        if len(children) > 2:
            raise ValueError('too many kids')
        return Node(node.label, *children, value=node.value)

    def eval(self, node: BackNode) -> None:
        """Evaluate the given backend node."""
        tree = self.convert(node)
        self.evalnode(tree)

    def command(self, command: Command, nodestk: list[BackNode]) -> None:
        match command.cmd:
            case '.text' | '.data' | '.bss' | '.string':
                self.curseg = command.cmd
            case '.common':
                oldseg = self.curseg
                self.curseg = '.bss'
                lab, size = command.args
                self.deflabel(lab)
                self.reserve(size)
                self.curseg = oldseg
            case '.export' | 'useregs':
                pass
            case '.func':
                self.funchead()
            case 'eval':
                self.eval(nodestk.pop())
            case 'brz':
                self.eval(nodestk.pop())
                self.test(Reg.HL)
                self.asm(f'je {command.args[0]}')
            case 'jmp':
                self.asm(f'jmp {command.args[0]}')
            case _:
                raise NotImplementedError

    def test(self, reg: Reg) -> None:
        """Assemble to test if the register is 0."""
        reg = Reg(reg)
        self.asm(f'mov a,{reg.name[0]}')
        self.asm(f'ora {reg.name[1]}')

    def deflabel(self, lab: str) -> None:
        assert ':' not in lab
        self.segs[self.curseg] += f"{lab}:\n"

    def asm(self, *lines: str) -> None:
        """Assemble the given lines of code."""
        for line in lines:
            self.segs[self.curseg] += f'\t{line}\n'

    def add(self, dest: Reg, left: Reg, right: Reg) -> None:
        """Assemble to add two registers, storing the result in a third."""
        dest, left, right = Reg(dest), Reg(left), Reg(right)
        if Reg.HL in (left, right) and Reg.HL == dest:
            reg = left if left != Reg.HL else right
            self.asm(f'dad {reg.name[0]}')
        else:
            self.asm(f'mov a,{left.name[1]}')
            self.asm(f'add {right.name[1]}')
            self.asm(f'mov {dest.name[1]},a')

            self.asm(f'mov a,{left.name[0]}')
            self.asm(f'adc {right.name[0]}')
            self.asm(f'mov {dest.name[0]},a')

    def loadhl(self):
        """Load HL indirectly from itself."""
        self.asm('mov a,m', 'inx h', 'mov l,m', 'mov h,a')

    def asmnode(self, node: Node, dest: Reg = Reg.HL, left: Reg = Reg.HL,
                right: Reg = Reg.HL) -> None:
        """Output assembly code for the given node."""
        dest, left, right = Reg(dest), Reg(left), Reg(right)
        match node.label:
            case 'sub':
                self.asm(f'mov a,{left.name[1]}', f'sub {right.name[1]}')
                self.asm(f'mov {dest.name[1]},a')

                self.asm(f'mov a,{left.name[0]}', f'sbb {right.name[0]}')
                self.asm(f'mov {dest.name[0]},a')
            case 'auto':
                self.immed(dest, node.value)
                self.add(dest, Reg.BC, dest)
            case 'con' | 'extern':
                self.immed(dest, node.value)
            case 'add':
                self.add(dest, left, right)
            case 'register':
                self.move(node.value, dest)
            case 'extstore':
                if left == Reg.HL:
                    self.asm(f'shld {node.value}')
                else:
                    self.asm(f'mov a,{left.name[1]}')
                    self.asm(f'sta {node.value}')
                    self.asm(f'mov a,{left.name[0]}')
                    self.asm(f'sta {node.value}+1')
            case 'arg':
                self.push(left)
            case 'load':
                if left == dest == Reg.HL:
                    self.loadhl()
                elif left == Reg.HL:
                    self.asm(f'mov {dest.name[1]},m', 'inx h',
                             f'mov {dest.name[0]},m')
                elif left == Reg.DE:
                    self.asm('xchg')
                    self.loadhl()
                    self.move(Reg.HL, dest)
                else:
                    assert left in (Reg.DE, Reg.BC)
                    stored = dest == left
                    self.asm(f'ldax {left.name[0]}')
                    if stored:
                        self.asm('push psw')
                    else:
                        self.asm(f'mov {dest.name[1]},a')
                    self.asm(f'inx {left.name[0]}')
                    self.asm(f'ldax {left.name[0]}')
                    self.asm(f'mov {dest.name[0]},a')
                    if stored:
                        self.asm('pop psw',
                                 f'mov {dest.name[1]},a')
            case 'extload':
                if dest == Reg.HL:
                    self.asm(f'lhld {node.value}')
                else:
                    self.asm(f'lda {node.value}', f'mov {dest.name[1]},a')
                    self.asm(f'lda {node.value}+1', f'mov {dest.name[0]},a')
            case _:
                raise NotImplementedError(node)

    def evalnode(self, node: Node | None, base: int = START_BASE) -> None:
        """Recursively output assembly for the given node."""
        if node is None:
            return
        match node.label:
            # Special cases
            case 'arg':
                self.evalnode(node.left, base)
                self.push(base)
                self.evalnode(node.right, base)
            case 'call':
                if base != Reg.HL:
                    self.push(Reg.HL)
                    saved = True
                else:
                    saved = False
                self.evalnode(node.right, base)
                if node.left.label == 'extern':
                    self.asm(f'call {node.left.value}')
                else:
                    self.evalnode(node.left, base)
                    self.move(base, Reg.HL)
                    self.asm('call ccall')
                if saved:
                    self.move(Reg.HL, base)
                    self.pop(Reg.HL)
            case _:
                if node.left and node.right:
                    if node.regs_used <= MAXREGS:
                        self.eval_fit(node, base)
                    else:
                        self.eval_nofit(node)
                elif node.left:
                    self.evalnode(node.left, base)
                    self.asmnode(node, base, base)
                else:
                    self.asmnode(node, base)

    def eval_fit(self, node: Node, base: int) -> None:
        """Recursively assemble a node if it will fit in the number of
        registers we have.
        """
        if node.left.regs_used == node.right.regs_used:
            assert node.left.regs_used == node.right.regs_used\
                == node.regs_used-1
            self.evalnode(node.right, base+1)
            rightreg = Reg(base+node.regs_used-1)
            self.evalnode(node.left, base)
            leftreg = Reg(base+node.regs_used-2)
            self.asmnode(node, rightreg, leftreg, rightreg)
        else:
            big, little = node.biggest
            self.evalnode(big, base)
            bigreg = Reg(base+node.regs_used-1)
            self.evalnode(little, base)
            littlereg = Reg(base+little.regs_used-1)
            if bigreg is node.right:
                self.asmnode(node, bigreg, littlereg, bigreg)
            else:
                self.asmnode(node, bigreg, bigreg, littlereg)

    def eval_nofit(self, node: Node) -> None:
        """Recursively evaluate a node that will not fit in our number of
        registers.
        """
        big, little = node.biggest
        assert big.regs_used >= MAXREGS
        self.evalnode(node, 1)
        self.push(MAXREGS-1)
        if little.regs_used >= MAXREGS:
            lbase = START_BASE
        else:
            lbase = MAXREGS-1 - little.regs_used
        self.evalnode(little, lbase)
        littlereg = Reg(MAXREGS-1)
        self.pop(bigreg := Reg(MAXREGS-2))
        if big is node.right:
            self.asmnode(node, littlereg, littlereg, bigreg)
        else:
            self.asmnode(node, littlereg, bigreg, littlereg)

    def pop(self, reg: Reg) -> None:
        """Assemble to pop a value into the given register."""
        self.asm(f'pop {Reg(reg).name[0]}')

    def push(self, reg: Reg) -> None:
        """Assemble to push the register to the stack."""
        self.asm(f'push {Reg(reg).name[0]}')


def test(name: str | Path):
    """Test the code generation."""
    path = Path(name)
    ir_rep = compile_c6t(path.read_text('utf8'))
    ir_path = path.with_suffix('.ir')
    ir_path.write_text(ir_rep, 'utf8')
    codegen = Code80()
    try:
        backend(ir_rep, codegen)
    finally:
        asm = codegen.getasm()
        print(asm)
        out = path.with_suffix('.s')
        out.write_text(asm, 'utf8')


if __name__ == "__main__":
    test('wrap.c')

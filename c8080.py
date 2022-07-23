"""C6T - C version 6 by Troy - Intel 8080 codegen
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from functools import cached_property
from typing import Any, Sequence
from backend import CodeGen, Command, Node as BackNode


MAXREGS = 2


class Reg(IntEnum):
    """An Intel 8080 register.
    """
    HL = 0
    DE = 1
    BC = 2


@dataclass(frozen=True)
class Node(BackNode):
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
        count = 1
        if self.left:
            count += self.left.regs_used
        if self.right:
            count += self.right.regs_used

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
    
    def reset(self) -> None:
        raise NotImplementedError
    
    def getasm(self) -> str:
        raise NotImplementedError
    
    def command(self, command: Command, nodestk: list[BackNode]) -> None:
        raise NotImplementedError
    
    def deflabel(self, lab: str) -> None:
        raise NotImplementedError
    
    def asm(self, *lines:str) -> None:
        """Assemble the given lines of code."""
        raise NotImplementedError

    def asmnode(self, node: Node, dest: Reg = Reg.HL, left: Reg = Reg.HL,
                right: Reg = Reg.HL) -> None:
        """Output assembly code for the given node."""
        raise NotImplementedError

    def evalnode(self, node: Node, base: int = 1) -> None:
        """Recursively output assembly for the given node."""
        if node.left and node.right:
            if node.regs_used <= MAXREGS:
                if node.left.regs_used == node.right.regs_used:
                    self.evalnode(node.right, base+1)
                    rightreg = base+node.regs_used-1
                    self.evalnode(node.left, base)
                    leftreg = base+node.regs_used-2
                    self.asmnode(node, rightreg, leftreg, rightreg)
                else:
                    big, little = node.biggest
                    self.evalnode(big, base)
                    bigreg = base+node.regs_used-1
                    self.evalnode(little, base)
                    littlereg = base+little.regs_used-1
                    if bigreg is node.right:
                        self.asmnode(node, bigreg, littlereg, bigreg)
                    else:
                        self.asmnode(node, bigreg, bigreg, littlereg)
            else:
                big, little = node.biggest
                assert big.regs_used >= MAXREGS
                self.evalnode(node, 1)
                self.push(MAXREGS-1)
                if little.regs_used >= MAXREGS:
                    lbase = 1
                else:
                    lbase = MAXREGS-1 - little.regs_used
                self.evalnode(little, lbase)
                littlereg = MAXREGS-1
                self.pop(bigreg := MAXREGS-2)
                if big is node.right:
                    self.asmnode(node, littlereg, littlereg, bigreg)
                else:
                    self.asmnode(node, littlereg, bigreg, littlereg)
        elif node.left:
            self.asmnode(node, base-1, base-1)
        else:
            self.asmnode(node, base-1)

    def pop(self, reg: Reg) -> None:
        """Assemble to pop a value into the given register."""
        self.asm(f'pop {Reg(reg).name}')

    def push(self, reg: Reg) -> None:
        """Assemble to push the register to the stack."""
        self.asm(f'push {Reg(reg).name}')

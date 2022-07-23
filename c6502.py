"""C6T - C version 6 by Troy - Code Generation for 6502"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from functools import cached_property
from typing import Any, Type
from backend import CodeGen, Command, Node

SEGMENTS = ('.text', '.data', '.string', '.bss')


@dataclass(frozen=True)
class Node65:
    """An internal format Node, as opposed to backend's. Is immutable and
    hashable.
    """
    label: str
    left: Node65 | None = None
    right: Node65 | None = None
    value: Any = field(default=None, hash=False, compare=False)

    def __len__(self) -> int:
        count = 1
        if self.left:
            count += len(self.left)
        if self.right:
            count += len(self.right)
        return count


@dataclass(frozen=True)
class Template:
    """A potential code generation template. Connects a given tree to a given
    replacement node, and action assembly string.
    """
    tree: Node65
    replacement: Node65
    action: str


@dataclass(frozen=True)
class MatchedNode:
    """Represents a node which has been matched to a template."""
    node: Node65
    template: Template
    left: MatchedNode | None = None
    right: MatchedNode | None = None

    @cached_property
    def regs_used(self) -> int:
        """The number of registers used recursively by this match and its
        children matches.
        """
        if self.left and self.right:
            left = self.left.regs_used
            right = self.right.regs_used
            if left == right:
                return left + 1
            return max(left, right)
        if self.left:
            return self.left.regs_used
        if self.right:
            return self.right.regs_used
        return 1

    def __len__(self):
        return len(self.node)


Scheme = dict[Node, Template]


ZP_REGS = ('rsp', 'rfp', 'rv0', 'rv1', 'rv2')

RegType = Type[IntEnum]


class Code6502(CodeGen):
    """Code generation for 6502."""

    def __init__(self, zp_regs: int, scheme: Scheme) -> None:
        self.segs: dict[str, str] = {seg: '' for seg in SEGMENTS}
        self.curseg = '.text'
        self.scheme = scheme
        self.regtype: RegType = IntEnum('RegType', list(
            ZP_REGS) + [f'r{i}' for i in range(zp_regs)])
        self.user_vars = 0

    def reset(self) -> None:
        for seg in self.segs:
            self.segs[seg] = ''
        self.curseg = '.text'
        self.user_vars = 0

    @property
    def startreg(self) -> RegType:
        """The first register available for expressions.
        """
        return self.regtype(self.regtype.rv0 + self.user_vars)

    @property
    def freeregs(self) -> int:
        """Return the number of registers available to expressions.
        """
        return len(self.regtype) - self.startreg

    def getasm(self) -> str:
        out = f"\t.text\n{self.segs['.text']}\n"
        out += f"\t.data\n{self.segs['.data']}\n"
        out += f"{self.segs['.string']}\n"
        out += f"\t.bss\n{self.segs['.bss']}\n"
        return out

    def command(self, command: Command, nodestk: list[Node]) -> None:
        match command.cmd:
            case 'eval':
                self.eval(nodestk.pop())
            case 'brz':
                node = Node('brz', [nodestk.pop()], command.args[1])
                self.eval(node)
            case _:
                raise NotImplementedError(command)

    def asm(self, *lines: str) -> None:
        """Assemble the given lines of code."""
        assert self.curseg in self.segs
        for line in lines:
            if '\n' in line or line[0] == '\t':
                raise ValueError('bad line', line)
            self.segs[self.curseg] += f"\t{line}\n"

    def deflabel(self, lab: str) -> None:
        assert self.curseg in self.segs
        self.segs[self.curseg] += f"\n{lab}:\n"

    def convert(self, node: Node | Node65) -> Node65:
        """Convert a backend node to one of ours, with additional conversions
        for evaluation.
        """
        if isinstance(node, Node65):
            return node  # Already converted
        raise NotImplementedError

    def eval(self, node: Node) -> None:
        """Output assembly for the given node."""
        tree = self.convert(node)
        match = self.match(tree)
        self.asm_match(match, self.startreg)

    def asm_match(self, match: MatchedNode, base: RegType):
        """Assemble the matched node setup. Returns a new node."""
        if match.left and match.right:
                        

    def match(self, node: Node65) -> MatchedNode:
        """Try to match the given node, returning the matched template and
        associated cost.

        Raises ValueError if can't find.
        """
        if node is None:
            raise ValueError(node)
        if node in self.scheme:
            return MatchedNode(node, self.scheme[node])

        try:
            left = self.match(node.left)
        except ValueError:
            left = None
        try:
            right = self.match(node.right)
        except ValueError:
            right = None

        matches: list[MatchedNode] = []
        if left:
            matches.append(self.childmatch(node, left=left))
        if right:
            matches.append(self.childmatch(node, right=right))
        if left and right:
            matches.append(self.childmatch(node, left, right))
        matches.sort(key=len, reverse=True)  # Most nodes replaced first
        if matches:
            return matches[0]
        raise ValueError

    def childmatch(self, node: Node65, left: MatchedNode | None = None,
                   right: MatchedNode | None = None) -> MatchedNode:
        """Try to match the node, replacing the left or right child.

        Raises ValueError if no match.
        """
        if left:
            nleft = left.template.replacement
        else:
            nleft = node.left
        if right:
            nright = right.template.replacement
        else:
            nright = node.right

        match = self.match(Node65(node.label, nleft, nright, node.value))

        match.node = node
        if left:
            match.left = left
        if right:
            match.right = right
        return match


if __name__ == "__main__":
    import doctest
    doctest.testmod()

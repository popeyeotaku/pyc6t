"""C6T - C version 6 by Troy - Intel 8080 codegen
"""

from __future__ import annotations
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any


REGS = ('hl', 'de')


@dataclass(frozen=True)
class Node:
    """A node for an expression tree."""
    label: str
    children: tuple[Node] = field(default_factory=tuple)
    value: Any = None

    def __post_init__(self):
        if not isinstance(self.children, tuple):
            object.__setattr__(self, 'children', tuple(self.children))

    @cached_property
    def regs(self) -> int:
        """Return the number of registers required to evaluate this node."""
        if len(self.children) < 1:
            return 1
        if len(self.children) == 1:
            return self.children[0].regs
        regs = [child.regs for child in self.children]
        if len(set(regs)) == 1:
            return regs[0] + 1
        return max(*regs)


@dataclass
class CodeGen80:
    """Code generator for Intel 8080 assembly."""
    asm_text: str = ''

    def clear(self):
        """Reset state."""
        self.asm_text = ''

    def asm(self, opcode: str, *operands: str) -> None:
        """Assemble the given instruction."""
        self.asm_text += f"\t{opcode} {','.join(operands)}\n"

    def outnode(self, node: Node, destreg: int) -> None:
        """Assemble a single node on its own."""
        args = [REGS[destreg]]
        if node.value is not None:
            args.append(str(node.value))
        self.asm(node.label, *args)

    def tree(self, node: Node, base: int = 0) -> None:
        """Recursively assemble an expression node tree."""
        if len(node.children) > len(REGS):
            raise ValueError("too many children")
        if base >= len(REGS):
            raise ValueError('too high of base reg')
        inorder = sorted(node.children, key=lambda n: n.regs, reverse=True)
        if node.regs > len(REGS):
            stacked = []
            for child in inorder:
                self.tree(child, 0)
                self.asm('push', REGS[0])
                stacked.append(child)
            for child in reversed(stacked):
                self.asm('pop', REGS[node.children.index(child)])
            self.outnode(node, 0)
        else:
            for i, child in enumerate(inorder):
                self.tree(child, i+base)
            # This is 8080 dependant! not on other CPUs
            if len(node.children) > 0 and inorder[0] != node.children[0]:
                self.asm('xchg')
            self.outnode(node, base)


def test():
    """A simple test.

    t = ((t>>2)&16376)|(t&7);
    t
    t
    load
    2
    rshift
    16376
    and
    t
    load
    7
    and
    or
    store
    """
    tree = Node('store', [
        Node('extern', value='t'),
        Node('or', [
            Node('and', [
                Node('rshift', [
                    Node('load', [
                        Node('extern', value='t')
                    ]),
                    Node('con', value=2)
                ]),
                Node('con', value=16376)
            ]),
            Node('and', [
                Node('load', [
                    Node('extern', value='t')
                ]),
                Node('con', value=7)
            ])
        ])
    ])
    codegen = CodeGen80()
    codegen.tree(tree)
    print(codegen.asm_text)

    # (*foo[bar/2])[4]
    # load
    # add
    # load
    # add
    # extern foo
    # div
    # extern bar
    # con 2
    # con 4
    tree = Node('load', [
        Node('add', [
            Node('load', [
                Node('add', [
                    Node('extern', value='foo'),
                    Node('div', [
                        Node('extern', value='bar'),
                        Node('con', value=2)
                    ])
                ]),
            ]),
            Node('con', value=4)
        ])
    ])
    codegen.clear()
    codegen.tree(tree)
    print(codegen.asm_text)


if __name__ == "__main__":
    test()

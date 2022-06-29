"""C6T - C version 6 by Troy - Expression Parsing"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
from parse_state import Parser


@dataclass
class Node:
    """An expression node."""
    label: str
    linenum: int
    children: list[Node]


@dataclass
class Leaf(Node):
    """A leaf expression node."""
    value: Any
    linenum: int


def build(label: str, children: list[Node]) -> Node:
    """Construct a new non-leaf node."""
    # TODO: build


def binary(parser: Parser, lesser: Callable[[Parser], Node],
           labels: dict[str, str]):
    """Handle a normal binary parse."""
    node = lesser(parser)
    while True:
        token = parser.match(*labels.keys())
        if not token:
            return node
        node = build(labels[token.label], [node, lesser(parser)])

def exp15(parser:Parser):
    """Parse ',' operator"""
    return binary(parser, exp14, {',': 'comma'})

def exp14(parser:Parser):
    """Parse assignment operators"""
    


def expression(parser: Parser, seecommas: bool = True) -> Node:
    """Parse an expression."""
    # TODO: parse the expression


def conexpr(parser: Parser, seecommas: bool = True, default: int = 1) -> int:
    """Parse an expression. If the end result is not an integer constant,
    return the defalut number and report an error. Else, return the constant
    value.
    """
    node = expression(parser, seecommas)
    if node.label != 'con':
        parser.error('bad constant expression', node.linenum)
        return default
    assert isinstance(node, Leaf) and isinstance(node.value, int)
    return node.value

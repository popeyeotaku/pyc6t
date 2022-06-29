"""C6T - C version 6 by Troy - Expression Parsing"""

from __future__ import annotations
import collections.abc
from dataclasses import dataclass, field
from typing import Any, Callable
from parse_state import Parser
from symtab import Symbol
from type6 import Char6, Double6, Func6, Int6, TypeElem, TypeString
from util import word
from lexer import Token


@dataclass
class Node(collections.abc.MutableSequence):
    """An expression node."""
    label: str
    linenum: int = field(compare=False)
    typestr: TypeString
    children: list[Node]

    def insert(self, index: int, value: Node) -> None:
        self.children.insert(index, value)

    def __len__(self):
        return len(self.children)

    def __getitem__(self, key: int) -> Node:
        return self.children[key]

    def __setitem__(self, key: int, value: Node) -> None:
        self.children[key] = value

    def __delitem__(self, key: int) -> None:
        del self.children[key]

    @property
    def islval(self) -> bool:
        """Return flag for if this node is an lval."""
        return self.label in ('deref', 'name', 'dot', 'arrow')


@dataclass
class Leaf(Node):
    """A leaf expression node."""
    value: Any
    linenum: int


def build(parser: Parser, linenum: int, label: str | None,
          children: list[Node]) -> Node:
    """Construct a new non-leaf node."""
    # TODO: build
    if label is None:
        return children[0]
    return Node(label, linenum, [Int6], children)


def binary(parser: Parser, lesser: Callable[[Parser], Node],
           labels: dict[str, str]):
    """Handle a normal binary parse."""
    node = lesser(parser)
    while True:
        token = parser.match(*labels.keys())
        if not token:
            return node
        node = build(parser, token.linenum,
                     labels[token.label], [node, lesser(parser)])


def exp15(parser: Parser) -> Node:
    """Parse ',' operator"""
    return binary(parser, exp14, {',': 'comma'})


def exp14(parser: Parser) -> Node:
    """Parse assignment operators"""
    node = exp13(parser)
    labels = {
        '=': 'assign',
        '=+': 'asnadd',
        '=-': 'asnsub',
        '=*': 'asnmult',
        '=/': 'asndiv',
        '=%': 'asnmod',
        '=>>': 'asnrshift',
        '=<<': 'asnlshift',
        '=&': 'asnand',
        '=^': 'asneor',
        '=|': 'asnor'
    }
    token = parser.match(*labels.keys())
    if token:
        node = build(parser, token.linenum, labels[token.label],
                     [node, exp14(parser)])
    return node


def exp13(parser: Parser) -> Node:
    """Parse conditional (? ... : ...) operator.
    """
    node = exp12(parser)
    while parser.match('?'):
        linenum = parser.curline
        left = exp12(parser)
        parser.need(':')
        right = exp12(parser)
        node = build(parser, linenum, 'cond', [node, left, right])
    return node


def exp12(parser: Parser) -> Node:
    """Parse || operator."""
    return binary(parser, exp11, {'||': 'logor'})


def exp11(parser: Parser) -> Node:
    """Parse && operator"""
    return binary(parser, exp10, {'&&': 'logand'})


def exp10(parser: Parser) -> Node:
    """Parse | operator"""
    return binary(parser, exp9, {'|': 'or'})


def exp9(parser: Parser) -> Node:
    """Parse ^ operator."""
    return binary(parser, exp8, {'^': 'eor'})


def exp8(parser: Parser) -> Node:
    """Parse & operator"""
    return binary(parser, exp7, {'&': 'and'})


def exp7(parser: Parser) -> Node:
    """Parse equality (==, !=) operators"""
    return binary(parser, exp6, {'==': 'equ', '!=': 'nequ'})


def exp6(parser: Parser) -> Node:
    """Parse relational (< > <= >=) operators"""
    return binary(parser, exp5, {
        '<': 'less',
        '>': 'great',
        '<=': 'lequ',
        '>=': 'gequ'
    })


def exp5(parser: Parser) -> Node:
    """Parse shift (<< >>) operators"""
    return binary(parser, exp4, {
        '>>': 'rshift',
        '<<': 'lshift'
    })


def exp4(parser: Parser) -> Node:
    """Parse additive (+ -) operators"""
    return binary(parser, exp3, {'+': 'add', '-': 'sub'})


def exp3(parser: Parser) -> Node:
    """Parse multiplicative (* / %) operators"""
    return binary(parser, exp2, {'*': 'mult', '/': 'div', '%': 'mod'})


def exp2(parser: Parser) -> Node:
    """Parse unary operators.
    """
    labels = {
        '&': 'addr',
        '-': 'neg',
        '!': 'lognot',
        '~': 'compl',
        '++': 'preinc',
        '--': 'predec',
        'sizeof': 'sizeof'
    }
    token = parser.match(*labels.keys())
    if token:
        return build(parser, token.linenum, labels[token.label], [exp2(parser)])
    node = exp1(parser)
    while True:
        token = parser.match('++', '--')
        if not token:
            return node
        if token.label == '++':
            label = 'postinc'
        else:
            label = 'postdec'
        node = build(parser, token.linenum, label, [node])


def domember(parser: Parser, linenum: int, node: Node, label: str,
             member: str) -> Node:
    """Perform a '.' or '->' operation."""
    # TODO: domember


def exp1(parser: Parser) -> Node:
    """Parse a primary expression."""
    token = parser.match('name', 'con', 'fcon', 'string', '(')
    if not token:
        parser.errskip('missing primary expression')
        token = Token('con', parser.curline, 1)
    match token.label:
        case 'name':
            assert isinstance(token.value, str)
            try:
                symbol = parser.symtab[token.value]
            except KeyError:
                if parser.peek().label == '(':
                    symbol = Symbol(token.value,
                                    'extern',
                                    [Func6, Int6],
                                    local=True)
                else:
                    symbol = Symbol(token.value,
                                    'static',
                                    [TypeElem('array', 1),
                                     Int6],
                                    offset=parser.nextstatic(),
                                    local=True,
                                    undefined=True)
                parser.symtab[token.value] = symbol
            node = Leaf('name', token.linenum, symbol.typestr.copy(),
                        [], symbol)
        case 'con':
            assert isinstance(token.value, int)
            node = Leaf('con', token.linenum, [Int6], [], word(token.value))
        case 'fcon':
            node = Leaf('fcon', token.linenum, [
                        Double6], [], float(token.value))
        case 'string':
            assert isinstance(token.value, bytes)
            node = Leaf('string', token.linenum,
                        [TypeElem('array', len(token.value)), Char6],
                        [], token.value)
        case '(':
            node = exp15(parser)
            parser.need(')')
        case _:
            raise ValueError
    while True:
        token = parser.match('(', '[', '->', '.')
        if not token:
            return node
        match token.label:
            case '(':
                args = []

                def callback(parser: Parser, token: Token) -> bool:
                    """Add an argument to the arg list."""
                    parser.unsee(token)
                    args.append(exp14(parser))
                    return True
                parser.list(')', callback)
                node = build(parser, token.linenum, 'call', [node] + args)
            case '[':
                node = build(parser, token.linenum, 'deref',
                             [build(parser,
                                    token.linenum, 'add',
                                    [node, exp15(parser)]
                                    )])
                parser.need(']')
            case '.' | '->':
                label = token.label
                token = parser.need('name', msg='missing member name')
                if not token:
                    parser.termskip()
                    return node
                assert isinstance(token.value, str)
                node = domember(parser, token.linenum, node, label,
                                token.value)


def expression(parser: Parser, seecommas: bool = True) -> Node:
    """Parse an expression."""
    if seecommas:
        node = exp15(parser)
    else:
        node = exp14(parser)
    # Flush pending conversions
    return build(parser, node.linenum, None, [node])


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

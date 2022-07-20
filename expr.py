"""C6T - C version 6 by Troy - Expression Parsing"""

from __future__ import annotations
import collections.abc
from dataclasses import dataclass, field
from typing import Any, Callable
from parse_state import Parser
from symtab import Symbol
from type6 import Char6, Double6, Func6, Int6, Point6, TypeElem, TypeString, tysize
from util import word
from lexer import Token
import opinfo


@dataclass
class Node(collections.abc.MutableSequence):
    """An expression node."""
    label: str
    linenum: int = field(compare=False)
    typestr: TypeString
    children: list[Node]

    def __post_init__(self):
        assert isinstance(self.label, str)
        assert isinstance(self.linenum, int)
        assert isinstance(self.typestr, list)
        assert isinstance(self.children, list)
        assert all((isinstance(i, Node) for i in self.children))

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
    
    def floating(self) -> bool:
        """Return a flag for if this node is floating type or not."""
        if self.typestr and self.typestr[0].floating:
            return True
        return False


@dataclass
class Leaf(Node):
    """A leaf expression node."""
    value: Any


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


def confold(node: Node) -> Node:
    """If the node can be constant folded, return the folded version. Else,
    return the node unmodified.
    """
    if any(map(lambda n: n.label != 'con', node.children)):
        return node
    children = [word(child.value) for child in node.children]
    match node.label:
        case 'add':
            result = word(sum(children))
        case 'sub':
            result = word(children[0] - children[1])
        case 'mult':
            result = word(children[0] * children[1])
        case 'div':
            result = word(children[0] // children[1])
        case 'mod':
            result = word(children[0] % children[1])
        case 'and':
            result = word(children[0] & children[1])
        case 'or':
            result = word(children[0] | children[1])
        case 'eor':
            result = word(children[0] ^ children[1])
        case 'lshift':
            result = word(children[0] << children[1])
        case 'rshift':
            result = word(children[0] >> children[1])
        case 'neg':
            result = word(-children[0])
        case 'compl':
            result = word(~children[0])
        case _:
            return Node
    return Leaf('con', node.linenum, [Int6], [], result)


def floating(*nodes: Node) -> bool:
    """Return a flag for if any of the nodes are floating type."""
    return any(map(lambda n: n.typestr[0].floating, nodes))


def pointer(*nodes: Node) -> bool:
    """Return a flag for if any of the nodes are pointer type."""
    return any(map(lambda n: n.typestr[0].pointer, nodes))


def doarray(node: Node) -> Node:
    """Convert an array type node to &->node of type pointer.
    """
    if node.label != 'addr' and node.typestr[0].type == 'array':
        node = Node('addr', node.linenum,
                    [Point6] + node.typestr[1:],
                    [node])
    return node


def dofunc(node: Node) -> Node:
    """Convert a function type node to addr to pointer to function.
    """
    if node.typestr[0].type == 'func':
        node = Node(
            'addr',
            node.linenum,
            [Point6] + node.typestr,
            node)
    return node


def build(parser: Parser, linenum: int, label: str | None,
          children: list[Node]) -> Node:
    """Construct a new non-leaf node."""
    if label == 'sizeof':
        return Leaf('con', children[0].linenum,
                    [Int6], [], tysize(children[0].typestr))

    if label is None:
        return dofunc(doarray(children[0]))

    if label == 'call':
        if not children[0].typestr[0].type == 'func':
            parser.error('call of non-function')
        node = Node(
            'call',
            linenum,
            children[0].typestr[1:],
            children
        )
        return node

    match len(children):
        case 1:
            typestr = children[0].typestr.copy()
        case 0:
            typestr = [Int6]
        case _:
            if floating(*children):
                typestr = [Double6]
            elif pointer(*children):
                for child in children:
                    if pointer(child):
                        typestr = child.typestr.copy()
                        break
            else:
                typestr = [Int6]
    node = Node(label, linenum, typestr, children)

    for i, child in enumerate(node.children[1:]):
        node.children[i+1] = dofunc(doarray(child))

    if label != 'addr':
        node.children[0] = doarray(node.children[0])
        if label != 'call':
            node.children[0] = dofunc(node.children[0])

    if opinfo.needlval[label] and not opinfo.islval[children[0].label]:
        parser.error('missing required lval')

    match label:
        case 'toint':
            node.typestr = [Int6]
            return node
        case 'toflt':
            node.typestr = [Double6]
            return node
        case 'cond':
            assert len(node.children) == 3
            _, left, right = node.children
            if left.typestr == right.typestr:
                node.typestr = left.typestr.copy()
            else:
                node.typestr = [Int6] # ? also need floats
            return node
        case 'deref':
            if children[0].label == 'addr':
                return children[0]
            if not typestr[0].pointer:
                parser.error('dereference of non-pointer')
            else:
                node.typestr = node.typestr[1:]
        case 'addr':
            if children[0].label == 'deref':
                node = node.children[0]
            node.typestr.insert(0, Point6)
        case 'postinc' | 'preinc' | 'postdec' | 'preinc':
            del node.children[1:]
            if pointer(*node.children):
                size = tysize(node.children[0].typestr)
            else:
                size = 1
            node.children.append(Leaf(
                'con', linenum, [Int6], [],
                size)
            )

    if len(children) == 2 and not opinfo.noconv[node.label]:
        if floating(*node.children):
            for i, child in enumerate(node.children):
                if not child.typestr[0].floating:
                    node.children[i] = build(
                        parser, linenum, 'toflt', [child]
                    )
        elif pointer(*node.children):
            if not opinfo.nopointconv[node.label]:
                size = 1
                for child in node.children:
                    if child.typestr[0].pointer:
                        size = tysize(child.typestr[1:])
                        break
                for i, child in enumerate(node.children):
                    if not child.typestr[0].pointer:
                        node.children[i] = build(
                            parser,
                            linenum,
                            'mult',
                            [child,
                             Leaf(
                                 'con',
                                 linenum,
                                 [Int6],
                                 [],
                                 size
                             )]
                        )

    if opinfo.isint[node.label]:
        node.typestr = [Int6]

    if opinfo.lessgreat[node.label] and pointer(*node.children) and node.label[0] != 'u':
        node.label = 'u' + node.label

    if floating(*node.children, node) and not opinfo.yesflt:
        parser.error("illegal operation for floating type")

    return confold(node)


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
        'sizeof': 'sizeof',
        '*': 'deref'
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
    if member not in parser.tagtab:
        parser.error(f'undefined member tag {member}')
        return node
    tag = parser.tagtab[member]
    if tag.storage != 'member':
        parser.error(f'tag {member} not a member')
        return node
    if label == '->':
        label = 'arrow'
    else:
        label = 'dot'
    node = build(parser, linenum, label,
                 [node, Leaf('con', linenum, [Int6], [], tag.offset)])
    node.typestr = tag.typestr.copy()
    return node


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

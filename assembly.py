"""C6T - C version 6 by Troy - Assembly Supports"""

from string import whitespace
from expr import Leaf, Node
from parse_state import Parser
import opinfo
from symtab import Symbol


def asm(parser: Parser, line: str) -> None:
    """Place an assembly line into the parser's output.
    """
    if not line.endswith('\n'):
        line = line + '\n'
    if not line[0] in whitespace:
        line = '\t' + line
    parser.asm += line


def deflab(parser, name: str) -> None:
    """Define an assembly label here.
    """
    parser.asm += f'{name}:'


def pseudo(parser, line: str) -> None:
    """Assemble a pseudo-op here.
    """
    if line[0] == '.':
        line = line[1:]
    asm(parser, '.' + line)


def fasm(parser, line: str, flag: bool) -> None:
    """Assemble the instruction, prepending a 'f' if the flag is True.
    """
    if flag:
        line = 'f' + line.lstrip()
    asm(parser, line)


def asmexpr(parser: Parser, node: Node) -> None:
    """Assemble an expression tree."""
    goseg(parser, 'text')
    asmnode(parser, node)
    rval(parser, node)


def rval(parser: Parser, node: Node) -> None:
    """If the node is an lval, do a load operation.
    """
    if opinfo.islval[node.label]:
        match node.typestr[0].type:
            case 'char':
                cmd = 'cload'
            case 'float':
                cmd = 'fload'
            case 'double':
                cmd = 'dload'
            case _:
                cmd = 'load'
        asm(parser, cmd)


def asmval(parser: Parser, leaf: Leaf) -> str:
    """Convert the value of a Leaf node into a string representation for
    output.
    """
    assert isinstance(leaf, Leaf)
    value = leaf.value
    match leaf.label:
        case 'name':
            assert isinstance(value, Symbol)
            match value.storage:
                case 'auto' | 'register':
                    return f'{value.storage} {value.offset}'
                case 'extern':
                    return f'extern _{value.name}'
                case 'static':
                    return f'extern {value.offset}'
                case _:
                    raise ValueError(f'bad storage {value.storage}')
        case 'con' | 'fcon':
            return f'{leaf.label} {leaf.value}'
        case 'string':
            oldseg = goseg(parser, 'string')
            lab = parser.nextstatic()
            deflab(parser, lab)
            asm(parser, f".dc {','.join((str(b) for b in value))}")
            goseg(parser, oldseg)
            return f'extern {lab}'
        case _:
            raise ValueError(f'bad leaf node {leaf.label}')


def asmchildren(parser: Parser, node: Node) -> None:
    """Run asmnode on all the children of the node in order."""
    for i, child in enumerate(node.children):
        asmnode(parser, child)
        if i == 0 and opinfo.needlval[node.label]:
            continue
        rval(parser, child)


def asmnode(parser: Parser, node: Node) -> None:
    """Assemble expression nodes recursively."""
    match node.label:
        case 'assign':
            assert len(node.children) == 2
            match node.children[0].typestr[0].type:
                case 'float':
                    label = 'fstore'
                case 'double':
                    label = 'dstore'
                case 'char':
                    label = 'cstore'
                case _:
                    label = 'store'
            asmchildren(parser, node)
            asm(parser, label)
        case 'dot' | 'arrow':
            assert len(node.children) == 2
            asmnode(parser, node.children[0])
            if node.label == 'arrow':
                rval(parser, node.children[0])
            assert isinstance(node.children[1], Leaf) and \
                node.children[1].label == 'con' and \
                isinstance(node.children[1].value, int)
            offset = node.children[1].value
            if offset:
                asm(parser, f'con {offset}')
                asm(parser, 'add')
        case 'addr' | 'deref':
            # do nothing
            asmchildren(parser, node)
        case 'call':
            assert len(node.children) >= 1
            for child in reversed(node.children[1:]):
                asmnode(parser, child)
                rval(parser, child)
                asm(parser, 'push')
            asmnode(parser, node.children[0])
            asm(parser, 'call')
        case _:
            asmchildren(parser, node)
            if isinstance(node, Leaf):
                asm(parser, asmval(parser, node))
            else:
                asm(parser, node.label)


def goseg(parser: Parser, segment: str) -> str:
    """Enter a new segment, returning the old one.
    """
    oldseg = parser.curseg
    if parser.curseg != segment:
        if segment != '':
            pseudo(parser, segment)
        parser.curseg = segment
    return oldseg

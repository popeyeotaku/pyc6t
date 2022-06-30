"""C6T - C version 6 by Troy - Assembly Supports"""

from string import whitespace
from expr import Leaf, Node, floating
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
    asm(parser, 'clear')
    asmnode(parser, node)
    rval(parser, node)


def rval(parser: Parser, node: Node) -> None:
    """If the node is an lval, do a load operation.
    """
    if node.label == 'name':
        assert isinstance(node, Leaf) and isinstance(node.value, Symbol)
        if node.value.storage == 'register':
            asm(parser, f'grabreg {node.value.offset}')
            return
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


def asmnode(parser: Parser, node: Node) -> None:
    """Assemble expression nodes recursively."""
    # Special cases
    if opinfo.assign[node.label]:
        asmnode(parser, node.children[0])
        if node.label != 'assign':
            asm(parser, 'dup')
            rval(parser, node.children[0])
        asmnode(parser, node.children[1])
        rval(parser, node.children[1])
        if node.label != 'assign':
            asm(parser, node.label.removeprefix('asn'))
        if node[0].label == 'name':
            assert isinstance(node[0], Leaf) and isinstance(
                node[0].value, Symbol)
            if node[0].value.storage == 'register':
                asm(parser, f'putreg {node[0].value.offset}')
                return
        match node[0].typestr[0].type:
            case 'float':
                cmd = 'fstore'
            case 'double':
                cmd = 'dstore'
            case 'char':
                cmd = 'cstore'
            case _:
                cmd = 'store'
        asm(parser, cmd)
        return
    match node.label:
        case 'postinc' | 'postdec' | 'preinc' | 'predec':
            label = node.label
            assert isinstance(node[1], Leaf) and isinstance(node[1].value, int)
            size = node[1].value
            if node[0].label == 'name':
                assert isinstance(node[0], Leaf) and isinstance(
                    node[0].value, Symbol)
                if node[0].value.storage == 'register':
                    asm(parser, f'reg{label} {node[0].value.offset}, {size}')
                    return
            asmnode(parser, node[0])
            asm(parser, f'{label} {size}')
        case 'logand':
            asmnode(parser, node[0])
            rval(parser, node[0])
            falselab = parser.nextstatic()
            fasm(parser, 'dup', floating(node[0]))
            fasm(parser, f'brz {falselab}', floating(node[0]))
            fasm(parser, 'drop', floating(node[0]))
            asmnode(parser, node[1])
            rval(parser, node[1])
            deflab(parser, falselab)
            asm(parser, 'log')
            return
        case 'call':
            for arg in reversed(node.children[1:]):
                asmnode(parser, arg)
                rval(parser, arg)
            asmnode(parser, node.children[0])
            asm(parser, f'call {len(node.children[1:])}')
            return
        case 'con' | 'fcon':
            assert isinstance(node, Leaf)
            fasm(parser, f'push {node.value}', node.label == 'fcon')
            return
        case 'name':
            assert isinstance(node, Leaf) and isinstance(node.value, Symbol)
            match node.value.storage:
                case 'auto':
                    asm(parser, f'auto {node.value.offset}')
                case 'static':
                    asm(parser, f'push {node.value.offset}')
                case 'extern':
                    asm(parser, f'push {node.value.name}')
                case 'register':
                    return
                case _:
                    parser.crash('BAD NAME NODE')
            return
        case 'string':
            assert isinstance(node, Leaf) and isinstance(node.value, bytes)
            label = parser.nextstatic()
            asm(parser, f'push {label}')
            assert label not in parser.strings
            parser.strings[label] = node.value
            return
    if len(node.children) > 0:
        asmnode(parser, node.children[0])
        if not opinfo.needlval[node.label]:
            rval(parser, node.children[0])
        for child in node.children[1:]:
            asmnode(parser, child)
            rval(parser, child)
    match node.label:
        case 'deref' | 'addr':
            pass
        case _:
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

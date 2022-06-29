"""C6T - C version 6 by Troy - Assembly Supports"""

from string import whitespace
from expr import Leaf, Node
from parse_state import Parser


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
    # TODO: assemble expressions
    for child in node.children:
        asmexpr(parser, child)
    if isinstance(node, Leaf):
        asm(parser, f'{node.label} {node.value}')
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

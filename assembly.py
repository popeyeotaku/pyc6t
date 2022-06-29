"""C6T - C version 6 by Troy - Assembly Supports"""

from string import whitespace
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

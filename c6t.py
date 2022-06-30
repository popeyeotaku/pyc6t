"""C6T - C version 6 by Troy - Main Compiler File"""

import pathlib
from lexer import Tokenizer
import preproc
import spec
from parse_state import Parser


def compile_c6t(source: str) -> str:
    """Returned compiled VM assembly from the given C6T source text."""
    source = preproc.preproc(source)
    parser = Parser(Tokenizer(source))

    while not parser.match('eof'):
        spec.extdef(parser)

    return parser.asm


def test():
    """A simple test program.
    """
    print(compile_c6t(pathlib.Path('test.c').read_text('utf8')))


if __name__ == "__main__":
    test()

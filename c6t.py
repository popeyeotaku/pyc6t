"""C6T - C version 6 by Troy - Main Compiler File"""
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


if __name__ == "__main__":
    testsrc = """
int foo[2+2], bar[4], foobar[sizeof(foo) + sizeof(bar)];
"""
    print(compile_c6t(testsrc))

"""C6T - C version 6 by Troy - Main Compiler File"""
import preproc
import spec
from parse_state import Parser


def compile_c6t(source: str) -> str:
    """Returned compiled VM assembly from the given C6T source text."""
    source = preproc.preproc(source)
    parser = Parser(source)

    while not parser.match('EOF'):
        spec.extdef(parser)

    return parser.asm

"""C6T - C version 6 by Troy - Main Compiler File"""

import pathlib
from assembly import deflab, goseg, pseudo
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

    for label, text in parser.strings.items():
        goseg(parser, 'data')
        deflab(parser, label)
        pseudo(parser, f'db {",".join(map(str, text))}')

    return parser.asm


def main(name:pathlib.Path|str):
    """Compile the given file.
    """
    name = pathlib.Path(name)
    asm = compile_c6t(name.read_text('utf8'))
    out = name.with_suffix('.ir')
    out.write_text(asm, encoding='utf8')


def test():
    """Compile some test programs.
    """
    main('hello.c')

if __name__ == "__main__":
    test()

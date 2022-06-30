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


def test():
    TESTSRC = r"""

foobar(foo, bar, func)
int (*func)();
int foo[];
{
    register b, *f, i;
    
    if (!func) return;

    if ((b = bar) && (f = foo)) {
        for (i = 0; i < b; i++)
            f[i] =+ (*func)(f[i]);
    }
}
"""
    print(compile_c6t(TESTSRC))


if __name__ == "__main__":
    test()

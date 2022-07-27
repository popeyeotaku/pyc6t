"""C6T - C version 6 by Troy - Main Compiler File"""

import sys
import argparse
from pathlib import Path
from assembly import deflab, goseg, pseudo
import c8080
from lexer import Tokenizer
import preproc
import spec
import backend
from parse_state import Parser

DEBUG = False


def compile_c6t(source: str) -> tuple[str, int]:
    """Preprocess and compile the given source text. Returns the compiled text
    and an error count.
    """
    source = preproc.preproc(source)
    tokenizer = Tokenizer(source)
    parser = Parser(tokenizer)

    while not parser.match('eof'):
        spec.extdef(parser)

    for label, text in parser.strings.items():
        goseg(parser, 'data')
        deflab(parser, label)
        pseudo(parser, f'db {",".join(map(str, text))}')

    errors = parser.errcount + tokenizer.errcount
    if errors:
        print(f'Total errors: {errors}')

    return parser.asm, errors


def compilefile(path: Path | str) -> tuple[str | None, str | None]:
    """Compile the given file. Tries to return the IR representation from the
    frontend and the final assembly file. If it cannot produce one of these
    due to errors, it will return None for that file isntead.
    """
    path = Path(path)
    ir_source, errors = compile_c6t(path.read_text('utf8'))
    if errors:
        return None, None

    try:
        codegen = c8080.Code80()
    # pylint:disable=broad-except
    except BaseException as error:
        print("ERROR BUILDING CODEGEN:", repr(error))
        return ir_source, None
    try:
        asm = backend.backend(ir_source, codegen)
    # pylint:disable=broad-except
    except BaseException as error:
        print("ERROR ON BACKEND:", repr(error))
        return ir_source, None
    return ir_source, asm


cmdparse = argparse.ArgumentParser(
    description="C6T - C version 6 compiler by Troy")
cmdparse.add_argument('-P', help='save preprocessed verisons of the source'
                      'files in .i extensions', action='store_true')
cmdparse.add_argument('sources', nargs='+', help='the C6T source files')


def main() -> None:
    """Main called from command line."""
    if DEBUG:
        argv = ['test.c']
    else:
        argv = sys.argv
    args = cmdparse.parse_args(argv)
    for source in args.sources:
        assert isinstance(source, str)
        path = Path(source)
        if path.suffix.casefold() != '.c'.casefold():
            continue
        if hasattr(args, '-P'):
            out: Path = out.with_suffix('.i')
            preproced = preproc.preproc(path.read_text('utf8'))
            out.write_text(preproced, 'utf8')
        else:
            ir_source, asm = compilefile(source)
            if None in (ir_source, asm):
                continue
            path.with_suffix('.ir').write_text(ir_source, 'utf8')
            path.with_suffix('.s').write_text(asm, 'utf8')


if __name__ == "__main__":
    main()

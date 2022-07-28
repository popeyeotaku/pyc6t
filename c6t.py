"""C6T - C version 6 by Troy - Main Compiler File"""

import sys
import argparse
from pathlib import Path
from asm80 import Assembler
from assembly import deflab, goseg, pseudo
import c8080
from lexer import Tokenizer
from linker import Linker, Module
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
                      'files in .i extensions', action='store_true',
                      default=False, dest='preproc')
cmdparse.add_argument('-c', help='save object files only, no linkage',
                      action='store_true', default=False, dest='nolink')
cmdparse.add_argument('-o', help='output executable name', nargs=1,
                      default='a.out', dest='outname')
cmdparse.add_argument('-S', help='save assembly output only',
                      action='store_true', default=False, dest='outasm')
cmdparse.add_argument('-Y', help='output symbol files',
                      action='store_true', default=False, dest='outsym')
cmdparse.add_argument('-R', help='output intermediate format file',
                      action='store_true', default=False, dest='outir')
cmdparse.add_argument('sources', nargs='+', help='the C6T source files')


def main() -> None:
    """Main called from command line."""
    if DEBUG:
        argv = '-o hello.bin -Y hello.c'.split()
    else:
        argv = sys.argv[1:]
    args = cmdparse.parse_args(argv)
    modules: list[Module] = []
    for source in args.sources:
        assert isinstance(source, str)
        path = Path(source)
        if path.suffix == '.c':
            if args.preproc:
                out = preproc.preproc(path.read_text('utf8'))
                path.with_suffix('.i').write_text(out, 'utf8')
                continue
            ir_src, asm_src = compilefile(path)
            if None in (ir_src, asm_src):
                return
            if args.outir:
                path.with_suffix('.ir').write_text(ir_src, 'utf8')
            if args.outasm:
                path.with_suffix('.s').write_text(asm_src, 'utf8')
                continue
            assembler = Assembler(asm_src)
            module = assembler.assemble()
            if not module:
                return
            if args.nolink:
                path.with_suffix('.o').write_bytes(bytes(module))
                continue
            modules.append(module)
        elif path.suffix == '.s' and not args.nolink:
            assembler = Assembler(path.read_text('utf8'))
            module = assembler.assemble()
            if not module:
                continue
            modules.append(module)
        else:
            module = Module().from_bytes(path.read_bytes())
    if args.nolink or not modules:
        return
    linker = Linker(*modules)
    linked = linker.link()
    outname = args.outname[0]
    Path(outname).write_bytes(linked)
    if args.outsym:
        syms = ''
        for symbol in sorted(linker.symtab.values(),
                             key=lambda s: s.value):
            syms += f'{symbol.name}: ${hex(symbol.value)}/{oct(symbol.value)}\n'
        Path(outname).with_suffix('.sym').write_text(syms, 'utf8')


if __name__ == "__main__":
    main()

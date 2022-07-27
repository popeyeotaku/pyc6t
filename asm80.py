"""Intel 8080 linking assembler
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Iterable, Sequence, overload

from util import word

SEGS = ('.text', '.data', '.string', '.bss')


PSEUDOS: tuple[str] = (
    '.text', '.data', '.string', '.bss',
    '.byte', '.word', '.export', '.common',
    '.storage'
)


def mksegs() -> dict[str, list]:
    """Construct an empty segments dictionary."""
    segs = {}
    for seg in SEGS:
        segs[seg] = []
    return segs


class Mode(Enum):
    """Modes for differnet opcodes to incorporate their operands."""
    INL0 = auto()
    INL3 = auto()
    IMMBYTE = auto()
    IMMWORD = auto()


@dataclass(frozen=True)
class Opcode:
    """An Intel 8080 instruction opcode."""
    name: str
    code: int
    args: tuple[Mode]

    @overload
    def __init__(self, name: str, code: int, *args: str):
        ...

    def __init__(self, name: str, code: int, *args: Mode):
        arglist = [Mode[arg] for arg in args]
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, 'code', code)
        object.__setattr__(self, 'args', tuple(arglist))

    def __repr__(self) -> str:
        return f"Opcode({repr(self.name)}, {repr(self.code)}, " \
            f"{','.join((repr(arg) for arg in self.args))})"


def build_opcodes(path: str | Path = 'op80.json') -> dict[str, Opcode]:
    """Read in the opcodes from a json file."""
    path = Path(path)
    opcodes: dict[str, Opcode] = {}
    with path.open('r', encoding='utf8') as opfile:
        decoded = json.load(opfile)
    if not isinstance(decoded, list):
        raise TypeError(decoded)
    for elem in decoded:
        if not isinstance(elem, list):
            raise TypeError
        if len(elem) < 2:
            raise ValueError(elem)
        if not isinstance(elem[0], str):
            raise TypeError(elem)
        if isinstance(elem[1], str):
            elem[1] = int(elem[1], base=8)
        if not isinstance(elem[1], int):
            raise TypeError(elem)
        if not all((isinstance(arg, str) for arg in elem[2:])):
            raise TypeError(elem)
        opcode = Opcode(*elem)
        opcodes[opcode.name] = opcode
    return opcodes


opdict: dict[str, Opcode] = build_opcodes()


@dataclass
class Symbol:
    """A symbol table entry. Wherever the name is encountered, it should be
    replaced with the corresponding value. The label flag indicates whether
    this value exists in program space and should be linked relatively or
    else is just a constant. Exported means it should be visible to other
    modules for linking.

    If common is set, and this symbol is not defined anywhere, then this
    symbol should be reserved as 0 bytes in the bss segment. If it IS,
    however, defined as non-common anywhere, it should be ignored.
    """
    name: str
    value: int
    segment: str
    label: bool = False
    exported: bool = False
    common: bool = False
    offset: int = 0

    @property
    def final_val(self) -> int:
        """Return the final version of our value, taking into account
        the offset.
        """
        if self.label:
            return self.value + self.offset
        return self.value


class RefMode(Enum):
    """Specifies which type of reference this is."""
    WORD = auto()
    HIWORD = auto()
    LOWORD = auto()
    LOBYTE = auto()
    HIBYTE = auto()


@dataclass
class Reference:
    """Specifies a linking reference - something which may need to be
    located. relative specifies whether this should be taken as relative to
    the start of the linked module. con specifies an integer value. If symbol
    is not None, it is a symbol table reference, whose value should be added
    to con. The mask is used to and against the final value.
    """
    symbol: str | None = None
    con: int = 0
    relative: bool = False
    mode: RefMode = RefMode.WORD

    def __len__(self):
        if self.mode in (RefMode.LOBYTE, RefMode.HIBYTE):
            return 2
        return 1

    def tobytes(self, symtab: dict[str, Symbol]) -> bytes:
        """Try to convert the reference into a bytes object using the given
        symbol table.

        Raises ValueError on failure.
        """
        con = self.con
        if self.symbol:
            if self.symbol in symtab:
                symbol = symtab[self.symbol]
                con += symbol.value
                if self.relative:
                    con += symbol.offset
            else:
                raise ValueError(f'undefed symbol {self.symbol}')
        else:
            if self.relative:
                raise ValueError
        con = word(con)
        match self.mode:
            case RefMode.HIWORD:
                con &= 0xFF00
                length = 2
            case RefMode.LOWORD:
                con &= 0xFF
                length = 2
            case RefMode.LOBYTE:
                length = 1
            case RefMode.HIBYTE:
                con = word((con >> 8) & 0xFF)
                length = 1
            case _:
                length = 2
        if length == 1:
            con = word(con) & 0xFF
        con = word(con)
        return con.to_bytes(length, 'little')


@dataclass
class Module:
    """A collection of assembled data to be linked."""
    symtab: dict[str, Symbol] = field(default_factory=dict)
    segs: dict[str, list[bytes | Reference]] = field(default_factory=mksegs)
    curseg: str = '.text'

    def add(self, *elems: bytes | Reference) -> None:
        """Add an element to the current segment."""
        assert self.curseg in self.segs
        for elem in elems:
            if not isinstance(elem, (bytes, Reference)):
                raise TypeError(elem)
            self.segs[self.curseg].append(elem)

    def fixup(self) -> None:
        """Finalize everything."""
        for seg in self.segs.values():
            for elem in seg:
                if isinstance(elem, Reference):
                    if elem.symbol:
                        elem.relative = elem.symbol in self.symtab

    def exported(self) -> dict[str, Symbol]:
        """Return all exported symbols."""
        return {symbol.name: symbol for symbol in self.symtab.values()
                if symbol.exported}

    def references(self) -> Iterable[Reference]:
        """Return all references in all segs."""
        for seg in self.segs.values():
            for elem in seg:
                if isinstance(elem, Reference):
                    yield elem

    def undefed(self, symtab: dict[str, Symbol] = None) -> Iterable[Reference]:
        """Return iterable over all undefined references."""
        if symtab is None:
            symtab = {}
        symtab = symtab.copy()
        symtab.update(self.symtab)
        for reference in self.references():
            if reference.symbol and reference.symbol not in self.symtab:
                yield reference

    def tobytes(self, seg: str = None,
                symtab: dict[str, Symbol] = None) -> bytes:
        """Try to convert the given segment into bytes.

        Raise ValueError on failure.
        """
        if symtab is None:
            symtab = {}
        symtab = symtab.copy()
        symtab.update(self.symtab)
        if seg is None:
            seg = self.curseg
        if seg not in self.segs:
            raise ValueError(seg)
        total = bytes()
        for elem in self.segs[seg]:
            if isinstance(elem, bytes):
                total += elem
            elif isinstance(elem, Reference):
                total += elem.tobytes(symtab)
        return total

    def __len__(self) -> int:
        assert self.curseg in self.segs
        return sum((len(elem) for elem in self.segs[self.curseg]))


STARTSYM: dict[str, int] = {
    'b': 0o0,
    'c': 0o1,
    'd': 0o2,
    'e': 0o3,
    'h': 0o4,
    'l': 0o5,
    'm': 0o6,
    'a': 0o7,
    'sp': 0o6,
    'psw': 0o6
}


class ArgMode(Enum):
    """Contains whether we should use the low or the high mode of the
    argument.
    """
    NORM = auto()
    LO = auto()
    HI = auto()


@dataclass
class Arg:
    """An expression argument."""
    con: int = 0
    symbol: str | None = None
    mode: ArgMode = ArgMode.NORM

    def literal(self, onebyte: bool = False) -> bytes:
        """If this argument has no symbol set, return a bytes object
        of us.
        """
        if self.symbol:
            raise ValueError('not a literal Arg')
        con = word(self.con).to_bytes(2, 'little') + bytes([0])
        if self.mode == ArgMode.HI:
            return bytes([con[1]])
        if onebyte:
            return bytes([con[0]])
        return bytes(con[:2])

    def refmode(self, isword: bool) -> RefMode:
        """Construct the corresponding RefMode."""
        mode = None
        if isword:
            match self.mode:
                case ArgMode.LO:
                    mode = RefMode.LOWORD
                case ArgMode.HI:
                    mode = RefMode.HIWORD
                case _:
                    mode = RefMode.WORD
        else:
            if self.mode == ArgMode.HI:
                mode = RefMode.HIBYTE
            else:
                mode = RefMode.LOBYTE
        assert mode in RefMode
        return mode


class Assembler:
    """Constructs an assembled module from assembly source code."""

    def __init__(self, source: str, index: int = 0):
        self.source = source
        self.index = index
        self.module = Module()
        self.errcount = 0
        for name, val in STARTSYM.items():
            symbol = Symbol(name, val, self.curseg, False)
            self.addsym(symbol)

    @property
    def curseg(self) -> str:
        """The module's current segment."""
        return self.module.curseg

    @property
    def curpc(self) -> int:
        """The current program counter position in the current segment."""
        return len(self.module)

    @property
    def symtab(self) -> dict[str, Symbol]:
        """The symbol table for our module."""
        return self.module.symtab

    def addsym(self, symbol: Symbol) -> None:
        """Add the symbol to the symbol table.
        """
        if symbol.name in self.symtab:
            self.error(f'redefined symbol {symbol.name}')
        self.symtab[symbol.name] = symbol

    @property
    def text(self) -> str:
        """The source text starting at the given index."""
        return self.source[self.index:]

    @property
    def linenum(self) -> int:
        """Return the current line number."""
        return 1 + self.source[:self.index].count('\n')

    def matchre(self, pattern: str) -> re.Match | None:
        """Try to match a regular expression. If it matches, skip past it in
        the text and return the match object. Else, return None and skip
        nothing.
        """
        if match := re.match(pattern, self.text):
            self.index += len(match[0])
            return match
        return None

    def matchlit(self, *literals: str) -> str | None:
        """If any literal matches the start of our source text, skip it and
        return the literal. Else, skip nothing and return None.

        The literals are checked in order, so the first one that matches
        gets returned.
        """
        self.skipws()
        for literal in literals:
            if self.text.startswith(literal):
                self.index += len(literal)
                return literal
        return False

    def skipws(self) -> None:
        """Skip leading whitespace, including comment, NOT including newlines.
        """
        self.matchre(r'(([^\S\n]+)|(;[^\n]*))+')

    def skipws_nl(self) -> None:
        """Skip leading whitespace, comments, AND newlines."""
        self.matchre(r'((;[^\n]*\n)|([\s]+))*')

    def atom(self) -> str | int | None:
        """Parse a name or number."""
        self.skipws()
        if match := self.matchre(r'\$([\da-fA-F]+)'):
            con = int(match[1], base=16)
            con = word(con)
            return con
        if match := self.matchre(r'\d+'):
            return word(int(match[0]))
        if match := self.matchre(r'[.a-zA-Z_][.a-zA-Z_0-9]*'):
            return match[0]
        return None

    def error(self, msg: str) -> None:
        """Display an error."""
        print(f'ERROR {self.linenum}: {msg}')
        self.errcount += 1

    def nextline(self) -> None:
        """Skip to the next line."""
        self.matchre(r'[^\n]*\n')

    def statement(self) -> None:
        """Parse a single statement."""
        self.skipws_nl()
        if not self.text:
            return
        atom = self.atom()
        if not isinstance(atom, str):
            self.error('missing start of command')
            self.nextline()
            return
        if self.matchlit(':'):
            self.addlabel(atom)
        elif self.matchlit('=', '.equ'):
            arg = self.expr()
            if arg.symbol:
                if arg.symbol not in self.symtab:
                    self.error('= can only use predefined symbols')
                    return
                if self.symtab[symbol].common:
                    self.error('cannot = with a common symbol')
                    return
                symbol = Symbol(atom, self.symtab[arg.symbol] + arg.con,
                                self.curseg,
                                self.symtab[arg.symbol].label)
            else:
                symbol = Symbol(atom, arg.con, self.curseg, label=False)
        else:
            cmd = atom
            args: list[Arg] = []
            while not self.matchlit('\n'):
                args.append(self.expr())
                if not self.matchlit(','):
                    break
            if cmd in opdict:
                self.addop(cmd, args)
            elif cmd in PSEUDOS:
                self.pseudo(cmd, args)
            else:
                self.error(f'bad opcode {cmd}')

    def pseudo(self, cmd: str, args: list[Arg]) -> None:
        """Handle a pseudo op."""
        match cmd:
            case '.storage':
                if len(args) != 2:
                    args.append(Arg(0))
                if len(args) != 2:
                    self.error('bad arg count')
                    return
                if args[1].symbol or args[0].symbol:
                    self.error('bad format')
                    return
                self.module.add(bytes([args[1].con] * args[0].con))
            case '.text' | '.data' | '.string' | '.bss':
                self.module.curseg = cmd
            case '.byte' | '.word':
                for arg in args:
                    if arg.symbol:
                        refmode = arg.refmode(cmd == '.word')
                        self.module.add(
                            Reference(
                                arg.symbol, word(arg.con),
                                mode=refmode
                            )
                        )
                    else:
                        con = arg.literal(cmd == '.byte')
                        self.module.add(con)
            case '.common':
                if len(args) != 2:
                    self.error('bad operand count')
                    return
                if not (args[0].symbol and args[1].con == 0):
                    self.error('bad common')
                    return
                if args[1].symbol is None:
                    self.error('bad common')
                    return
                self.addsym(Symbol(
                    args[0].symbol, args[1].value,
                    self.curseg, common=True, exported=True
                ))
            case '.export':
                for arg in args:
                    if arg.con or not arg.symbol:
                        self.error('bad symbol')
                        return
                    if arg.symbol not in self.symtab:
                        self.error('must export AFTER define')
                        return
                    self.symtab[arg.symbol].exported = True
            case _:
                raise ValueError(cmd)

    def expr(self) -> Arg:
        """Parse an expression."""
        if self.matchlit('<'):
            mode = ArgMode.LO
        elif self.matchlit('>'):
            mode = ArgMode.HI
        else:
            mode = ArgMode.NORM

        left = self.primary()
        while oper := self.matchlit('+', '-'):
            right = self.primary()
            match oper:
                case '-':
                    if right.symbol:
                        self.error('bad expression')
                    else:
                        left.con = word(left.con - right.con)
                case '+':
                    if right.symbol:
                        left, right = right, left
                    if right.symbol:
                        self.error('bad expression')
                    else:
                        left.con = word(left.con + right.con)

        left.mode = mode
        return left

    def primary(self) -> Arg:
        """Parse a primary expression."""
        atom = self.atom()
        if atom is None:
            self.error('missing primary expression')
            return Arg(0)
        if isinstance(atom, str):
            return Arg(0, atom)
        assert isinstance(atom, int)
        return Arg(word(atom))

    def addop(self, cmd: str, args: list[Arg]) -> None:
        """Assemble a given opcode here."""
        opcode = opdict[cmd]
        if len(args) != len(opcode.args):
            self.error('bad operand length')
            return
        code = opcode.code
        outargs: list[Reference | bytes] = []
        for mode, arg in zip(opcode.args, args):
            match mode:
                case Mode.INL0 | Mode.INL3:
                    if arg.symbol:
                        if arg.symbol in self.symtab and \
                                not self.symtab[arg.symbol].label:
                            con = self.symtab[arg.symbol].value + arg.con
                        else:
                            self.error('bad arg')
                            return
                    else:
                        con = arg.con
                    mask = word(con) & 0o7
                    if mode == Mode.INL3:
                        mask <<= 3
                    code |= mask
                case Mode.IMMWORD | Mode.IMMBYTE:
                    if arg.symbol:
                        refmode = arg.refmode(mode == Mode.IMMWORD)
                        outargs.append(Reference(
                            arg.symbol, word(arg.con), mode=refmode
                        ))
                    else:
                        con = arg.literal(mode == Mode.IMMBYTE)
                        outargs.append(con)

        code = word(code & 0xFF)
        self.module.add(code.to_bytes(1, 'little'), *outargs)

    def addlabel(self, name: str) -> None:
        """Add a label to the symbol table."""
        self.addsym(Symbol(
            name, self.curpc, self.curseg, label=True
        ))

    def assemble(self) -> Module | None:
        """Try to assemble the source text. If any errors were encountered,
        return None. Else, return the module.
        """
        while self.text:
            self.statement()
        if self.errcount:
            return None
        self.module.fixup()
        return self.module


class Linker:
    """Links together several modules and import libraries.
    """

    def __init__(self, modules: Sequence[Module], libraries: Sequence[Module] = None):
        if libraries is None:
            libraries = []
        self.modules = tuple(modules)
        self.libraries = tuple(libraries)
        self.usedlibs: list[Module] = []

    @property
    def allmods(self) -> list[Module]:
        """Modules + used libraries."""
        return list(self.modules) + self.usedlibs

    @property
    def symtab(self) -> dict[str, Symbol]:
        """Return all exported symbols."""
        table: dict[str, Symbol] = {}
        for module in reversed(self.allmods):
            table.update(module.exported())
        return table

    @property
    def unused_libs(self) -> list[Module]:
        """Return all unused libraries."""
        return [lib for lib in self.libraries if lib not in self.usedlibs]

    def undefed(self) -> Iterable[Reference]:
        """Return all undefined references."""
        for module in self.allmods:
            for undefed in module.undefed(self.symtab):
                yield undefed

    def __bytes__(self) -> bytes:
        total = bytes()
        for seg in SEGS:
            for module in self.allmods:
                data = module.tobytes(seg, self.symtab)
                if seg == '.bss':
                    total += bytes(len(data))
                else:
                    total += data
        return total

    def link(self) -> bytes:
        """Link all modules."""
        self.findlibs()
        self.fixrels()
        return bytes(self)

    def fixrels(self) -> None:
        """Fix all relative symbols to be at the proper offsets."""
        offset = 0
        for seg in SEGS:
            for mod in self.allmods:
                for symbol in (sym for sym in mod.symtab.values()
                               if sym.segment == seg):
                    symbol.offset = offset
                offset += len(mod.tobytes(seg, self.symtab))

    def findlibs(self):
        """Find all libraries that should be linked in."""
        self.usedlibs.clear()

        while undeflist := list(self.undefed()):
            found = False
            for library in self.usedlibs:
                if undeflist[0].symbol in library.symtab:
                    self.usedlibs.append(library)
                    found = True
                    break
            if not found:
                raise ValueError(f'unfound symbol {undeflist[0].symbol}')

    def pretty_symtab(self) -> Iterable[tuple[str, int]]:
        """A nicer form of our symbol table."""
        for symbol in sorted(self.symtab.values(),
                             key=lambda s: s.final_val):
            yield symbol.name, symbol.final_val


def test(path: str | Path):
    """A simple test program."""
    path = Path(path)
    asm = Assembler(path.read_text('utf8'))
    out = asm.assemble()
    if out:
        linker = Linker([out])
        outpath = path.with_suffix('.bin')
        outpath.write_bytes(linker.link())
        outpath = path.with_suffix('.sym')
        symtab = ''
        for name, val in linker.pretty_symtab():
            symtab += f'{name}: ${hex(val)}\n'
        outpath.write_text(symtab, 'utf8')


if __name__ == "__main__":
    test('hello.s')

"""Intel 8080 linking assembler
"""

from argparse import ArgumentParser
import json
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import overload

from util import word
from linker import Reference, RefFlag, Symbol as LinkSym, SymFlag, Module, SEGS

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


@dataclass
class Symbol(LinkSym):
    """Flags whether the symbol is a label or not."""
    label: bool = field(kw_only=True)

    def linksym(self) -> LinkSym:
        """Return a linker symbol version of this symbol."""
        return LinkSym(self.flags, self.name, self.value)


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


class ReferenceMode(Enum):
    """Contains whether we should use the low or the high mode of the
    argument.
    """
    NORM = auto()
    LO = auto()
    HI = auto()


class Assembler:
    """Constructs an assembled module from assembly source code."""

    def __init__(self, source: str, index: int = 0):
        self.source = source + '\n'  # some matches can fail if not
        self.index = index
        self.module = Module()
        self.segname: str = 'text'
        self.errcount = 0
        self.bss_seg: list[bytes | Reference] = []
        self.symtab: dict[str, Symbol] = {}
        for name, val in STARTSYM.items():
            symbol = Symbol(self.segnum, name, val, label=False)
            self.addsym(symbol)

    @property
    def segnum(self) -> SymFlag:
        """Return the segment number."""
        return SEGS[self.segname]

    @property
    def curseg(self) -> list[bytes | Reference]:
        """Return the current segment."""
        match self.segname:
            case 'text':
                return self.module.text
            case 'data':
                return self.module.data
            case 'bss':
                return self.bss_seg

    @property
    def curpc(self) -> int:
        """The current program counter position in the current segment."""
        return Module.seglen(self.curseg)

    def addsym(self, symbol: Symbol) -> None:
        """Add the symbol to the symbol table.
        """
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
        if match := self.matchre(r'(-?)\$([\da-fA-F]+)'):
            con = int(match[1] + match[2], base=16)
            con = word(con)
            return con
        if match := self.matchre(r'-?\d+'):
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
                if arg.name not in self.symtab:
                    self.error('= can only use predefined symbols')
                    return
                if self.symtab[arg.name].common:
                    self.error('cannot = with a common symbol')
                    return
                symbol = Symbol(self.segnum, atom,
                                arg.con + self.symtab[arg.name],
                                label=False)
            else:
                symbol = Symbol(self.curseg, atom, arg.con, label=False)
            self.addsym(symbol)
        else:
            cmd = atom
            args: list[Reference] = []
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

    def add(self, *elems: bytes | Reference) -> None:
        """Add the given elements to our current segment."""
        seg = self.curseg
        for elem in elems:
            assert isinstance(elem, (bytes | Reference))
            seg.append(elem)

    def pseudo(self, cmd: str, args: list[Reference]) -> None:
        """Handle a pseudo op."""
        match cmd:
            case '.storage':
                if len(args) != 2:
                    args.append(Reference(0, '', 0))
                if len(args) != 2:
                    self.error('bad arg count')
                    return
                if args[1].symbol or args[0].symbol:
                    self.error('bad format')
                    return
                self.add(bytes([args[1].con] * args[0].con))
            case '.text' | '.data' | '.bss':
                self.segname = cmd[1:]
            case '.byte' | '.word':
                flags = RefFlag.BYTE if cmd == '.byte' else 0
                for arg in args:
                    argflags = arg.flags & (RefFlag.HI | RefFlag.HILO)
                    ref = Reference(flags | argflags, arg.name, arg.con)
                    if ref.symbol:
                        self.add(
                            Reference(flags | argflags, arg.name, arg.con)
                        )
                    else:
                        self.add(ref.resolve(0))
            case '.common':
                if len(args) != 2:
                    self.error('bad operand count')
                    return
                if not (args[0].symbol and not args[1].symbol):
                    self.error('bad common')
                    return
                if args[1].symbol is None:
                    self.error('bad common')
                    return
                symbol = Symbol(SymFlag.BSS | SymFlag.COMMON, args[0].name,
                                args[1].con, label=True)
                self.addsym(symbol)
            case '.export':
                for arg in args:
                    if arg.con or not arg.symbol:
                        self.error('bad symbol')
                        return
                    if arg.name not in self.symtab:
                        self.error(f'must export AFTER define: {arg.name}')
                        return
                    self.symtab[arg.name].flags |= SymFlag.EXPORT
            case _:
                raise ValueError(cmd)

    def expr(self) -> Reference:
        """Parse an expression."""
        flags: RefFlag = RefFlag.ALWAYS_SET
        if self.matchlit('<'):
            flags |= RefFlag.HILO | RefFlag.HI
        elif self.matchlit('>'):
            flags |= RefFlag.HILO
            flags &= ~RefFlag.HI

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

        left.flags |= flags
        return left

    def primary(self) -> Reference:
        """Parse a primary expression."""
        atom = self.atom()
        if atom is None:
            self.error('missing primary expression')
            return Reference(RefFlag.ALWAYS_SET, '', 0)
        if isinstance(atom, str):
            if atom in self.symtab and not self.symtab[atom].label:
                # Replace a non-label with its value
                return Reference(RefFlag.ALWAYS_SET, '',
                                 self.symtab[atom].value)
            return Reference(RefFlag.ALWAYS_SET | RefFlag.SYMBOL, atom, 0)
        assert isinstance(atom, int)
        return Reference(RefFlag.ALWAYS_SET, '', word(atom))

    def addop(self, cmd: str, args: list[Reference]) -> None:
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
                        if arg.name in self.symtab and \
                                not self.symtab[arg.name].label:
                            con = self.symtab[arg.name].value + arg.con
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
                    refmode = arg.flags & ~RefFlag.BYTE
                    if mode == Mode.IMMBYTE:
                        refmode |= RefFlag.BYTE

                    if arg.symbol:
                        outargs.append(Reference(
                            refmode, arg.name, word(arg.con)
                        ))
                    else:
                        con = Reference(refmode, '', arg.con).resolve(0)
                        outargs.append(con)

        code = word(code) & 0xFF
        self.add(code.to_bytes(1, 'little'), *outargs)

    def addlabel(self, name: str) -> None:
        """Add a label to the symbol table."""
        self.addsym(Symbol(
            self.segnum, name, self.curpc, label=True
        ))

    def assemble(self) -> Module | None:
        """Try to assemble the source text. If any errors were encountered,
        return None. Else, return the module.
        """
        self.index = 0
        while self.text:
            self.statement()
        if self.errcount:
            return None

        if self.errcount:
            return None

        self.module.symtab.clear()
        for sym in self.symtab.values():
            if sym.label:
                self.module.symtab[sym.name] = sym.linksym()
        self.module.bss_len = Module.seglen(self.bss_seg)
        return self.module


cmdline = ArgumentParser()
cmdline.add_argument('sources', nargs=1)


def main():
    """For using asm80 from the command line."""
    names = cmdline.parse_args()
    for source in names.sources:
        assert isinstance(source, str)
        path = Path(source)
        print(path)
        assembler = Assembler(path.read_text('utf8'))
        module = assembler.assemble()
        if not module:
            continue
        path.with_suffix('.o').write_bytes(bytes(module))


if __name__ == "__main__":
    main()

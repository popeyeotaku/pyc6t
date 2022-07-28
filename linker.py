"""C6T - C version 6 by Troy - Object File Linker."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntFlag
import struct
from util import word

NAMELEN = 8

STRUCT_HEADER = "<HHH"
STRUCT_BYTE = "<b"
STRUCT_UBYTE = "<B"
STRUCT_WORD = "<H"
STRUCT_NAME = f"<{NAMELEN}s"


def bytename(name: str) -> bytes:
    """Properly encode a bytes representation of a symbol name."""
    name = (name + '\x00' * NAMELEN)[:NAMELEN].encode('ascii')


class SymFlag(IntFlag):
    """Flags for a symbol table entry."""
    TEXT = 0
    DATA = 1
    BSS = 2
    SEG = 3
    EXTERN = 4
    EXPORT = 8
    COMMON = 16


@dataclass
class Symbol:
    """A symbol table entry."""
    flags: SymFlag
    name: str
    value: int

    @property
    def export(self) -> bool:
        """Flag for if this symbol is exported."""
        return bool(self.flags & SymFlag.EXPORT)

    @property
    def common(self) -> bool:
        """A flag for if this is a common marked symbol."""
        return bool(self.flags & SymFlag.COMMON)

    def __bytes__(self) -> bytes:
        return struct.pack(f"<{NAMELEN}sHB",
                           bytename(self.name),
                           self.value,
                           self.flags)

    def copy(self) -> Symbol:
        """Return a duplicate of the symbol"""
        return Symbol(self.flags, self.name, self.value)


SEGS = {'text': SymFlag.TEXT,
        'data': SymFlag.DATA,
        'bss': SymFlag.BSS}


class RefFlag(IntFlag):
    """Flags for a segment reference record."""
    BYTE = 1
    HI = 2
    SYMBOL = 4
    HILO = 8
    ALWAYS_SET = 16


@dataclass
class Reference:
    """A relocation reference in a segment."""
    flags: RefFlag
    name: str
    con: int

    @property
    def symbol(self) -> bool:
        """Return a flag for if this is a symbol reference or not."""
        return bool(self.flags & RefFlag.SYMBOL)

    def __len__(self) -> int:
        if self.flags & RefFlag.BYTE:
            return 1
        return 2

    def __bytes__(self) -> bytes:
        return struct.pack(f"<b{NAMELEN}sH",
                           -(self.flags | RefFlag.ALWAYS_SET),
                           bytename(self.name),
                           self.con)

    def resolve(self, offset: int, *symtabs: dict[str, Symbol]) -> bytes:
        """Resolve the reference, returning its byte value."""
        mode = ''
        if self.flags & RefFlag.HILO:
            if self.flags & RefFlag.HI:
                mode = 'hi'
            else:
                mode = 'lo'
        isword = not self.flags & RefFlag.BYTE

        if self.flags & RefFlag.SYMBOL:
            found = False
            for symtab in symtabs:
                if self.name in symtab:
                    symbol = symtab[self.name]
                    if symbol.flags & SymFlag.COMMON:
                        raise ValueError('illegal common')
                    data = self.con + symbol.value
                    found = True
                    break
            if not found:
                raise ValueError('undefined symbol', self.name)
        else:
            data = offset + self.con
        assert isinstance(data, int)
        data = word(data).to_bytes(2, 'little')
        assert len(data) == 2
        if mode == 'hi':
            data = bytes([data[1], 0])
        elif mode == 'lo':
            data = bytes([data[0], 0])
        if isword:
            return data
        return bytes([data[0]])


@dataclass
class Module:
    """A single object file."""
    text: list[bytes | Reference] = field(default_factory=list)
    data: list[bytes | Reference] = field(default_factory=list)
    symtab: dict[str, Symbol] = field(default_factory=dict)
    bss_len: int = 0

    def from_bytes(self, source: bytes) -> Module:
        """Parse the module from some source bytes."""
        textlen, datalen, bsslen = struct.unpack_from(STRUCT_HEADER,
                                                      source,
                                                      0)
        i = 6
        text, i = self._inseg(source, i)
        if self.seglen(text) != textlen:
            raise ValueError
        data, i = self._inseg(source, i)
        if self.seglen(data) != datalen:
            raise ValueError
        symtab, i = self._insyms(source, i)

        return Module(text, data, symtab, bsslen)

    def _inname(self, source: bytes, i: int) -> tuple[str, int]:
        """Read in a symbol name at the current position, returning it as a
        Python string and the new source offset 'i'.
        """
        namebytes = struct.unpack_from(STRUCT_NAME, source, i)[0]
        assert isinstance(namebytes, bytes)
        i += NAMELEN
        namebytes.removesuffix(b'\x00')
        return namebytes.decode('ascii')

    def _insyms(self, source: bytes, i: int) -> tuple[dict[str, Symbol], int]:
        """Read in the symbol table from the source bytes at the given i
        index, returning the symbol table and the new index.
        """
        symtab: dict[str, Symbol] = {}
        while True:
            if source[i] == 0:
                return symtab, i
            name, i = self._inname(source, i)
            value = struct.unpack_from(STRUCT_WORD, source, i)[0]
            assert isinstance(value, int)
            i += 2
            flags = struct.unpack_from(STRUCT_UBYTE, source, i)[0]
            assert isinstance(flags, int)
            i += 1

            symbol = Symbol(
                SymFlag(flags),
                name,
                value
            )
            if symbol.name in symtab:
                raise ValueError('redefined symbol', symbol)
            symtab[symbol.name] = symbol

    def _inseg(self, source: bytes,
               i: int) -> tuple[list[bytes | Reference], int]:
        """Read the segment in from the source bytes, returning the new index
        into the bytes, and the parsed segment.
        """
        seg: list[bytes | Reference] = []
        while True:
            count = struct.unpack_from(STRUCT_BYTE, source, i)[0]
            i += 1
            if count > 0:
                seg.append(source[i:i+count])
                i += count
            elif count < 0:
                ref, i = self._inref(-count, source, i)
                seg.append(ref)
            else:
                break
        return seg, i

    def _inref(self, flags: int, source: bytes,
               i: int) -> tuple[Reference, int]:
        """Read a references at the given i position in the source bytes.
        Return the reference and a new i value after it.
        """
        flags = RefFlag(flags)
        if flags & RefFlag.SYMBOL:
            symbol, i = self._inname(source, i)
        else:
            symbol = ''
        con = struct.unpack_from(STRUCT_WORD, source, i)[0]
        assert isinstance(con, int)
        i += 2

        return Reference(RefFlag(flags), symbol, con), i

    @staticmethod
    def seglen(seg: list[bytes | Reference]) -> int:
        """Return the length in bytes of the segment."""
        return sum((len(elem) for elem in seg))

    def __bytes__(self):
        out = struct.pack("<HHH",
                          self.seglen(self.text),
                          self.seglen(self.data),
                          self.bss_len)
        for seg in self.text, self.data:
            for elem in seg:
                out += bytes(elem)
            out += b'\x00'
        for symbol in self.symtab.values():
            out += bytes(symbol)
        out += b'\x00'

        return out


class Linker:
    """Links together object modules."""

    def __init__(self, *modules: Module) -> None:
        self.modules = list(modules)
        self.symtab: dict[str, Symbol] = {}
        self.modsyms: list[dict[str, Symbol]] = []
        self.common_bss: int = 0
        self.commons: list[Symbol] = []

    def link(self) -> bytes:
        """Link the symbol table."""
        self.buildsyms()

        out = bytes()
        for seg in ('text', 'data'):
            for i, module in enumerate(self.modules):
                out += self.resolve(len(out), self.modsyms[i],
                                    getattr(module, seg))
        return out + bytes(sum((mod.bss_len for mod in self.modules)))

    def resolve(self, offset: int, modsym: dict[str, Symbol],
                seg: list[bytes | Reference]) -> bytes:
        """Resolve all references in a given segment."""
        out = bytes()
        for elem in seg:
            if isinstance(elem, bytes):
                out += elem
            elif isinstance(elem, Reference):
                out += elem.resolve(offset+len(out), modsym, self.symtab)
            else:
                raise TypeError(elem)
        return out

    def buildsyms(self) -> None:
        """Construct the symbol table."""
        self.symtab.clear()
        self.modsyms.clear()
        for _ in range(len(self.modules)):
            self.modsyms.append({})
        offset = 0

        for seg in ('text', 'data', 'bss'):
            segnum = SEGS[seg]
            for i, module in enumerate(self.modules):
                modsym: list[Symbol] = []
                for symbol in module.symtab.values():
                    if (symbol.flags & SymFlag.SEG) != segnum:
                        continue
                    newsym = symbol.copy()
                    if not newsym.common:
                        newsym.value += offset
                    modsym.append(newsym)
                if seg == 'bss':
                    offset += module.bss_len
                else:
                    offset += module.seglen(getattr(module, seg))
                self.modsyms[i].update({sym.name: sym for sym in modsym})

        for modtab in self.modsyms:
            for sym in modtab.values():
                if sym.export and not sym.common:
                    self.symtab[sym.name] = sym

        self._commons(offset)

    def _commons(self, offset: int) -> None:
        """Resolve common references."""
        self.commons.clear()

        commons: dict[str, int] = {}

        for symtab in self.modsyms:
            for sym in symtab.values():
                if sym.common:
                    name = sym.name
                    size = sym.value
                    if name in commons and commons[name] > size:
                        size = commons[name]
                    commons[name] = size

        resolved: dict[str, Symbol] = {}
        for name in commons.copy():
            if name in self.symtab:
                sym = self.symtab[name]
                assert not sym.common
                resolved[sym.name] = sym
                del commons[name]

        for name, size in commons.items():
            sym = Symbol(SymFlag.EXPORT | SymFlag.BSS, name, offset)
            offset += size
            self.commons.append(sym)
            self.symtab[sym.name] = sym
        self.common_bss = offset

        for modsym in self.modsyms:
            for name, sym in modsym.copy().items():
                if sym.common:
                    del modsym[name]

        self.symtab.update(resolved)

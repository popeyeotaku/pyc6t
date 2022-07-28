"""C6T - C version 6 by Troy - Object File Linker."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntFlag
import struct

NAMELEN = 8

STRUCT_HEADER = "<HHH"
STRUCT_BYTE = "<b"
STRUCT_UBYTE = "<B"
STRUCT_WORD = "<H"
STRUCT_NAME = f"<{NAMELEN}s"


class RefFlag(IntFlag):
    """Flags for a segment reference record."""
    BYTE = 1
    HI = 2
    SYMBOL = 4
    HILO = 8


@dataclass
class Reference:
    """A relocation reference in a segment."""
    flags: RefFlag
    symbol: str
    con: int

    def __len__(self) -> int:
        if self.flags & RefFlag.BYTE:
            return 1
        return 2


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
                ref, i = self._inref(source, i)
                seg.append(ref)
            else:
                break
        return seg, i

    def _inref(self, source: bytes, i: int) -> tuple[Reference, int]:
        """Read a references at the given i position in the source bytes.
        Return the reference and a new i value after it.
        """
        flags = struct.unpack_from(STRUCT_UBYTE, source, i)[0]
        assert isinstance(flags, int)
        i += 1
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

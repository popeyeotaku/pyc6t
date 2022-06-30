"""C6T - C version 6 by Troy - Parser State Class"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, NoReturn
from lexer import Token, Tokenizer
from symtab import Symbol
import util


@dataclass
class Parser:
    """A state container for the current parser."""
    tokenizer: Tokenizer
    symtab: dict[str, Symbol] = field(default_factory=dict)
    tagtab: dict[str, Symbol] = field(default_factory=dict)
    asm: str = ''
    localscope: bool = False
    curstatic: int = 0
    brkstk: list[str] = field(default_factory=list)
    contstk: list[str] = field(default_factory=list)
    casestk: list[dict[int, str]] = field(default_factory=list)
    defaultstk: list[str | None] = field(default_factory=list)
    curseg: str = ''

    def cleartab(self, table: dict[str, Symbol]) -> None:
        """Clear locals from a given table."""
        for name, symbol in table.copy().items():
            if symbol.local:
                if symbol.undefined:
                    self.error(f'undefined symbol {name}')
                del table[name]

    def exitlocal(self) -> None:
        """Exit local scope."""
        assert self.localscope

        self.brkstk.clear()
        self.contstk.clear()
        self.casestk.clear()
        self.defaultstk.clear()

        self.cleartab(self.symtab)
        self.cleartab(self.tagtab)

        self.localscope = False

    def nextstatic(self) -> str:
        """Return the next static label."""
        self.curstatic += 1
        assert self.curstatic >= 0
        return f"L{self.curstatic}"

    def __post_init__(self):
        self.errs = 0

    @property
    def errcount(self) -> int:
        """Return the number of errors."""
        return self.errs + self.tokenizer.errcount

    @property
    def curline(self) -> int:
        """Return the current input line."""
        return self.tokenizer.curline

    def match(self, *labels: str) -> Token | None:
        """If any of the labels match the next input token, return the
        matched token. Else, return the token to the input stream and return
        None.
        """
        return self.tokenizer.match(*labels)

    def peek(self) -> Token:
        """Return the next token, also placing it back in the input stream to
        be read again.
        """
        return self.tokenizer.peek()

    def unsee(self, token: Token) -> None:
        """Return the given token to the input stream, to be seen again."""
        self.tokenizer.unsee(token)

    def __next__(self) -> Token:
        return next(self.tokenizer)

    def error(self, msg: str, line: int | None = None) -> None:
        """Print an error message."""
        util.error(self, msg, line)

    def crash(self, msg: str, line: int | None = None) -> NoReturn:
        """Print an error message and crash the compiler."""
        util.error(self, msg, line)
        raise util.CompilerCrash

    def need(self, *labels: str, msg: str = 'syntax error') -> None | Token:
        """If we don't match any of the labels, give the error. If we do,
        return the token matched.
        """
        token = self.match(*labels)
        if token:
            return token
        self.error(msg)
        return None

    def eoferror(self):
        """If we match an end of file, crash."""
        if self.match('eof'):
            self.crash('unexpected end of file')

    def list(self, endlabel: str,
             callback: Callable[[Parser, Token], bool],
             seplabel: str = ',',
             errmsg: str | None = 'syntax error') -> None:
        """Process a seperated list of elements. After seeing each
        element token, run the callback. If the callback returns False, end
        the list search immediately.
        """
        while not self.match(endlabel):
            self.eoferror()
            if not callback(self, next(self.tokenizer)):
                break
            if not self.peek().label == endlabel:
                if not self.need(seplabel, msg=errmsg):
                    self.termskip()
                    break

    def termskip(self) -> None:
        """Skip to a terminal input token, used with errskip."""
        while self.peek().label not in (';', '{', '}', 'eof'):
            next(self.tokenizer)

    def errskip(self, msg: str, line: int | None = None) -> None:
        """Print the error message and skip to the next terminal input
        token.
        """
        self.error(msg, line)
        self.termskip()

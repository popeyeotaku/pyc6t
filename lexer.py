"""C6T - C version 6 by Troy - Tokenizer"""

from dataclasses import dataclass, field
import re
from typing import Any, Iterable
import util

keywords = [
    'int', 'char', 'float', 'double', 'struct', 'auto', 'register', 'static',
    'goto', 'return', 'sizeof', 'break', 'continue', 'if', 'else', 'for',
    'do', 'while', 'switch', 'case', 'default', 'extern'
] # The spec also keys 'entry', which is unimplemented

re_name = re.compile(r'[a-zA-Z_]+[a-zA-Z_0-9]*')
re_fcon = re.compile(
    r'([0-9]*\.[0-9]+([eE][+-]?[0-9]+)?)|([0-9]+[eE][+-]?[0-9]+)')
re_con = re.compile(r'[0-9]+')
re_string = re.compile(r'"([^"]|(\\"))*"')
re_charcon = re.compile(r"'([^']|(\\'))*'")

operators = sorted([
    '{', '}', ';',
    ',',
    '=', '=+', '=-', '=*', '=/', '=%', '=>>', '=<<', '=&', '=^', '=|',
    '?', ':',
    '||',
    '&&',
    '|',
    '^',
    '&',
    '==', '!=',
    '<', '>', '<=', '>=',
    '>>', '<<',
    '+', '-',
    '*', '/', '%',
    '!', '~', '++', '--',
    '(', ')', '[', ']', '.', '->'
], key=len, reverse=True)


@dataclass(frozen=True)
class Token:
    """An input lexical token."""
    label: str
    linenum: int = field(compare=False)
    value: Any = field(default=None, compare=False)


class Tokenizer(Iterable[Token]):
    """Returns tokens from an input source."""

    def __init__(self, source: str, startline: int = 1) -> None:
        self._source = source
        self._curline = startline
        self._i = 0
        self._countlines = True
        self._peeked = []  # type:list[Token]
        self.errs = 0

    @property
    def errcount(self):
        """Return the number of errors."""
        return self.errs

    def unsee(self, token: Token):
        """Return the given token to the input stream to be seen again."""
        self._peeked.append(token)

    def peek(self) -> Token:
        """Return the next token, returning it to the input stream so it can
        be seen again.
        """
        token = next(self)
        self.unsee(token)
        return token

    def match(self, *labels: str) -> Token | None:
        """Try to match one of the given labels to the given token. If we
        match, return the matched token. Else, return the token ot the input
        stream and return None.
        """
        token = next(self)
        if token.label in labels:
            return token
        self.unsee(token)
        return None

    @property
    def curline(self) -> int:
        """Return the current input line number."""
        return self._curline

    @property
    def text(self) -> str:
        """Return the source text from the current internal index onwards."""
        assert self._i >= 0
        return self._source[self._i:]

    def __iter__(self) -> Iterable[Token]:
        return self

    def _token(self, label: str, value: Any = None) -> Token:
        """Construct a new token -- mainly used to set the line number
        automatically.
        """
        return Token(label, self.curline, value)

    def dochar(self) -> bytes:
        """Return the next input character, with escape support."""
        if len(self.text) < 1:
            return ''
        if self.text[0] == '\\':
            self._i += 1
            if len(self.text) < 1:
                return ''
            match self.text[0]:
                case 'b':
                    self._i += 1
                    return b'\b'
                case 'n':
                    self._i += 1
                    return b'\n'
                case 'r':
                    self._i += 1
                    return b'\r'
                case 't':
                    self._i += 1
                    return b'\t'
                case '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7':
                    match = re.match(r'[0-7][0-7]?[0-7]?', self.text)
                    if not match:
                        raise ValueError(
                            "FATAL UNABLE TO MATCH CHAR CON OCTAL")
                    self._i += len(match[0])
                    return bytes([int(match[0], base=8)])
                case _:
                    char = self.text[0].encode(encoding='ascii')
                    self._i += 1
                    return char
        else:
            char = self.text[0].encode(encoding='ascii')
            self._i += 1
            return char

    def whitespace(self) -> None:
        """Skip leading whitespace."""
        while len(self.text) > 0:
            match self.text[0]:
                case '@':
                    self._countlines = not self._countlines
                    self._i += 1
                case '\n':
                    if self._countlines:
                        self._curline += 1
                    self._i += 1
                case ' ' | '\t':
                    self._i += 1
                case _:
                    if self.text.startswith('/*'):
                        self._i += 2
                        while len(self.text) > 0 and \
                                not self.text.startswith('*/'):
                            if self._countlines and self.text[0] == '\n':
                                self._curline += 1
                            self._i += 1
                        self._i += 2
                    else:
                        return

    def __next__(self) -> Token:  # pylint:disable=too-many-return-statements
        if len(self._peeked) > 0:
            return self._peeked.pop()

        self.whitespace()
        if len(self.text) < 1:
            return self._token('eof')

        for operator in operators:
            if self.text.startswith(operator):
                self._i += len(operator)
                return self._token(operator)

        match = re_name.match(self.text)
        if match:
            self._i += len(match[0])
            if match[0] in keywords:
                return self._token(match[0])
            return self._token('name', match[0])

        match = re_fcon.match(self.text)
        if match:
            self._i += len(match[0])
            return self._token('fcon', float(match[0]))

        match = re_con.match(self.text)
        if match:
            self._i += len(match[0])
            digits = match[0]
            if digits[0] == '0':
                base = 8
            else:
                base = 10
            num = 0
            for digit in digits:
                num = util.word(num * base + int(digit))
            return self._token('con', num)

        if self.text[0] == "'":
            self._i += 1
            con = 0
            while len(self.text) > 0:
                if self.text[0] == "'":
                    self._i += 1
                    break
                con = (con << 8) | (self.dochar()[0] & 0xFF)
            return self._token('con', con)

        if self.text[0] == '"':
            text = bytes()
            self._i += 1
            while len(self.text) > 0:
                if self.text[0] == '"':
                    self._i += 1
                    text += bytes([0])
                    return self._token('string', text)
                text += self.dochar()

        util.error(self, f'bad input character {repr(self.text[0])}')
        self._i += 1
        return next(self)


if __name__ == "__main__":
    import doctest
    doctest.testmod()

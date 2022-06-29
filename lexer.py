"""C6T - C version 6 by Troy - Tokenizer"""

from dataclasses import dataclass, field
from typing import Any, Iterable


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
        assert self._i > 0
        return self._source[self._i:]

    def __iter__(self) -> Iterable[Token]:
        return self

    def _token(self, label: str, value: Any = None) -> Token:
        """Construct a new token -- mainly used to set the line number
        automatically.
        """
        if len(self._peeked) > 0:
            return self._peeked.pop()
        # TODO: tokenize
        return Token(label, self.curline, value)

    def __next__(self) -> Token:
        return self._token('eof')

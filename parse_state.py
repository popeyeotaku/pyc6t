"""C6T - C version 6 by Troy - Parser State Class"""

from dataclasses import dataclass, field
from lexer import Token, Tokenizer
from symtab import Symbol


@dataclass
class Parser:
    """A state container for the current parser."""
    tokenizer: Tokenizer
    symtab: dict[str, Symbol] = field(default_factory=dict)
    tagtab: dict[str, Symbol] = field(default_factory=dict)
    asm: str = ''

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

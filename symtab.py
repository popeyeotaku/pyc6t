"""C6T - C version 6 by Troy - Symbol Table Support"""

from dataclasses import dataclass
from typing import Literal

from type6 import TypeString

StorageClass = Literal['extern', 'static',
                       'auto', 'register', 'struct', 'member']


@dataclass
class Symbol:
    """A symbol table entry."""
    name: str
    storage: StorageClass
    typestr: TypeString
    offset: int | None = None

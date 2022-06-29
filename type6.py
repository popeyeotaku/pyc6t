"""C6T - C version 6 by Troy - Type System"""

from dataclasses import dataclass
from functools import cached_property
from typing import Literal


BaseType = Literal['int', 'char', 'float', 'double', 'struct']
ModType = Literal['point', 'func', 'array']


@dataclass(frozen=True)
class TypeElem:
    """A single C6T type element."""
    type: BaseType | ModType
    size: int = 0

    def tysize(self) -> int:
        """Return the size of the element, in bytes, or element count for an
        array.
        """
        match self.type:
            case 'int' | 'point' | 'func':
                return 2
            case 'char':
                return 1
            case 'float':
                return 4
            case 'double':
                return 8
            case _:
                return self.size

    @cached_property
    def pointer(self):
        """Returns a flag for if this is a pointer type."""
        return self.type in ('point', 'array')

    @cached_property
    def integral(self):
        """Returns a flag for if this is an integral type."""
        return self.type in ('int', 'char')

    @cached_property
    def floating(self):
        """Returns a flag for if this is a floating type."""
        return self.type in ('float', 'double')


Int6 = TypeElem('int')
Char6 = TypeElem('char')
Float6 = TypeElem('float')
Double6 = TypeElem('double')

Point6 = TypeElem('point')
Func6 = TypeElem('func')

TypeString = list[TypeElem]


def tysize(typestr: TypeString) -> int:
    """Returns the size of the type string in bytes."""
    assert len(typestr) > 0
    if typestr[0].type == 'array':
        return tysize(typestr[1:]) * typestr[0].tysize()
    return typestr[0].tysize()

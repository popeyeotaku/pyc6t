"""C6T - C version 6 by Troy - Defaulting Mapping Class"""


import collections.abc
from typing import Generic, Iterator, TypeVar

D = TypeVar('D')
K = TypeVar('K')
V = TypeVar('V')


class Defaulter(collections.abc.MutableMapping, Generic[K, V, D]):
    """A mutable mapping who defaults to a given value when the key does not
    exist.
    """

    def __init__(self, default: D, elems: dict[K, V]):
        self._dict = elems.copy()
        self._default = default

    def __getitem__(self, key: K) -> V | D:
        try:
            return self._dict[key]
        except KeyError:
            return self._default

    def __len__(self) -> int:
        return len(self._dict)

    def __iter__(self) -> Iterator[K]:
        return iter(self._dict)

    def __delitem__(self, key: K) -> None:
        del self._dict[key]

    def __setitem__(self, key: K, value: V) -> None:
        self._dict[key] = value


class Flags(Defaulter[str, bool, bool]):
    """A defaulter which stores named flags."""

    def __init__(self, *args: str, **kwargs: bool):
        for arg in args:
            if arg not in kwargs:
                kwargs[arg] = True
        super().__init__(False, kwargs)

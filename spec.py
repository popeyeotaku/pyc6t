"""C6T - C version 6 by Troy - Specifier Parsing and Support Code"""

from typing import Callable
from assembly import pseudo
from expr import conexpr
from lexer import Token
from parse_state import Parser
from symtab import StorageClass, Symbol
from type6 import BaseType, Func6, Int6, Point6, TypeElem, TypeString, tysize


def dostruct(parser: Parser) -> int:
    """Having already read the leading base type 'struct' keyword, parse a
    struct specifier, returning its size in bytes.
    """
    # TODO: do the struct


def grabtype(parser: Parser) -> TypeElem | None:
    """Parse a base type, if any."""
    token = parser.match('int', 'char', 'float', 'double')
    if token:
        return TypeElem(token.label)
    if parser.match('struct'):
        return TypeElem('struct', dostruct(parser))
    return None


def grabclass(parser: Parser) -> StorageClass | None:
    """Parse a storage class specifier, if any."""
    token = parser.match('auto', 'extern', 'static', 'register')
    if token:
        return token.label
    return None


def typeclass(parser: Parser) -> tuple[BaseType | None, StorageClass | None]:
    """Parse a type and storage class specifier, which may appear in either
    order.
    """
    base = grabtype(parser)
    if base:
        return base, grabclass(parser)
    storage = grabclass(parser)
    return storage, grabtype(parser)


def spec(parser: Parser, basetype: TypeElem) -> tuple[str | None, TypeString, list[str]]:
    """Process a single specifier, returning its name, type string, and
    parameter names. If the name is None, then we didn't see a specifier.
    """
    token = parser.match('*', '(', 'name')
    if not token:
        return None, [], []
    match token.label:
        case '*':
            name, typestr, params = spec(parser, basetype)
            typestr.insert(0, Point6)
            return name, typestr, params
        case '(':
            name, typestr, params = spec(parser, basetype)
            parser.need(')')
        case 'name':
            assert isinstance(token.value, str)
            name = token.value
            typestr = [basetype]
            params = []
    while True:
        if parser.match('('):
            typestr.insert(0, 'func')

            def addparam(parser: Parser, token: Token):
                """Add a parameter to the parameter list.
                """
                if token.label != 'name':
                    parser.error('missing parameter name')
                assert isinstance(token.value, str)
                params.append(token.value)

            parser.list(')', addparam)
        elif parser.match('['):
            if parser.match(']'):
                size = 1
            else:
                size = conexpr(parser)
                parser.need(']')
            typestr.insert(0, TypeElem('array', size))
        else:
            break

    return name, typestr, params


def specline(parser: Parser, needtypeclass: bool,
             callback: Callable[
                 [Parser, str, StorageClass, TypeString, list[str], int],
                 bool]) -> bool:
    """Handle a single line of specifiers."""
    basetype, storage = typeclass(parser)
    if basetype is None and storage is None and needtypeclass:
        return False
    if basetype is None:
        basetype = Int6
    if storage is None:
        if parser.localscope:
            storage = 'auto'
        else:
            storage = 'extern'

    count = 0

    def dospec(parser: Parser, token: Token) -> bool:
        """Lower level callback for parser.line"""
        nonlocal count
        parser.unsee(token)
        name, typestr, params = spec(parser, basetype)
        if name is None:
            parser.error('missing declarator')
            return True
        count += 1
        return callback(parser, name, storage, typestr, params, count)

    parser.list(';', dospec)
    return True


def funcdef(parser: Parser, name: str, typestr: TypeString,
            params: list[str]) -> None:
    """Handles an external function definition."""
    # TODO: function definition


def datainit(parser: Parser, name: str, typestr: TypeString) -> TypeString:
    """Handle a data initializer, returning a typestring that may be modified.
    """
    # TODO: initializers
    return typestr


def datadef(parser: Parser, name: str, typestr: TypeString) -> None:
    """Handles an external data definition, possibly followed by an
    initializer.
    """
    if parser.peek().label in (',', ';'):
        # No initializer
        pseudo(parser, f'common {name}, {tysize(typestr)}')
    else:
        # Initializer
        typestr = datainit(parser, name, typestr)
    symbol = Symbol(
        name,
        'extern',
        typestr.copy()
    )
    parser.symtab[name] = symbol


def extdef(parser: Parser) -> bool:
    """Process a line of external definitions."""
    # TODO: external definition
    def extcallback(parser: Parser, name: str, storage: StorageClass,
                    typestr: TypeString, params: list[str],
                    count: int) -> bool:
        """Constructs an external definition having seen its specifier."""
        if typestr[0] == Func6:
            if count > 1:
                parser.errskip('function definition not first element in '
                               'specifier list')
            else:
                funcdef(parser, name, typestr, params)
            return False
        datadef(parser, name, typestr)
        return True

    return specline(parser, False, extcallback)

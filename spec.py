"""C6T - C version 6 by Troy - Specifier Parsing and Support Code"""

from typing import Callable
from assembly import asm, deflab, fasm, goseg, pseudo
from expr import conexpr
from lexer import Token
from parse_state import Parser
from statement import statement
from symtab import StorageClass, Symbol
from type6 import BaseType, Double6, Func6, Int6, Point6, TypeElem, TypeString, tysize
import util


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
            typestr.insert(0, Func6)

            def addparam(parser: Parser, token: Token):
                """Add a parameter to the parameter list.
                """
                if token.label != 'name':
                    parser.error('missing parameter name')
                assert isinstance(token.value, str)
                params.append(token.value)
                return True

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

    goseg(parser, 'text')
    deflab(parser, '_' + name)
    pseudo(parser, f'export _{name}')

    functype = typestr

    parser.symtab[name] = Symbol(
        name, 'extern', functype
    )

    parser.localscope = True
    paramtypes = {}
    for paramname in params:
        paramtypes[paramname] = [Int6].copy()

    def paramcallback(parser: Parser, name: str, storage: StorageClass,
                      typestr: TypeString, params: list[str],
                      count: int) -> bool:
        """Add the final type of a parameter.
        """
        if name not in paramtypes:
            parser.error(f'parameter {name} not listed in function '
                         'parameters')
            return True
        match typestr[0].type:
            case 'char':
                typestr[0] = Int6
            case 'float':
                typestr[0] = Double6
            case 'array':
                typestr[0] = Point6
            case 'func' | 'struct':
                parser.error('function and struct types not passable')
                return True
        paramtypes[name] = typestr.copy()
        return True
    while specline(parser, True, paramcallback):
        pass
    offset = util.PARAM_OFFSET
    for paramname, typestr in paramtypes.items():
        if paramname in parser.symtab:
            parser.error(f'name {paramname} already defined')
            continue
        symbol = Symbol(
            paramname,
            'auto',
            typestr.copy(),
            offset,
            local=True
        )
        parser.symtab[paramname] = symbol
        offset = util.word(offset + tysize(typestr))

    parser.need('{')

    auto_offset = 0
    regs = 0

    def localcallback(parser: Parser, name: str, storage: StorageClass,
                      typestr: TypeString, params: list[str],
                      count: int) -> bool:
        nonlocal auto_offset, regs
        if storage == 'register' and regs >= util.MAXREGS:
            storage = 'auto'
        match storage:
            case 'auto':
                auto_offset = util.word(auto_offset - tysize(typestr))
                offset = auto_offset
            case 'static':
                offset = parser.nextstatic()
                goseg(parser, 'bss')
                deflab(parser, offset)
                pseudo(parser, f'ds {tysize(typestr)}')
            case 'register':
                offset = regs
                regs += 1
            case _:
                offset = None
        symbol = Symbol(
            name,
            storage,
            typestr.copy(),
            offset,
            local=True
        )
        if name in parser.symtab:
            parser.error(f'redefined local {name}')
        else:
            parser.symtab[name] = symbol
    while specline(parser, True, localcallback):
        pass

    if auto_offset != 0:
        asm(parser, f'dropstk {util.word(-auto_offset)}')

    asm(parser, f'useregs {regs}')

    while not parser.match('}'):
        parser.eoferror()
        statement(parser, functype[1].floating)

    asm(parser, 'push 0')
    fasm(parser, 'ret', functype[1].floating)

    parser.exitlocal()


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
        goseg(parser, 'bss')
        pseudo(parser, f'common _{name}, {tysize(typestr)}')
    else:
        # Initializer
        typestr = datainit(parser, name, typestr)
    symbol = Symbol(
        name,
        'extern',
        typestr.copy()
    )
    parser.symtab[name] = symbol
    pseudo(parser, f'export _{name}')


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

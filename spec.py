"""C6T - C version 6 by Troy - Specifier Parsing and Support Code"""

from math import ceil
from typing import Callable
from assembly import asm, deflab, fasm, goseg, pseudo
from expr import Leaf, Node, conexpr, expression
from lexer import Token
from parse_state import Parser
from statement import statement
from symtab import StorageClass, Symbol
from type6 import BaseType, Double6, Func6, Int6, Point6, TypeElem, TypeString, tysize
import util


# pylint:disable=unused-argument
def dostruct(parser: Parser) -> int:
    """Having already read the leading base type 'struct' keyword, parse a
    struct specifier, returning its size in bytes.
    """
    tempname = None
    if token := parser.match('name'):
        assert isinstance(token.value, str)
        name = token.value
        if name not in parser.tagtab:
            tempname = name
            tempsize = 0
            parser.tagtab[name] = Symbol(
                name, 'struct', [TypeElem('struct', tempsize)],
                tempsize, parser.localscope
            )
    else:
        name = None

    offset = 0

    def addmember(parser: Parser, name: str, storage: StorageClass,
                  typestr: TypeString, args: list[str], count: int) -> bool:
        """Callback for one member spec."""
        nonlocal offset

        if name in parser.tagtab:
            check = parser.tagtab[name]
            if check.storage == 'member' and check.typestr == typestr and \
                    check.offset == offset:
                offset += tysize(typestr)
                return True
            parser.error(f'redefined member {name}')
            return True

        parser.tagtab[name] = Symbol(
            name, 'member', typestr, offset, parser.localscope
        )
        offset = util.word(tysize(typestr) + offset)
        return True

    if parser.match('{'):
        anymembers = True
        while not parser.match('}'):
            parser.eoferror()
            if not specline(parser, True, addmember):
                parser.termskip()
                break
    else:
        anymembers = False

    if tempname is not None:
        del parser.tagtab[tempname]

    if name is not None:
        if name in parser.tagtab:
            if parser.tagtab[name].storage != 'struct':
                parser.error(f'non-struct {name}')
            elif anymembers:
                parser.error(f'redefined struct {name}')
            else:
                offset = parser.tagtab[name].offset
                assert isinstance(offset, int)
        else:
            if not anymembers:
                parser.error(f'undefined struct {name}')
            else:
                parser.tagtab[name] = Symbol(
                    name,
                    'struct',
                    [TypeElem('struct', offset)],
                    offset,
                    parser.localscope
                )

    if name is None and not anymembers:
        parser.error('missing struct definition')

    return offset


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
    return grabtype(parser), storage


def _spec(parser: Parser) -> tuple[str | None, TypeString, list[str]]:
    """Process a single specifier, returning its name, type string, and
    parameter names. If the name is None, then we didn't see a specifier.
    """
    token = parser.match('*', '(', 'name')
    if not token:
        return None, [], []
    match token.label:
        case '*':
            name, typestr, params = _spec(parser)
            typestr.append(Point6)
            return name, typestr, params
        case '(':
            name, typestr, params = _spec(parser)
            parser.need(')')
        case 'name':
            assert isinstance(token.value, str)
            name = token.value
            typestr = []
            params = []
    while True:
        if parser.match('('):
            typestr.append(Func6)

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
            typestr.append(TypeElem('array', size))
        else:
            break

    return name, typestr, params


def spec(parser: Parser, basetype: TypeElem) -> tuple[str | None, TypeString, list[str]]:
    """Process a single specifier, returning its name, type string, and
    parameter names. If the name is None, then we didn't see a specifier.
    """
    name, typestr, params = _spec(parser)
    return name, typestr + [basetype], params


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

    # pylint:disable=unused-argument
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
    for paramname, ptype in paramtypes.items():
        if paramname in parser.symtab:
            parser.error(f'name {paramname} already defined')
            continue
        symbol = Symbol(
            paramname,
            'auto',
            ptype.copy(),
            offset,
            local=True
        )
        parser.symtab[paramname] = symbol
        offset = util.word(offset + tysize(ptype))

    parser.need('{')

    auto_offset = 0
    regs = 0

    def localcallback(parser: Parser, name: str, storage: StorageClass,
                      typestr: TypeString, params: list[str],
                      count: int) -> bool:
        nonlocal auto_offset, regs
        if storage == 'register' and regs >= util.MAXREGS:
            storage = 'auto'
        if typestr[0].type == 'func':
            storage = 'extern'
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
        return True
    while specline(parser, True, localcallback):
        pass

    goseg(parser, 'text')

    asm(parser, f'useregs {regs}')

    pseudo(parser, f'func _{name}')

    if auto_offset != 0:
        asm(parser, f'lenautos {util.word(-auto_offset)}')

    while not parser.match('}'):
        parser.eoferror()
        statement(parser, functype[1].floating)

    fasm(parser, 'retnull', functype[1].floating)

    parser.exitlocal()


def targtype(typestr: TypeString) -> tuple[str, int, int]:
    """Determine the storage type from the given type string - used in
    initializers. Returns the modifier character, the size of its storage,
    and the real size of the type.
    """
    assert len(typestr) >= 1
    size = tysize(typestr)
    match typestr[0].type:
        case 'float':
            return 'f', size, size
        case 'double':
            return 'd', size, size
        case 'char':
            return 'c', size, size
        case 'struct':
            return 'w', tysize([Int6]), tysize(typestr)
        case 'point' | 'int' | 'struct' | 'func':
            return 'w', tysize([Int6]), size
        case 'array':
            assert len(typestr) > 1
            return targtype(typestr[1:])
    raise ValueError


def initconv(node: Node) -> tuple[Node, int]:
    """Convert the expression node into the proper setup for initexpr's
    return. Seperate because it's recursive.
    """
    match node.label:
        case 'fcon' | 'con':
            return node, 0
        case 'addr':
            child = node[0]
            if child.label in ('string', 'name'):
                return child, 0
        case 'add' | 'sub':
            if node[0].label == 'con':
                assert isinstance(node[0], Leaf)
                curoffset = node[0].value
                check = node[1]
            elif node[1].label == 'con':
                assert isinstance(node[1], Leaf)
                curoffset = node[1].value
                check = node[0]
            else:
                raise ValueError
            if node.label == 'sub':
                curoffset = -curoffset
            # pylint:disable=unpacking-non-sequence
            node, offset = initconv(check)
            if node.label not in ('name', 'string'):
                raise ValueError
            return node, offset + curoffset
    raise ValueError


def initexpr(parser: Parser) -> tuple[Node, int]:
    """Handle an initializer expression returning its value, and an optional
    integer offset.
    """
    node = expression(parser, seecommas=False)
    try:
        # pylint:disable=unpacking-non-sequence
        node, offset = initconv(node)
    except ValueError:
        parser.error('bad initializer')
        return Leaf('con', parser.curline, [Int6], [], 1), 0
    return node, offset


def outinit(parser: Parser, cmd: str, node: Node, offset: int,
            asmstring: bool = True) -> None:
    """Output an initializer expression."""
    match node.label:
        case 'con' | 'fcon':
            assert isinstance(node, Leaf)
            goseg(parser, 'data')
            pseudo(parser, f'{cmd} {node.value}')
        case 'name' | 'string':
            assert isinstance(node, Leaf)
            if offset:
                offstr = f"{'-' if offset < 0 else '+'}{abs(offset)}"
            else:
                offstr = ''
            if node.label == 'string':
                assert isinstance(node.value, bytes)
                strbytes = ','.join((str(b) for b in node.value))
                if asmstring:
                    goseg(parser, 'string')
                    label = parser.nextstatic()
                    deflab(parser, label)
                    val = label
                    pseudo(parser, f'dc {strbytes}')
                else:
                    assert cmd[-1] == 'c'
                    val = strbytes
            else:
                assert isinstance(node.value, Symbol)
                assert node.value.storage == 'extern'
                val = '_' + node.value.name
            goseg(parser, 'data')
            pseudo(parser, f'{cmd} {val}{offstr}')
        case _:
            raise ValueError


def datainit(parser: Parser, typestr: TypeString) -> TypeString:
    """Handle a data initializer, returning a typestring that may be modified.
    """
    # At this point, the next input token will be the first one of the initializer.

    # pylint: disable=unpacking-non-sequence
    cmd, storesize, realsize = targtype(
        typestr)
    cmd = f'd{cmd}'

    # Two cases: list of initializers in braces, or a single one.
    totalsize = tysize(typestr)
    elembytes = 0

    if parser.match('{'):
        def parselist(parser: Parser, token: Token) -> bool:
            nonlocal elembytes

            parser.unsee(token)
            node, offset = initexpr(parser)
            outinit(parser, cmd, node, offset)
            elembytes += storesize
            return True
        parser.list('}', parselist)
    else:
        node, offset = initexpr(parser)
        if node.label == 'string' and typestr[0].type == 'array' and \
                typestr[1].type == 'char':
            asmstr = False
            assert isinstance(node, Leaf)
            assert isinstance(node.value, bytes)
            incbytes = len(node.value)
        else:
            incbytes = storesize
            asmstr = True
        outinit(parser, cmd, node, offset, asmstr)
        elembytes += incbytes

    numelems = ceil(elembytes / realsize)
    elemsize = realsize * numelems
    if elemsize > totalsize:
        typestr = typestr.copy()
        assert len(typestr) >= 1
        if typestr[0].type == 'array':
            # Adjust array size
            assert len(typestr) >= 2
            typestr[0] = TypeElem('array', numelems)
            totalsize = elemsize
    if totalsize > elembytes:
        asm(parser, f'.ds {totalsize - elembytes}')

    return typestr


def datadef(parser: Parser, name: str, typestr: TypeString) -> None:
    """Handles an external data definition, possibly followed by an
    initializer.
    """
    if parser.peek().label in (',', ';'):
        # No initializer
        goseg(parser, 'bss')
        if typestr[0].type != 'func':
            pseudo(parser, f'common _{name}, {tysize(typestr)}')
    else:
        # Initializer
        goseg(parser, 'data')
        deflab(parser, f'_{name}')
        typestr = datainit(parser, typestr)
    symbol = Symbol(
        name,
        'extern',
        typestr.copy()
    )
    parser.symtab[name] = symbol
    pseudo(parser, f'export _{name}')


def extdef(parser: Parser) -> bool:
    """Process a line of external definitions."""
    def extcallback(parser: Parser, name: str, storage: StorageClass,
                    typestr: TypeString, params: list[str],
                    count: int) -> bool:
        """Constructs an external definition having seen its specifier."""
        if typestr[0] == Func6:
            if parser.peek().label in (',', ';'):
                pass  # uninitialized function
            else:
                if count > 1:
                    parser.errskip('function definition not first element in '
                                   'specifier list')
                else:
                    funcdef(parser, name, typestr, params)
                return False
        datadef(parser, name, typestr)
        return True

    return specline(parser, False, extcallback)

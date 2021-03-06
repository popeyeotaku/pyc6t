"""C6T - C version 6 by Troy - Statement Handling"""

from assembly import asm, asmexpr, deflab, fasm, goseg, pseudo
from expr import Node, conexpr, expression
from parse_state import Parser
from symtab import Symbol
from type6 import Int6, TypeElem


def statement(parser: Parser, retflt: bool):
    """Process a single statement recursively.
    """
    goseg(parser, 'text')
    token = next(parser)
    match token.label:
        case 'name':
            if parser.match(':'):
                addgoto(parser, token.value)
                statement(parser, retflt)
            else:
                parser.unsee(token)
                doexpr(parser)
        case 'if':
            labfalse = parser.nextstatic()
            parenexpr(parser, labfalse)
            statement(parser, retflt)
            if parser.match('else'):
                labtrue = parser.nextstatic()
                asm(parser, f'jmp {labtrue}')
                deflab(parser, labfalse)
                statement(parser, retflt)
                deflab(parser, labtrue)
            else:  # Ironic, isn't it?
                deflab(parser, labfalse)
        case 'while':
            parser.contstk.append(parser.nextstatic())
            parser.brkstk.append(parser.nextstatic())
            deflab(parser, parser.contstk[-1])
            parenexpr(parser, parser.brkstk[-1])
            statement(parser, retflt)
            asm(parser, f'jmp {parser.contstk[-1]}')
            deflab(parser, parser.brkstk[-1])
            parser.contstk.pop()
            parser.brkstk.pop()
        case 'do':
            lab = parser.nextstatic()
            parser.contstk.append(parser.nextstatic())
            parser.brkstk.append(parser.nextstatic())

            deflab(parser, lab)
            statement(parser, retflt)
            parser.need('while')
            deflab(parser, parser.contstk[-1])
            parenexpr(parser, parser.brkstk[-1])
            parser.need(';')
            asm(parser, f'jmp {lab}')
            deflab(parser, parser.brkstk[-1])

            parser.brkstk.pop()
            parser.contstk.pop()
        case 'for':
            lab1 = parser.nextstatic()
            parser.brkstk.append(parser.nextstatic())
            parser.contstk.append(parser.nextstatic())

            parser.need('(')
            if not parser.match(';'):
                asmexpr(parser, expression(parser), 'eval')
                parser.need(';')
            deflab(parser, lab1)
            if not parser.match(';'):
                asmexpr(parser, expression(parser))
                asm(parser, f'brz {parser.brkstk[-1]}')
                parser.need(';')
            if parser.match(')'):
                update = None
                parser.contstk[-1] = lab1
            else:
                update = expression(parser)
                parser.need(')')

            statement(parser, retflt)
            if update:
                deflab(parser, parser.contstk[-1])
                asmexpr(parser, update, 'eval')
            asm(parser, f'jmp {lab1}')
            deflab(parser, parser.brkstk[-1])

            parser.contstk.pop()
            parser.brkstk.pop()
        case 'switch':
            parser.brkstk.append(parser.nextstatic())

            parser.casestk.append({})
            parser.defaultstk.append(None)

            swdest = parser.nextstatic()

            parser.need('(')
            node = expression(parser)
            parser.need(')')

            asm(parser, f'jmp {swdest}')

            statement(parser, retflt)

            deflab(parser, swdest)
            doswitch(parser, node, parser.casestk.pop(),
                     parser.defaultstk.pop())

            deflab(parser, parser.brkstk[-1])
            parser.brkstk.pop()
        case 'case':
            con = conexpr(parser)
            parser.need(':')
            if len(parser.casestk) < 1:
                parser.error('case outside of switch')
            else:
                label = parser.nextstatic()
                if con in parser.casestk[-1]:
                    parser.error(f'redefined case {con}')
                parser.casestk[-1][con] = label
                deflab(parser, label)
            statement(parser, retflt)
        case 'default':
            parser.need(':')
            if len(parser.defaultstk) < 1:
                parser.error('default outside of switch')
            elif parser.defaultstk[-1]:
                parser.error('multiple defaults')
            else:
                lab = parser.nextstatic()
                parser.defaultstk[-1] = lab
                deflab(parser, lab)
            statement(parser, retflt)
        case 'break':
            parser.need(';')
            try:
                lab = parser.brkstk[-1]
            except IndexError:
                parser.error('nothing to break to')
                return
            asm(parser, f'jmp {lab}')
        case 'continue':
            parser.need(';')
            try:
                lab = parser.contstk[-1]
            except IndexError:
                parser.error("nothing to continue to")
                return
            asm(parser, f'jmp {lab}')
        case 'return':
            if parser.match(';'):
                asm(parser, 'retnull')
            else:
                parser.need('(')
                node = expression(parser)
                parser.need(')')
                parser.need(';')
                asmexpr(parser, node)
                if retflt and not node.typestr[0].floating:
                    asm(parser, 'toflt')
                if (not retflt) and node.typestr[0].floating:
                    asm(parser, 'toint')
                fasm(parser, 'ret', retflt)
        case 'goto':
            asmexpr(parser, expression(parser))
            parser.need(';')
            asm(parser, 'ijmp')
        case ';':
            return
        case '{':
            while not parser.match('}'):
                parser.eoferror()
                statement(parser, retflt)
        case _:
            parser.unsee(token)
            doexpr(parser)


def parenexpr(parser: Parser, label: str) -> None:
    """Assemble to evaulate an expression in parenthesis and branch if it is
    false to the given label.
    """
    parser.need('(')
    node = expression(parser)
    parser.need(')')
    asmexpr(parser, node)
    asm(parser, f'brz {label}')


def doexpr(parser: Parser):
    """Handle an expression statement.
    """
    asmexpr(parser, expression(parser), 'eval')
    parser.need(';')


def addgoto(parser: Parser, name: str):
    """Define a new goto label.
    """
    if name not in parser.symtab:
        parser.symtab[name] = Symbol(
            name,
            'static',
            [TypeElem('array', 1), Int6],
            parser.nextstatic(),
            local=True
        )
    symbol = parser.symtab[name]
    if symbol.storage != 'static' or symbol.typestr != [TypeElem('array', 1),
                                                        Int6] or not \
            symbol.local:
        parser.error(f'bad goto label {name}')
    else:
        if symbol.undefined:
            symbol.undefined = False
        assert isinstance(symbol.offset, str)
        deflab(parser, symbol.offset)


def doswitch(parser: Parser, node: Node, cases: dict[int, str],
             default: None | str):
    """Output assembly for a switch statement.
    """
    goseg(parser, 'data')
    tablab = parser.nextstatic()
    deflab(parser, tablab)
    for con, label in cases.items():
        pseudo(parser, f'dw {con}, {label}')
    goseg(parser, 'text')
    asmexpr(parser, node)
    if default:
        asm(parser, f'extern {default}')
    else:
        try:
            asm(parser, f'extern {parser.brkstk[-1]}')
        except IndexError:
            parser.error('missing break for switch')
    asm(parser, f'con {len(cases)}')
    asm(parser, f'extern {tablab}')
    asm(parser, 'doswitch')

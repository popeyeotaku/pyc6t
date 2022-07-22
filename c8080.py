"""C6T - C version 6 by Troy - Intel 8080 codegen
"""
from enum import IntEnum
from pathlib import Path
from backend import CodeGen, Command, Node
import backend

SEGMENTS = ('.text', '.data', '.bss', '.string')

REGVARS = 3


class Reg(IntEnum):
    """Represents an 8080 16bit register."""
    HL = 0
    DE = 1


def equal(*elems) -> bool:
    """Return a flag for if ALL the elements are equal."""
    elem0 = elems[0]
    return all(elem == elem0 for elem in elems[1:])


class Code8080(CodeGen):
    """Intel 8080 codegen for C6T."""

    def __init__(self) -> None:
        super().__init__()
        self.segs = {}
        for seg in SEGMENTS:
            self.segs[seg] = ''
        self.curseg = '.text'
        self.curlab = 0

    def nextlab(self) -> str:
        """Return a unique temporary label which does not interfere w/ the C6T
        ones.
        """
        self.curlab += 1
        return f"LL{self.curlab}"

    def getasm(self) -> str:
        out = ''
        for seg in SEGMENTS:
            out += seg + '\n' + self.segs[seg]
        return out

    def reset(self) -> None:
        for seg in self.segs:
            self.segs[seg] = ''
        self.curseg = '.text'
        self.curlab = 0

    def asm(self, *lines: str) -> None:
        """Assemble the given line to the current segment."""
        for line in lines:
            self.segs[self.curseg] += f'\t{line}\n'

    def deflabel(self, lab: str) -> None:
        self.segs[self.curseg] += f'{lab}:'

    def logical(self, branch_op: str, reg: Reg, *, eqfalse: bool = False,
                eqtrue: bool = False) -> None:
        """After assembling a test, assemble code to put 1 or 0 into the
        target register according to its value, using the given 8080
        branch instruction.

        If equal false is set, then we also insert a 'je' to logical 0.
        """
        lab1, lab2 = self.nextlab(), self.nextlab()
        if eqfalse:
            self.asm(f'jne {lab1}')
        elif eqtrue:
            self.asm(f'je {lab1}')
        self.asm(f'{branch_op} {lab1}')
        self.immed(reg, 0)
        self.asm(f'jmp {lab2}')
        self.deflabel(lab1)
        self.immed(reg, 1)
        self.deflabel(lab2)

    def convert(self, node: Node) -> Node:
        """Recursively convert the node as needed.
        """
        if 'converted' in node.info:
            return node
        children = [self.convert(child) for child in node.children]
        node = Node(node.label, children, node.value)
        match node.label:
            case 'lognot':
                match children[0].label:
                    case 'lognot':
                        node = children[0]
                    case 'log':
                        node.children = children[0].children
                    case 'brz':
                        node = self.convert(Node('bnz', children[0].children))
                    case 'bnz':
                        node = self.convert(Node('brz', children[0].children))
            case 'log':
                if children[0].label == 'lognot':
                    node = children[0]
            case 'logor':
                lab = self.nextlab()
                node = Node('bnz', [node.children[0], node.children[1], Node
                                    ('label', value=lab)], value=lab)
                node = Node('log', [node])
                node = self.convert(node)
            case 'logand':
                assert len(children) == 2
                lab = self.nextlab()
                node = Node('brz', children + [Node('label', value=lab)],
                            value=lab)
                node = self.convert(Node('log', [node]))
            case 'brz':
                match children[0].label:
                    case 'log':
                        node.children = children[0].children
                    case 'lognot':
                        node = self.convert(Node('bnz', children[0].children))
            case 'bnz':
                match children[0].label:
                    case 'log':
                        node.children = children[0].children
                    case 'lognot':
                        node = self.convert(Node('brz', children[0].children))
            case 'add':
                if children[0].label == 'con':
                    child = children[0]
                    other = children[1]
                elif children[1].label == 'con':
                    child = children[1]
                    other = children[0]
                else:
                    child = None
                    other = None
                if child and child.value == 1:
                    node = Node('inc', [other], info={'converted': True})
            case 'sub':
                if children[1].label == 'con' and children[1].value == 1:
                    node = Node('dec', [children[0]])
                elif children[1].label == 'con':
                    child = Node('con', value=-children[1].value)
                    node = self.convert(Node('add', [children[0], child]))
                elif children[0].label == 'con':
                    child = Node('con', value=-children[0].value)
                    node = self.convert(Node('add', [children[1], child]))
            case 'load' | 'cload':
                if children[0].label == 'extern':
                    node = Node('ext'+node.label, value=children[0].value)
            case 'store' | 'cstore':
                children.reverse()
                if children[1].label == 'extern':
                    node = Node('ext'+node.label,
                                [children[0]], children[1].value)
            case 'great' | 'equ' | 'nequ' | 'uless':
                node = Node(node.label, [self.convert(Node('sub', children))])
            case 'arg':
                assert len(children) == 1
                node = children[0]
            case 'register':
                node = Node('extern', children, f'reg{node.value}')
        node.children = [self.convert(child) for child in node.children]
        node.info['converted'] = True
        return node

    def immed(self, reg: Reg, value) -> None:
        """Get the immediate value into the register."""
        match reg:
            case Reg.HL:  # HL
                self.asm(f'lxi h,{value}')
            case Reg.DE:  # DE
                self.asm(f'mvi e,<{value}')
                self.asm(f'mvi d,>{value}')

    def regcount(self, node: Node) -> int:
        """Calculate the number of registers it would take to evaluate
        the node and its descendants.

        This is cached in the node's info.
        """
        if 'regcount' in node.info:
            return node.info['regcount']
        children = [self.regcount(child) for child in node.children]
        match node.label:
            # Special cases
            case 'brz' | 'bnz' | 'label':
                return max(children) if children else 0
            case 'call':
                assert len(children) >= 1
                args = children[:-1]
                func = children[-1]
                funcnode = node.children[-1]
                if args:
                    count = max(args)
                else:
                    count = 0
                if funcnode.label != 'extern':
                    count += func
            case _:
                match len(node.children):
                    case 0:
                        count = 1
                    case 1:
                        count = children[0]
                    case _:
                        if equal(*children):
                            count = children[0] + 1
                        else:
                            count = max(children)
        node.info['regcount'] = count
        return count

    def eval(self, node: Node) -> None:
        """Assemble the given node, result being in HL."""
        converted = self.convert(node)
        self.asmnode(converted)

    def asmchildren(self, node: Node, targreg: Reg) -> None:
        """Assemble the children of the node into registers starting w/
        targreg.
        """
        if not node.children:
            return
        assert len(node.children) <= len(Reg)
        count = self.regcount(node)
        if len(node.children) > 1 and count + targreg >= len(Reg):
            assert targreg == Reg.HL
            ordered = node.children.copy()
            ordered.sort(key=self.regcount, reverse=True)
            for child in ordered:
                self.asmnode(child, targreg)
                self.asm(f'push {targreg.name}')
            for child in reversed(ordered):
                reg = node.children.index(child)
                self.asm(f'pop {reg}')
        else:
            for i, child in enumerate(node.children):
                self.asmnode(child, Reg(i+targreg))

    def asmnode(self, node: Node, targreg: Reg = Reg.HL) -> None:
        """Assemble the node into the given register.

        Note that the store operands are reversed by convert so the addr
        should end up in HL -- but you'll need to xchg to get the resulting
        value back in HL.
        """
        reghi = targreg.name[0]
        reglo = targreg.name[1]
        match node.label:
            # Special cases
            case 'brz' | 'bnz':
                # The value is the label to branch to if the first child is
                # equal to 0.
                # Optional additional children should be assembled next in
                # order.
                assert len(node.children) >= 1
                self.asmnode(node.children[0], targreg)
                match targreg:
                    case Reg.HL:
                        self.asm('mov a,l', 'ora h')
                    case Reg.DE:
                        self.asm('mov a,e', 'ora d')
                opcode = 'je' if node.label == 'brz' else 'jne'
                self.asm(f'{opcode} {node.value}')
                for child in node.children[1:]:
                    self.asmnode(child, targreg)
            case 'label':
                # Define a label here then assemble the children if any.
                self.deflabel(node.value)
                for child in node.children:
                    self.asmnode(child, targreg)
            case 'drop' | 'comma':
                # Assemble all children into the same target register, so that
                # only the last one's value is used.
                for child in node.children:
                    self.asmnode(child, targreg)
            case 'call':
                assert len(node.children) >= 1

                if targreg > Reg.HL:
                    self.asm('push h')
                    saved = True
                else:
                    saved = False

                args = node.children[:-1]
                func = node.children[-1]
                for arg in args:
                    self.asmnode(arg, Reg.HL)
                    self.asm('push h')
                if func.label == 'extern':
                    self.asm(f'call {func.value}')
                else:
                    self.asmnode(func, Reg.HL)
                    self.asm('call ccall')

                # Remove args from stack
                if args:
                    # We shouldn't need DE's value since if that's the
                    # targ reg, we want to replace it
                    self.asm(
                        'xchg', f'lhld {len(args)*2}', 'dad sp', 'sphl',
                        'xchg')

                if saved:
                    self.asm('xchg')  # Result in HL now in DE where we wanted
                    self.asm('pop h')  # Restore old HL

            case _:
                self.asmchildren(node, targreg)
                match node.label:
                    case 'extcload':
                        self.asm(f'lda {node.value}', f'mov {reglo},a')
                        self.asm(f'mvi {reghi},0')
                    case 'extcstore':
                        self.asm(f'mov a,{reglo}', f'sta {node.value}')
                    case 'cload':
                        match targreg:
                            case Reg.HL:
                                self.asm('mov a,m')
                            case Reg.DE:
                                self.asm('ldax d')
                        self.asm(f'mov {reglo},a', f'mvi {reghi},0')
                    case 'cstore':
                        self.asm('mov e,m', 'xchg')
                    case 'inc':
                        self.asm(f'inx {targreg.name}')
                    case 'dec':
                        self.asm(f'dcx {targreg.name}')
                    case 'extload':
                        match targreg:
                            case Reg.HL:
                                self.asm(f'lhld {node.value}')
                            case Reg.DE:
                                self.asm(f'lda {node.value}', 'mov e,a')
                                self.asm(f'lda {node.value}+1', 'mov d,a')
                    case 'extstore':
                        match targreg:
                            case Reg.HL:
                                self.asm(f'shld {node.value}')
                            case Reg.DE:
                                self.asm('mov a,e', f'sta {node.value}')
                                self.asm('mov a,d', f'sta {node.value}+1')
                    case 'great':
                        self.logical('jcs', targreg, eqfalse=True)
                    case 'gequ':
                        self.logical('jcs', targreg, eqtrue=True)
                    case 'nequ':
                        self.logical('jne', targreg)
                    case 'equ':
                        self.logical('je', targreg)
                    case 'uless':
                        self.logical('jcs', targreg, eqfalse=True)
                    case 'less':
                        self.logical('jcc', targreg, eqfalse=True)
                    case 'lequ':
                        self.logical('jcc', targreg, eqtrue=True)
                    case 'auto':
                        if targreg == Reg.DE:
                            self.asm('xchg')
                        self.immed(Reg.HL, node.value)
                        self.asm('dad b')
                        if targreg == Reg.DE:
                            self.asm('xchg')
                    case 'load':
                        if targreg == Reg.DE:
                            self.asm('xchg')
                        self.asm('mov m,a', 'inx h', 'mov h,m',
                                 'mov l,a')
                        if targreg == Reg.DE:
                            self.asm('xchg')
                    case 'store':
                        assert targreg == Reg.HL  # SHOULD be the only case
                        self.asm('mov m,e', 'inx h', 'mov m,d', 'xchg')
                    case 'extern' | 'con':
                        self.immed(targreg, node.value)
                    case 'add':
                        assert targreg == Reg.HL
                        self.asm('dad d')
                    case 'sub':
                        assert targreg == Reg.HL
                        self.asm('mov a,l', 'sub e', 'mov l,a')
                        self.asm('mov a,h', 'sbb d', 'mov h,a')
                    case 'cstore':
                        assert targreg == Reg.HL
                        self.asm('xchg', 'mov m,e', 'xchg')
                    case 'mult':
                        self.asm('call cmult')
                    case 'log':
                        self.logical('jne', targreg)
                    case 'lognot':
                        self.logical('je', targreg)
                    case _:
                        raise NotImplementedError(node.label)

    def asmret(self) -> None:
        """Output standard assembly for a return."""
        self.asm('jmp cret')

    def command(self, command: Command, nodestk: list[Node]) -> None:
        match command.cmd:
            case '.text' | '.data' | '.bss' | '.string':
                assert command.cmd in self.segs
                self.curseg = command.cmd
            case '.common':
                oldseg = self.curseg
                self.curseg = '.bss'
                self.deflabel(command[0])
                self.asm(f'.ds {command[1]}')
                self.curseg = oldseg
            case '.export':
                pass
            case 'useregs':
                pass
            case 'eval':
                self.eval(nodestk.pop())
            case 'brz':
                node = Node('brz', [nodestk.pop()], command[0])
                self.eval(node)
            case 'jmp':
                self.asm(f'jmp {command[0]}')
            case '.func':
                self.asm('push b')
                for i in range(REGVARS):
                    self.asm(f'lhld reg{i}', 'push h')
                self.asm('lxi h,0', 'dad sp', 'mov c,l', 'mov b,h')
            case 'retnull':
                self.asmret()
            case 'ret':
                self.eval(nodestk.pop())
                self.asmret()
            case '.ds':
                self.asm(f'.ds {command.args[0]}')
            case _:
                raise ValueError('unsupport command', command)


def test():
    """Simple test program."""
    path = Path('wrap.ir')
    codegen = Code8080()
    try:
        backend.backend(path.read_text('utf8'), codegen)
    finally:
        print(codegen.getasm())


if __name__ == "__main__":
    test()

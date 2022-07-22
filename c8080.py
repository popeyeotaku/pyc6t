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

    def getasm(self) -> str:
        out = ''
        for seg in SEGMENTS:
            out += seg + '\n' + self.segs[seg]
        return out

    def reset(self) -> None:
        for seg in self.segs:
            self.segs[seg] = ''
        self.curseg = '.text'

    def asm(self, *lines: str) -> None:
        """Assemble the given line to the current segment."""
        for line in lines:
            self.segs[self.curseg] += f'\t{line}\n'

    def deflabel(self, lab: str) -> None:
        self.segs[self.curseg] += lab

    def convert(self, node: Node) -> Node:
        """Recursively convert the node as needed.
        """
        children = [self.convert(child) for child in node.children]
        match node.label:
            case 'arg':
                assert len(children) == 0
                return children[0]
            case 'register':
                return Node('extern', children, f'reg{node.value}')
            case _:
                return Node(node.label, children, node.value, node.info)

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
            case 'call':
                assert len(children) >= 1
                if children[1:]:
                    count = max(children[1:])
                else:
                    count = 0
                if children[0].label != 'extern':
                    count += children[0]
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
        node = self.convert(node)
        self.asmnode(node)

    def asmchildren(self, node: Node, targreg: Reg) -> None:
        """Assemble the children of the node into registers starting w/
        targreg.
        """
        if not node.children:
            return
        assert len(node.children) <= len(Reg)
        count = self.regcount(node)
        if count + targreg > len(Reg):
            stacked: list[Reg] = []
            for i, child in enumerate(node.children):
                self.asmnode(child, targreg)
                self.asm(f'push {targreg.name}')
                stacked.append(Reg(targreg+i))
            for reg in reversed(stacked):
                self.asm(f'pop {reg}')
        else:
            for i, child in enumerate(node.children):
                self.asmnode(child, Reg(i+targreg))

    def asmnode(self, node: Node, targreg: Reg = Reg.HL) -> None:
        """Assemble the node into the given register."""
        match node.label:
            # Special cases
            case 'brz':
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
                self.asm(f'je {node.value}')
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

                args = node.children[1:]
                func = node.children[0]
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
                    self.asm(
                        'xchg', f'lhld {len(args)*2}', 'dad sp', 'sphl',
                        'xchg')

                if saved:
                    self.asm('xchg')  # Result in HL now in DE where we wanted
                    self.asm('pop h')  # Restore old HL

            case _:
                self.asmchildren(node, targreg)
                match node.label:
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
                        self.asm('xchg', 'mov m,e', 'inx h', 'mov m,d',
                                 'xchg')
                    case 'extern' | 'con':
                        self.immed(targreg, node.value)
                    case 'add':
                        assert targreg == Reg.HL
                        self.asm('dad d')
                    case 'sub':
                        assert targreg == Reg.HL
                        self.asm('mov a,e', 'sub l', 'mov l,a')
                        self.asm('mov a,d', 'sbb h', 'mov h,a')
                    case 'cstore':
                        assert targreg == Reg.HL
                        self.asm('xchg', 'mov m,e', 'xchg')
                    case 'mult':
                        self.asm('call cmult')
                    case _:
                        raise NotImplementedError

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
                self.eval(nodestk.pop)
                self.asmret()
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

"""C6T - C version 6 by Troy - Operator Information Tables"""

from defaulter import Flags

noconv = Flags(
    'comma', 'logor', 'logand', 'postinc', 'preinc', 'postdec', 'predec'
)

assign = Flags(
    'assign', 'asnadd', 'asnsub', 'asnmult', 'asndiv', 'asnmod', 'asnrshift',
    'asnlshift', 'asnand', 'asneor', 'asnor'
)

tyright = Flags(
    'comma'
)

isint = Flags(
    'logor', 'logand'
)

lessgreat = Flags(
    'less', 'great', 'lequ', 'gequ',
    'uless', 'ugreat', 'ulequ', 'ugequ'
)

compare = Flags(
    'equ', 'nequ', *lessgreat.keys()
)

yesflt = Flags(
    'add', 'sub', 'mult', 'div', 'neg'
)

needlval = Flags(
    *assign.keys(), 'preinc', 'postinc', 'predec', 'postdec', 'dot', 'addr'
)

islval = Flags(
    'dot', 'arrow', 'deref', 'name'
)

nopointconv = Flags(
    *assign.keys(), *compare.keys()
)

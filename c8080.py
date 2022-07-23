"""C6T - C version 6 by Troy - Intel 8080 codegen


--- THINKING IT THRU ON PAPER ---
Codegens can be unary-HL, binary, unary-DE, unary-ANY, leaf-DE, leaf-HL, or
leaf-ANY. So more accurately, unary/binary/leaf, with binary using DE and HL,
leafs attaching HL/DE/ANY.

Labels can be leaf, unary, binary, or special.
Labels can be commutative or not.

Left operands/results in HL, right operands in DE. Commutative doesn't matter.

Calculate into HL. If binary, see if we can get right into DE w/o using HL.
In other words, using only leaf/unary-DE/ANY. If not, push H and calculate.

We could also calculate the left node first, swap it into DE, and then see if
the right node is computable using only unary/leaf-HL/ANY nodes.

So, a given node can be matched to unary/leaf-HL/DE/Any -- you could see which
register operations are available and list them all. Or it could be binary.

A given node, RECURSIVELY DOWN THRU ITS CHILDREN, either contains ANY binary
nodes, or unary/leaf-HL/DE/ANY's. If unary/leaf, and not all of its children
support all registers, then we COULD calculate a maximal chain of the minimal
xchg's needed, OR just say "ANY" and xchg away. Maybe mark it XCHG-requiring.

So, if we want a node, and it's binary, then the order of the children depends
on whether the node's label is commutative, and whether any children can be
computed unary-style. One could count up the number of xchg's required on
a unary to decide which order if it is so marked.

BUT, it's fine to push HL and pop it into DE or HL later, we're going to do
a bunch of that.

POSSIBLY, we could also list requirements -- for starts, the left or right
child node labels. Then limit those being searched to things fitting those
requirements. MAYBE also value comparisons, equals would be easiest.

Anyway, so our expression assembler could work recursively downwards. We
should keep track of if HL or DE are in-use. In case of a unary/leaf node,
if we can place it into a not-in-use register do so, otherwise swap/save
the register.

It would be GREAT if I could keep track of where evaluated nodes have gotten
stored, so I can swap 'em and just know where they were?

OK, so let's look again. If we started with a binary node, the cases are
we could evaluate one into HL and one into DE (meaning both are
Unary/Leaf-DE/HL/ANY), or else they interfere in some way. If both are
recursively binaries, then the order doesn't matter - I guess we could save
some pushes/pops along the way? Commutative we could do the one with the last
of those first, push it, then the other one, then pop back into DE. Otherwise
the order is required.

For unaries, we either don't interfere or we do. If we interfere we can either
avoid pushing and do it all with xchg's or not. We ALWAYS can as long as
neither side is binaries.

So a binary with two binaries is push, a binary with two unaries or a unary
with a unary is a xchg. So we can weight the cost.

So we have a push/xchg/noninterfere cost, and a binary/unary/leaf cost.

We could also mark nodes as ORDER_REQUIRED as opposed to just commutative -
non-commutative would reuqire the nodes to be in the proper order,
possibly xchging them (add to cost?), while ORDER_REQUIRED means you HALF
to do one side first then the other. Those might all end up special though?
Yes they would. Carry on then.

Special is things like &&/||/call/brz/etc. We need to handle them carefully
anyhow.

In terms of for_cc or not, we really only have "we just did a subtraction,
do we need to logical (convert to 1 or 0) or not". We might manually put in
branch and logical/lognot nodes and then grab out chains. Chains of logical/
lognots should return the other, and a branch on a logical/lognot can just
be what it was logicalling. But logical/lognot's MUST have their sub node be
a subtraction. This subtraction maybe could be special cased so that we can't
do a lot of subtraction optimzations (converting to additions where possible).

This would be good for if we could have requirements of immediate child node
labels/values, 'cause then we could have a brz on a sub evaluate to no test,
while brz on anything else throws a test in.

We'll only assume CC codes are set on the special subtraction? Maybe call it
'compare' even though its implemented w/ a phsyical subtract.

Special nodes might require assuming both sides are using both registers, or
else on a maximum worst case of all its elements. So like a CALL, we need
to evaluate all arguments, push them onto the stack one by one, and evaluate
the function itself. And the worst case we have is a binary with a set count
of xchg/pushes.

It's IMPORTANT that all things we push on get popped off by the end of
evaluating a given node. Treating binaries individually is a good example
of that.
"""

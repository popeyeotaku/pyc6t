# pyC6T - python implementation of C version 6 by Troy

pyC6T ('pie see sixty') is an implementation of the ancient pre-K&R version of C included in the 1975 Unix
edition released by Bell Labs as "Research Unix, Sixth Edition". This version
of C is much closer to assembly than modern C, has far fewer type conversions,
and many difficult areas of parsing modern C are missing. More accurately,
it is very similar to many toy C compilers, in tersm of the difficulties
of the language they skip.

Briefly, there's no longs or shorts, structs can't be passed, pointers are guaranteed
to be interchangable with ints, no enums, no typedefs.

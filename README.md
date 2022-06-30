# pyC6T - python implementation of C version 6 by Troy

pyC6T ('pie see sixty') is an implementation of the ancient pre-K&R version of C included in the 1975 Unix
edition released by Bell Labs as "Research Unix, Sixth Edition". This version
of C is much closer to assembly than modern C, has far fewer type conversions,
and many difficult areas of parsing modern C are missing. More accurately,
it is very similar to many toy C compilers, in tersm of the difficulties
of the language they skip.

Briefly, there's no longs or shorts, structs can't be passed, pointers are guaranteed
to be interchangable with ints, no enums, no typedefs.

## Compiler Tour

There are three things in C6T:
    - specifications (called 'declarations' in regular C)
    - statements
    - expressions

A program is a series of external definition specifiers, which are a specifier followed by an optional initializer expression or list of expressions in braces.

For instance:
    int foo[] { 2, 3, 4};
    extern int bar 5, double foobar 6.0;

As a special case, if the first element in list is function type, the rest of the element is a function definition, and the given line of specifiers is ended.

A function definition contains a series of specifiers for parameters giving their types, followed by a left brace, followed by specifiers for locals, followed by the statements of the function, and ended in a right brace.

For instance:
    main(argc, argv) char **argv;
    {
        static char *string;

        while (--argc) {
            string = *++argv;
            puts(string);
        }
    }

Lines of specifiers are implemented thru the function spec.specline, with a callback function to be run immediately after the specifier has been seen - this allows initializers to be consumed, for instance. The callback returns a flag for if the specifier line should continue, to implement function definitions.

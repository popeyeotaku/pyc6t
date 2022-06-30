#

/* testing */

#define FOOBAR foo /* foo */ , /* bar */ bar

#include "test.h"

foobar()
{
    putoct(FOOBAR, 0);
}

putoct(o)
{
    if (o)
        putoct((o>>3)&~0160000);
    putdigit(o&07);
}

putdigit(c)
{
    putchar(c + '0');
}

main()
{
    puts("\n\nHello, world! :D\n");
    putoct(sizeof("1234")); /* should be 5 */
}

puts(string)
{
    register char *s;
    register c;

    if (s = string) while (c = *s++) putchar(c);
}
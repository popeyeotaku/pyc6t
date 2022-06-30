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

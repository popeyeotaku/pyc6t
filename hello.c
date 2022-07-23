#

/* Hello World for the Intel 8080 */

main()
{
    initsio();
    puts("Hello world :D\n");
}

puts(string)
{
    register c;
    register char *s;

    if (s = string) while (c = *s) {
        putchar(c);
        s = s + 1;
    }
}

/* 2SIO support */

#define SIOPORT 020
#define SIODAT 021

#define SIOCLK 0
#define SIOPAR 07
#define SIOINT 0

#define SIOXMIT 02
#define SIOREC 01

intsio()
{
    out80(SIOPORT, SIOCLK<<5+SIOPAR<<2+SIOCLK);
}

putchar(c)
{
    while (!(in80(SIOPORT)&SIOXMIT))
        ;
    out80(SIODAT, c&0177);
}

getchar()
{
    while(in80(SIOPORT)&SIOREC)
        ;
    return (in80(SIOPORT) & 0177);
}
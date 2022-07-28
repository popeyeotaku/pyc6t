#define SIOPORT 020
#define SIODAT 021

#define SIOCLK 0
#define SIOPAR 07
#define SIOINT 0

#define SIOXMIT 02
#define SIOREC 0

initsio()
{
    out80(SIOPORT, SIOCLK<<5|SIOPAR<<2|SIOCLK);
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
    return (0177 & in80(SIOPORT));
}

puts(string)
{
    register c;
    register char *s;

    if (s = string) while (c = *s++) putchar(c);
}
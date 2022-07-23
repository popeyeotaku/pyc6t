#

#define WIDTH 80

#define BUFLEN 512
char wordbuf[BUFLEN];
int wordlen;
int foundnl;

wrap(linewidth)
{
        register left, line;

        left = line = linewidth;
        while (inword()) {
                if (foundnl) {
                        putchar('\n');
                        left = line - wordlen;
                }
                else if (wordlen + 1 > left) {
                        putchar('\n');
                        outword();
                        left = line - wordlen;
                }
                else {
                        outword();
                        left = left - wordlen + 1;
                }
        }
        flush();
}

inword()
{
        register c;
        static peeked;
        register char *pnt;

        foundnl = 0;
        pnt = wordbuf;

        /* skip leading whitespace */
        if (peeked) {
                c = peeked;
                peeked = 0;
        }
        else c = getchar();
        do {
                if (c && c != ' ' && c != '\t') break;
        } while (c = getchar());

        if (!c) return (0);

        if (c == '\n') {
                foundnl = 1;
                return (1);
        }

        do {
                if (!c || c == ' ' || c == '\t' || c == '\n') {
                        peeked = c;
                        break;
                }
                if (pnt < &wordbuf[BUFLEN-1]) {
                        *pnt = c;
                        pnt = pnt + 1;
                }
        } while (c = getchar());
        *pnt = 0;

        return (wordlen = pnt - wordbuf);
}

outword()
{
        register char *pnt;
        register c;

        pnt = wordbuf;
        for (pnt = wordbuf; c = *pnt; pnt = pnt + 1)
                putchar(c);
        putchar(' ');
}

digit(c)
{
        return (c >= '0' && c <= '9');
}


/* 2SIO support */

#define SIO 020
#define SIODAT 021
#define SIOXMIT 02

#define SIOSHAKE 0
#define SIODATA 7
#define SIOCLK 0

int siostart;

putchar(c)
{
        if (!siostart) initsio();
        while (!(in80(SIO)&SIOXMIT))
                ;
        out80(SIODAT, c);
}

sioinit()
{
        out80(SIO, SIOSHAKE<<5|SIODATA<<2|SIOCLK);
        siostart = 1;
}

main()
{
        wrap(WIDTH);
}
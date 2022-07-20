#

#define DEFAULT 80

#define BUFLEN 512
char wordbuf[BUFLEN];
int wordlen;

wrap(linewidth)
{
        register left;

        left = linewidth;
        while (inword()) {
                if (wordlen + 1 > left) {
                        putchar('\n');
                        outword();
                        left = linewidth - wordlen;
                }
                else {
                        outword();
                        left = left - (wordlen + 1);
                }
        }
        flush();
}

inword()
{
        register c;
        register char *pnt;

        pnt = wordbuf;

        /* skip leading whitespace */
        while (c = getchar()) {
                if (!ws(c)) break;
        }
        if (!c) return (0);

        do {
                if (ws(c)) break;
                if (pnt < &wordbuf[BUFLEN-1]) *pnt++ = c;
        } while (c = getchar());
        *pnt = 0;

        return (wordlen = pnt - wordbuf);
}

main(argc, argv) char **argv;
{
        register width;

        if (argc < 2) width = DEFAULT;
        else width = atoi(argv[1]);
        wrap(width);
}

ws(c)
{
        return (c == ' ' || c == '\t' || c == '\n');
}

outword()
{
        register char *pnt;
        register c;

        pnt = wordbuf;
        while (c = *pnt++) putchar(c);
        putchar(' ');
}

atoi(string)
{
        register char *pnt;
        register c;
        register i;

        i = 0;
        pnt = string;

        while (!digit(*pnt)) pnt++;

        while (digit(c = *pnt++)) i = i * 10 + c - '0';

        return (i ? i : DEFAULT);
}

digit(c)
{
        return (c >= '0' && c <= '9');
}
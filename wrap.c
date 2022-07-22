#

#define DEFAULT 80

#define BUFLEN 512
char wordbuf[BUFLEN];
int wordlen;
char foundnl;

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

main(argc, argv) char **argv;
{
        register width;

        if (argc < 2) width = DEFAULT;
        else width = atoi(argv[1]);
        wrap(width);
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

atoi(string)
{
        register char *pnt;
        register c;
        register i;

        i = 0;
        pnt = string;

        while (!digit(*pnt)) pnt = pnt + 1;

        while (digit(c = *pnt)) {
                i = i * 10 + c - '0';
                pnt = pnt + 1;
        }

        if (i > 0)
                return (i);
        else return (DEFAULT);
}

digit(c)
{
        return (c >= '0' && c <= '9');
}

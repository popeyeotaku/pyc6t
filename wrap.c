#

#define WIDTH 23

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
			left = left - (wordlen + 1);
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
		if (pnt < &wordbuf[BUFLEN-1]) *pnt++ = c;
	} while (c = getchar());
	*pnt = 0;

	return (wordlen = pnt - wordbuf);
}

outword()
{
	register char *pnt;
	register c;

	pnt = wordbuf;
	while (c = *pnt++) putchar(c);
	putchar(' ');
}


/* 2SIO support */

#define SIO 020
#define SIODAT 021
#define SIOXMIT 02
#define SIOREC 01

#define SIOSHAKE 0
#define SIODATA 7
#define SIOCLK 0

putchar(c)
{
	while (!(in80(SIO)&SIOXMIT))
		;
	out80(SIODAT, c);
}

getchar()
{
	register c;
	while(in80(SIO)&SIOREC)
		;
	c = in80(SIODAT) & 0177;
	/* putchar(c); */
	return (c);
}

sioinit()
{
	out80(SIO, SIOSHAKE<<5|SIODATA<<2|SIOCLK);
}

main()
{
	sioinit();
	wrap(WIDTH);
}

flush()
{}

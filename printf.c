printf(fmt, args)
{
    register char *s;
    register i;
    register *argpnt;

    s = fmt;
    argpnt = &args;
    
    while (i = *s++) if (i == '%') switch (i = *s++) {
        case 0:
            return;
        default:
            putchar(i);
            continue;
        case 'c':
            if (i = *argpnt++) putchar(i);
            continue;
        case 's':
            puts(*argpnt++);
            continue;
        case 'd':
            i = *argpnt++;
            if (!i) { putchar('0'); continue;; }
            if (i < 0) {
                i = -i;
                putchar('-');
            }
            putdec(i);
        case 'o':
            if (!(i = *argpnt++)) putchar('0');
            else putoct(i);
    }
    else putchar(i);
}

putoct(num)
{
    register n;

    if (n = num)
        putoct((n>>3)&~0160000);
    putchar((n&07)+'0');
}

putdec(num)
{
    register n, t;

    if (t = (n = num)/10)
        putdec(t);
    putchar(n%10 + '0');
}
main(argc, argv) char **argv;
{
    register i;

    i = 0;
    while (--argc) i =+ atoi(*++argv);
    return (i);
}

atoi(string)
{
    register char *pnt;
    register i;
    register neg;

    pnt = string;
    i = neg = 0;

    while (*pnt && !digit(*pnt) && *pnt != '-') pnt++;
    if (*pnt == '-') {
        neg = -1;
        pnt++;
    }
    
    while (digit(*pnt))
        i = (i * 10) + (*pnt++ - '0');
    
    return (neg ? -i : i);
}

digit(c)
{
    return ('0' <= c && c <= '9');
}
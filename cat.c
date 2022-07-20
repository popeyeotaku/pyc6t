#
/* by Troy F. */

#define BUFLEN 512

main(argc, argv) char **argv;
{
    register file;
    register char *name;

    if (argc <= 1)
        cat(0);
    else while (--argc) {
        name = *++argv;
        if (name[0] == '-')
            file = 0;
        else {
            file = open(name, 0);
            if (file < 0) continue;
        }
        cat(file);
        if (file != 0) close(file);
    }
}

out(file, buffer, count)
{
    register c, i;
    register char *pnt;

    c = count;
    pnt = buffer;

    while (c) {
        if ((i = write(file, pnt, c)) < 0)
            return;
        c =- i;
        pnt =+ i;
    }
}

cat(file)
{
    register in, f;
    static char buf[BUFLEN];

    f = file;
    while ((in = read(f, buf, BUFLEN)) > 0)
        out(f, buf, in);    
}
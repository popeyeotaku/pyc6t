#
int fin 0;

getchar()
{
    static pushed, c;
    register p;

    if (read(fin, &c, 1) != 1) {
        if (pushed) {
            p = pushed;
            pushed = 0;
            return (p);
        }
    }
    if (c == '\n' && pushed == '\r') {
        pushed = 0;
        return ('\n');
    }
    if (c == '\r' && pushed == '\n') {
        pushed = 0;
        return ('\n');
    }
    if (pushed) {
        p = pushed;
        if (c == '\n' || c == '\r') 
            pushed = c;
        else pushed = 0;
        return (p);
    }
    if (c == '\n' || c == '\r') {
        pushed = c;
        return (getchar());
    }
    return (c);
}
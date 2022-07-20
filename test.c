#

#define FOOBAR 150
#define INDEX 11

struct foobar {
    int foo, bar;
} foobar[] {
    1, 2, 3, 4, 5, 6, 7
};

main()
{
    register struct foobar *pnt;
    register total;

    for (total = 0, pnt = foobar; pnt->foo && pnt->bar; pnt++)
        total =+ pnt->foo * pnt->bar;
    return (total);
}
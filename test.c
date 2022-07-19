#

#define FOOBAR 150

struct foobar {
    int foo, bar;
    struct foobar *list[FOOBAR];
};

main()
{
    static struct foobar fb;
    
    return (test(fb.foo, fb.list[11]->bar));
}

test(foo, bar)
{
    return (foo*bar);
}
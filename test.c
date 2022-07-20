#

#define FOOBAR 150
#define INDEX 11

struct foobar {
    char foo, bar;
    struct foobar *list[FOOBAR];
};

main()
{
    static struct foobar foobar;
    register foo, bar;

    foo = foobar.foo = foobar.foo ? foobar.bar : test(foobar.list[INDEX]);
    bar = foobar.bar = foobar.foo ? foobar.foo : foobar.bar;
    return (test(foo, bar));
}

test(foo, bar)
{
    return (foo*bar);
}
struct foobar {
    int foo;
    int (*bar)();
    struct foobar *next;
};

foobar(head, foo)
{
    register *pnt, f;

    for (pnt = head, f = foo; pnt; pnt = pnt->next)
        if (pnt->foo == f)
            (*pnt->bar)(f);
}
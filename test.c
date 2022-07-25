main(argc, argv) char **argv;
{
    int i;

    for (i = 0; i < argc; i++) {
        puts(argv[i]);
        continue;
        break;
    };
    
    for (i = 0; i < argc) {
        puts(argv[i++]);
        continue;
        break;
    }
}
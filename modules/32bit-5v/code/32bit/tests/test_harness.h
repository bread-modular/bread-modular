#ifndef TEST_HARNESS_H
#define TEST_HARNESS_H

void bm_test_install_failure_handlers(void);
void bm_test_start(const char *test_name);
void bm_test_end(void);

#define BM_RUN_TEST(fn)        \
    do {                       \
        bm_test_start(#fn);    \
        fn();                  \
        bm_test_end();         \
    } while (0)

#endif /* TEST_HARNESS_H */

CC ?= gcc
CFLAGS ?= -std=c99 -Wall -Wextra -Werror -pedantic -I../main/include -Istubs
LDFLAGS ?= -lm

LIB_SOURCES = \
    ../main/src/lib/bm_buffer.c \
    ../main/src/lib/bm_param.c \
    ../main/src/lib/bm_utils.c \
    stubs/esp_heap_caps.c

TEST_SOURCES = test_bm_lib.c

TARGET = run_tests

.PHONY: all clean test

all: $(TARGET)

$(TARGET): $(LIB_SOURCES) $(TEST_SOURCES)
	$(CC) $(CFLAGS) $(LIB_SOURCES) $(TEST_SOURCES) $(LDFLAGS) -o $(TARGET)

clean:
	rm -f $(TARGET)
	rm -f *.o
	rm -f stubs/*.o
	rm -f stubs/*.gcda stubs/*.gcno
	rm -f *.gcda *.gcno
	rm -f *.d

run: $(TARGET)
	./$(TARGET)

test: run

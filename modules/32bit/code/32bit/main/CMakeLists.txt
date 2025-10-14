idf_component_register(SRCS "main.c" "src/bm_led.c" "src/bm_button.c"
                       PRIV_REQUIRES spi_flash
                       REQUIRES driver
                       INCLUDE_DIRS "" "include")

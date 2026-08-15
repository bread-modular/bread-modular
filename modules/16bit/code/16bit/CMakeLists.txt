# Generated Cmake Pico project file

cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Initialise pico_sdk from installed location
# (note this can come from environment, CMake cache etc)

# SDK and toolchain paths are provided by scripts/build.sh via -DPICO_SDK_PATH and
# -DPICO_TOOLCHAIN_PATH (both installed under ~/.breadmodular by scripts/setup.sh).
# The build is fully self-contained and does NOT depend on ~/.pico-sdk.

# 16bit board script will set the flash size to 16MB in the runtime
set(PICO_BOARD 16bit)
set(PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/includes/boards)
# This configures the firmware flash size to 2MB
# So, it won't override the 14MB filesystem when flashing the firmware
set(PICO_FLASH_SIZE_BYTES 2097152)

# Pull in Raspberry Pi Pico SDK (must be before project)
include(pico_sdk_import.cmake)

project(16bit C CXX ASM)

# Initialise the Raspberry Pi Pico SDK
pico_sdk_init()

# ---------------------------------------------------------------------------
# App selection at compile time (one app per firmware, like the 32bit module)
# The firmware compiles a SINGLE app into the binary; scripts/package.sh builds
# one firmware per app. Default to polysynth if not specified.
# ---------------------------------------------------------------------------
if(NOT DEFINED APP_NAME)
    set(APP_NAME "polysynth")
endif()

set(VALID_APPS "noop" "sampler" "polysynth" "fxrack" "elab")
if(NOT APP_NAME IN_LIST VALID_APPS)
    message(FATAL_ERROR "Invalid APP_NAME: ${APP_NAME}. Valid options are: ${VALID_APPS}")
endif()

# BM_APP_<NAME>=1 compile definition + FIRMWARE_NAME used by main.cpp
set(APP_DEFINE "BM_APP_${APP_NAME}")
string(TOUPPER "${APP_DEFINE}" APP_DEFINE)

# Add executable. Default name is the project name, version 0.1

add_executable(16bit
    main.cpp
)
pico_generate_pio_header(16bit ${CMAKE_CURRENT_LIST_DIR}/i2s.pio)

# Read version from file main 16bit versiob file
file(READ "${CMAKE_CURRENT_LIST_DIR}/../../VERSION" PROJECT_VERSION)
string(STRIP "${PROJECT_VERSION}" PROJECT_VERSION)

pico_set_program_name(16bit "16bit")
pico_set_program_version(16bit "${PROJECT_VERSION}")

# Modify the below lines to enable/disable output over UART/USB
pico_enable_stdio_uart(16bit 0)
pico_enable_stdio_usb(16bit 1)

# Configure USB device descriptors
target_compile_definitions(16bit PRIVATE
    USBD_VID=0x2E8A
    USBD_PID=0x000A
    USBD_MANUFACTURER="Bread Modular"
    USBD_PRODUCT="16bit"
    ${APP_DEFINE}=1
    FIRMWARE_NAME="${APP_NAME}"
)

# Add external libraries
add_library(lfs STATIC
    ${CMAKE_CURRENT_LIST_DIR}/lib/lfs/lfs.c
    ${CMAKE_CURRENT_LIST_DIR}/lib/lfs/lfs_util.c
)

# Add the standard library to the build
target_link_libraries(16bit
        pico_stdlib
        hardware_pio
        pico_multicore
        hardware_adc
        lfs
        )

# Add the standard include files to the build
target_include_directories(16bit PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}
        ${CMAKE_CURRENT_LIST_DIR}/includes
        ${CMAKE_CURRENT_LIST_DIR}/lib/lfs
)

pico_add_extra_outputs(16bit)

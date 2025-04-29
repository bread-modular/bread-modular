# Generated Cmake Pico project file

cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Initialise pico_sdk from installed location
# (note this can come from environment, CMake cache etc)

# == DO NOT EDIT THE FOLLOWING LINES for the Raspberry Pi Pico VS Code Extension to work ==
if(WIN32)
    set(USERHOME $ENV{USERPROFILE})
else()
    set(USERHOME $ENV{HOME})
endif()
set(sdkVersion 2.1.1)
set(toolchainVersion 14_2_Rel1)
set(picotoolVersion 2.1.1)
set(picoVscode ${USERHOME}/.pico-sdk/cmake/pico-vscode.cmake)
if (EXISTS ${picoVscode})
    include(${picoVscode})
endif()
# ====================================================================================
# 16bit board script will set the flash size to 16MB in the runtime
set(PICO_BOARD 16bit)
set(PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/includes/boards)
# This configures the firmware flash size to 2MB
# So, it won't override the 14MB filesystem when flashing the firmware
set(PICO_FLASH_SIZE_BYTES 2097152)

# Pull in Raspberry Pi Pico SDK (must be before project)
include(pico_sdk_import.cmake)

project(sampler C CXX ASM)

# Initialise the Raspberry Pi Pico SDK
pico_sdk_init()

# Add executable. Default name is the project name, version 0.1

add_executable(sampler main.cpp )
pico_generate_pio_header(sampler ${CMAKE_CURRENT_LIST_DIR}/i2s.pio)

pico_set_program_name(sampler "sampler")
pico_set_program_version(sampler "0.1")

# Modify the below lines to enable/disable output over UART/USB
pico_enable_stdio_uart(sampler 0)
pico_enable_stdio_usb(sampler 1)

# Add external libraries
add_library(lfs STATIC
    ${CMAKE_CURRENT_LIST_DIR}/lib/lfs/lfs.c
    ${CMAKE_CURRENT_LIST_DIR}/lib/lfs/lfs_util.c
)

# Add the standard library to the build
target_link_libraries(sampler
        pico_stdlib
        hardware_pio
        pico_multicore
        hardware_adc
        lfs
        )

# Add the standard include files to the build
target_include_directories(sampler PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}
        ${CMAKE_CURRENT_LIST_DIR}/includes
        ${CMAKE_CURRENT_LIST_DIR}/lib/lfs
)

pico_add_extra_outputs(sampler)


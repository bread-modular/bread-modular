# App selection at compile time
# Default to fxrack if not specified
if(NOT DEFINED APP_NAME)
    set(APP_NAME "fxrack")
endif()

# Validate app name
set(VALID_APPS "fxrack" "reverb")
if(NOT APP_NAME IN_LIST VALID_APPS)
    message(FATAL_ERROR "Invalid APP_NAME: ${APP_NAME}. Valid options are: ${VALID_APPS}")
endif()

# Read VERSION file (located at ../../../VERSION relative to main/CMakeLists.txt)
set(VERSION_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../../../VERSION")
if(EXISTS "${VERSION_FILE}")
    file(READ "${VERSION_FILE}" VERSION_CONTENT)
    string(STRIP "${VERSION_CONTENT}" FIRMWARE_VERSION)
else()
    set(FIRMWARE_VERSION "0.0.0")
    message(WARNING "VERSION file not found at ${VERSION_FILE}, using default version 0.0.0")
endif()

# Set compile definition for the selected app
set(APP_DEFINE "BM_APP_${APP_NAME}")
string(TOUPPER "${APP_DEFINE}" APP_DEFINE)

idf_component_register(
    SRCS
        "main.c"
        "src/bm_led.c"
        "src/bm_button.c"
        "src/bm_cv.c"
        "src/bm_es8388.c"
        "src/bm_audio.c"
        "src/bm_midi.c"
        "src/bm_usb_serial.c"
        "src/lib/bm_buffer.c"
        "src/lib/bm_utils.c"
        "src/lib/bm_save.c"
        "src/lib/bm_param.c"
        "src/audio/bm_comb_filter.c"
        "src/audio/bm_all_pass_filter.c"
        "src/audio/bm_classic_reverb.c"
        "src/apps/bm_app_fxrack.c"
        "src/apps/bm_app_reverb.c"
    PRIV_REQUIRES
        spi_flash
    REQUIRES
        driver
        esp_adc
        esp_timer
        nvs_flash
    INCLUDE_DIRS
        ""
        "include"
)

# Add compile definitions after component registration
target_compile_definitions(${COMPONENT_LIB} PRIVATE 
    ${APP_DEFINE}=1
    FIRMWARE_NAME="${APP_NAME}"
    FIRMWARE_VERSION="${FIRMWARE_VERSION}"
)

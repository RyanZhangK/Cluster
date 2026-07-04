cmake_minimum_required(VERSION 3.20)
project(cluster-flasher VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ---- Option: bundle esptool via PyInstaller ----
option(BUNDLE_ESPTOOL "Bundle esptool as a standalone binary" OFF)

# ---- Dependencies via FetchContent ----
include(FetchContent)

# GLFW
FetchContent_Declare(
    glfw
    GIT_REPOSITORY https://github.com/glfw/glfw.git
    GIT_TAG 3.4
    GIT_SHALLOW TRUE
)
set(GLFW_BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(GLFW_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(glfw)

# Dear ImGui
FetchContent_Declare(
    imgui
    GIT_REPOSITORY https://github.com/ocornut/imgui.git
    GIT_TAG v1.91.8
    GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(imgui)

# ---- ImGui GLFW backend source ----
set(IMGUI_SOURCES
    ${imgui_SOURCE_DIR}/imgui.cpp
    ${imgui_SOURCE_DIR}/imgui_draw.cpp
    ${imgui_SOURCE_DIR}/imgui_tables.cpp
    ${imgui_SOURCE_DIR}/imgui_widgets.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_glfw.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_opengl3.cpp
)

# ---- Flasher sources ----
set(FLASHER_SOURCES
    main.cpp
    serial_ports.cpp
    flasher.cpp
)

# ---- Executable ----
add_executable(cluster-flasher ${FLASHER_SOURCES} ${IMGUI_SOURCES})

target_include_directories(cluster-flasher PRIVATE
    ${imgui_SOURCE_DIR}
    ${imgui_SOURCE_DIR}/backends
)

target_link_libraries(cluster-flasher PRIVATE glfw)

# Platform-specific OpenGL
if(WIN32)
    target_link_libraries(cluster-flasher PRIVATE opengl32)
elseif(APPLE)
    find_library(OPENGL_LIB OpenGL REQUIRED)
    target_link_libraries(cluster-flasher PRIVATE ${OPENGL_LIB})
else()
    find_package(OpenGL REQUIRED)
    target_link_libraries(cluster-flasher PRIVATE OpenGL::GL)
endif()

# Platform-specific serial port enumeration
if(WIN32)
    target_link_libraries(cluster-flasher PRIVATE setupapi)
    target_compile_definitions(cluster-flasher PRIVATE UNICODE _UNICODE)
endif()

# Runtime output dir
set_target_properties(cluster-flasher PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

# ---- Bundle esptool via PyInstaller ----
if(BUNDLE_ESPTOOL)
    # Use system python (with pip), not venv python
    find_program(SYSTEM_PYTHON NAMES python3
        PATHS /usr/bin /usr/local/bin
        NO_DEFAULT_PATH
    )
    if(NOT SYSTEM_PYTHON)
        find_program(SYSTEM_PYTHON python3 REQUIRED)
    endif()
    set(ESPTOOL_ENTRY "${CMAKE_SOURCE_DIR}/bundle_esptool.py")
    set(ESPTOOL_OUTPUT "${CMAKE_BINARY_DIR}/bin/esptool")

    add_custom_command(
        OUTPUT ${ESPTOOL_OUTPUT}
        COMMAND ${SYSTEM_PYTHON} -m pip install esptool pyserial pyinstaller --quiet --break-system-packages
        COMMAND ${SYSTEM_PYTHON} -m PyInstaller --onefile --noconfirm --clean
                --collect-submodules esptool
                --distpath "${CMAKE_BINARY_DIR}/bin" --name esptool "${ESPTOOL_ENTRY}"
        WORKING_DIRECTORY "${CMAKE_BINARY_DIR}"
        COMMENT "Bundling esptool with PyInstaller..."
    )
    add_custom_target(bundle_esptool DEPENDS ${ESPTOOL_OUTPUT})
    add_dependencies(cluster-flasher bundle_esptool)
endif()

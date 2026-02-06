cmake_minimum_required(VERSION 3.15)
project(fasttoml)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find pybind11
find_package(pybind11 REQUIRED)

# SIMD optimizations
if(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|AMD64|i[3-6]86")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -mavx2 -msse4.2")
endif()

# Optimization flags
if(MSVC)
    set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} /O2 /EHsc /std:c++17")
else()
    set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -O3 -march=native")
endif()

# Include directories
include_directories(include)

# Source files
set(SOURCES
    src/toml_parser.cpp
    src/python_bindings.cpp
)

# Python module
pybind11_add_module(_native ${SOURCES})

# Set target properties
set_target_properties(_native PROPERTIES
    CXX_VISIBILITY_PRESET "hidden"
    VISIBILITY_INLINES_HIDDEN ON
)

if(NOT MSVC)
    target_compile_options(_native PRIVATE -Wall -Wextra -Wpedantic)
endif()

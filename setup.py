import os
import re
import sys
import platform
import subprocess

from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup, Extension

# Read version from pyproject.toml
def get_version():
    with open("pyproject.toml", "r") as f:
        content = f.read()
        match = re.search(r'version = "([^"]+)"', content)
        if match:
            return match.group(1)
    return "0.1.0"

__version__ = get_version()

# Check if CMake is available
def check_cmake():
    try:
        subprocess.check_output(["cmake", "--version"])
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

if not check_cmake():
    raise RuntimeError("CMake is required to build this package")

# Get pybind11 include directory
def get_pybind11_include():
    import pybind11
    return pybind11.get_include()

# SIMD flags
def get_simd_flags():
    flags = []
    if platform.machine().lower() in ['x86_64', 'amd64', 'i386', 'i686']:
        # AVX2 and SSE4.2 support
        if sys.platform != 'win32':
            flags.extend(['-mavx2', '-msse4.2'])
        else:
            flags.extend(['/arch:AVX2'])
    return flags

# Compiler-specific flags
def get_compile_args():
    extra_args = []
    
    # SIMD flags
    extra_args.extend(get_simd_flags())
    
    # C++17 standard
    if sys.platform != 'win32':
        extra_args.extend(['-std=c++17', '-O3', '-march=native'])
    else:
        extra_args.extend(['/std:c++17', '/O2', '/EHsc'])
    
    return extra_args

# Linker flags
def get_link_args():
    if sys.platform != 'win32':
        return ['-flto']
    return []

# Extension module
ext_modules = [
    Pybind11Extension(
        "fasttoml._native",
        [
            "src/toml_parser.cpp",
            "src/python_bindings.cpp",
        ],
        include_dirs=[
            "include",
            get_pybind11_include(),
        ],
        cxx_std=17,
        extra_compile_args=get_compile_args(),
        extra_link_args=get_link_args(),
        language='c++',
    ),
]

setup(
    name="fasttoml",
    version=__version__,
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
    python_requires=">=3.10",
)

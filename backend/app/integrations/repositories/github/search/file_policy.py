# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Allowed file extensions for the planned GitHub code-search restriction.

This module owns the ordered extension list and its REST qualifier suffix for
product and research callers. It does not filter responses or perform IO.
The search adapter does not apply this policy yet.
"""

CODE_SEARCH_EXTENSIONS: tuple[str, ...] = (
    # Python, Cython and notebooks.
    "py", "pyi", "pyx", "pxd", "ipynb",
    # R, Julia and MATLAB/Octave.
    "r", "rmd", "jl", "m",
    # C/C++ and GPU code.
    "c", "h", "cc", "cpp", "cxx", "hh", "hpp", "hxx", "cu", "cuh", "cl",
    # Fortran and include files.
    "f", "for", "f77", "f90", "f95", "f03", "f08", "inc",
    # Wolfram, SageMath, Scilab and IDL.
    "wl", "wls", "nb", "sage", "sci", "sce", "pro",
    # Other implementation languages and scripts.
    "rs", "go", "java", "js", "ts", "cs", "pl", "pm", "lua", "sh", "bash",
    "ps1", "sql",
    # Documentation.
    "md", "markdown", "rst", "tex", "latex", "adoc", "org", "html", "htm",
    "qmd", "txt",
)

CODE_SEARCH_EXTENSION_SUFFIX: str = " ".join(
    f"extension:{extension}" for extension in CODE_SEARCH_EXTENSIONS
)

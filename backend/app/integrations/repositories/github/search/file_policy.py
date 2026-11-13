# SPDX-FileCopyrightText: 2026 Ernest Borysenko
# SPDX-License-Identifier: Apache-2.0

"""Allowed files and request construction for GitHub REST code search.

This module owns the ordered extension list and its REST qualifier suffix for
product and research callers. It does not filter responses or perform IO.
"""

from app.integrations.repositories.common.search_query import quote_search_phrase

MAX_CODE_SEARCH_QUERY_LENGTH = 1000

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


def build_code_search_query(query: str) -> str:
    """Build the decoded REST q value; reject overflow without changing scope."""
    search_query = f"{quote_search_phrase(query)} {CODE_SEARCH_EXTENSION_SUFFIX}"
    if len(search_query) > MAX_CODE_SEARCH_QUERY_LENGTH:
        raise ValueError(
            "GitHub code search query exceeds the 1000-character limit after "
            "quoting and adding the allowed file extensions"
        )
    return search_query

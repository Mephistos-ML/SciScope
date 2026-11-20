"""The agreed GitHub file scope and its fixed request-size budget."""

import pytest

from app.integrations.repositories.github.search.file_policy import (
    CODE_SEARCH_EXTENSIONS,
    CODE_SEARCH_EXTENSION_SUFFIX,
    build_code_search_query,
)


def test_allowed_extensions_cover_the_agreed_scientific_file_scope():
    expected = set(
        "py pyi pyx pxd ipynb r rmd jl m "
        "c h cc cpp cxx hh hpp hxx cu cuh cl "
        "f for f77 f90 f95 f03 f08 inc "
        "wl wls nb sage sci sce pro "
        "rs go java js ts cs pl pm lua sh bash ps1 sql "
        "md markdown rst tex latex adoc org html htm qmd txt".split()
    )
    assert set(CODE_SEARCH_EXTENSIONS) == expected
    assert len(CODE_SEARCH_EXTENSIONS) == len(expected) == 59


def test_rest_suffix_contains_only_the_allowed_extension_qualifiers():
    qualifiers = CODE_SEARCH_EXTENSION_SUFFIX.split(" ")
    assert qualifiers == [f"extension:{ext}" for ext in CODE_SEARCH_EXTENSIONS]
    assert CODE_SEARCH_EXTENSION_SUFFIX.isascii()
    assert len(CODE_SEARCH_EXTENSION_SUFFIX) == 812


def test_fixed_suffix_leaves_185_characters_for_an_unescaped_ascii_phrase():
    request_query = build_code_search_query("a" * 185)
    assert len(request_query) == 1000


@pytest.mark.parametrize("query", ["x" * 186, "x" * 184 + '"', "x" * 184 + "\\"])
def test_request_cannot_exceed_the_fixed_budget(query):
    with pytest.raises(ValueError, match="1000-character limit"):
        build_code_search_query(query)


def test_search_terms_are_quoted_as_one_phrase():
    assert build_code_search_query("paramagnetic nmr") == (
        f'"paramagnetic nmr" {CODE_SEARCH_EXTENSION_SUFFIX}'
    )


def test_explicit_quotes_are_preserved_without_adding_quotes():
    assert build_code_search_query('"paramagnetic nmr"') == (
        f'"paramagnetic nmr" {CODE_SEARCH_EXTENSION_SUFFIX}'
    )


@pytest.mark.parametrize("query", ["", " \t\n"])
def test_empty_search_is_rejected(query):
    with pytest.raises(ValueError, match="must not be empty"):
        build_code_search_query(query)

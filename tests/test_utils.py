"""Tests for utility functions and edge cases."""

import pytest
from citeverify.utils import (
    clean_title,
    extract_year_from_text,
    fix_concatenated_words,
    normalize_doi,
    normalize_arxiv_id,
)


# --- clean_title: concatenated phrases (PDF drops spaces) ---


def test_clean_title_asa_to_as_a():
    """Grammar asa foreign language -> Grammar as a foreign language."""
    assert clean_title("Grammar asa foreign language") == "Grammar as a foreign language"


def test_clean_title_inthe_to_in_the():
    """inthe -> in the (PDF line break artifact)."""
    assert clean_title("results inthe wild") == "results in the wild"


def test_clean_title_ofthe_to_of_the():
    """ofthe -> of the."""
    assert clean_title("study ofthe effects") == "study of the effects"


def test_clean_title_suchas_to_such_as():
    """suchas -> such as."""
    assert clean_title("methods suchas attention") == "methods such as attention"


def test_clean_title_hyphenated_line_break():
    """im- age -> image (hyphenated line break)."""
    assert clean_title("im- age") == "image"


def test_clean_title_extra_whitespace():
    """Collapse multiple spaces."""
    assert clean_title("Hello   world") == "Hello world"


def test_clean_title_empty():
    """Empty or None-like input."""
    assert clean_title("") == ""


# --- extract_year_from_text: page ranges vs publication year ---


def test_extract_year_skip_page_range():
    """Skip 1929 in page range 15(1):1929–1958, prefer 2014."""
    text = "Journal of Machine Learning Research, 15(1):1929–1958, 2014."
    assert extract_year_from_text(text) == 2014


def test_extract_year_simple():
    """Single year in text."""
    assert extract_year_from_text("Published in 2020.") == 2020


def test_extract_year_prefer_last():
    """Prefer last year (publication year often at end)."""
    text = "First edition 2010. Revised 2023."
    assert extract_year_from_text(text) == 2023


def test_extract_year_none():
    """No year in text."""
    assert extract_year_from_text("No year here") is None


# --- fix_concatenated_words: compound words preserved ---


def test_fix_concatenated_words_overfitting_preserved():
    """overfitting should not be split into over fitting."""
    assert fix_concatenated_words("prevent overfitting") == "prevent overfitting"


def test_fix_concatenated_words_network_grammars():
    """networkgrammars -> network grammars (if applicable)."""
    result = fix_concatenated_words("networkgrammars")
    assert "network" in result and "grammars" in result


def test_fix_concatenated_words_short_words_unchanged():
    """Short words (<=8 chars) pass through."""
    assert fix_concatenated_words("hello world") == "hello world"


# --- normalize_doi ---


def test_normalize_doi_strips_prefix():
    """Strip doi:, https://doi.org/ prefixes."""
    assert normalize_doi("doi:10.1234/example") == "10.1234/example"
    assert normalize_doi("https://doi.org/10.1234/example") == "10.1234/example"


# --- normalize_arxiv_id ---


def test_normalize_arxiv_id_strips_version():
    """1234.5678v1 -> 1234.5678."""
    assert normalize_arxiv_id("arXiv:1234.5678v1") == "1234.5678"

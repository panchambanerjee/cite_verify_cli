"""Tests for citation extractor."""

import pytest
from citeverify.extractor import CitationExtractor
from citeverify.models import Citation


def test_parse_single_citation(sample_citation_text):
    """Test parsing a single citation string."""
    extractor = CitationExtractor()
    citation = extractor._parse_single_citation(sample_citation_text, "1")

    assert citation.number == "1"
    assert citation.raw_text == sample_citation_text
    assert citation.doi == "10.1234/test"
    assert citation.year == 2020
    assert "Example Paper Title" in (citation.title or "")


def test_parse_doi():
    """Test DOI extraction from citation text."""
    extractor = CitationExtractor()
    citation = extractor._parse_single_citation(
        "Author et al. (2020). Title. DOI: 10.1234/example", "1"
    )
    assert citation.doi == "10.1234/example"
    assert citation.year == 2020


def test_parse_arxiv_id():
    """Test arXiv ID extraction."""
    extractor = CitationExtractor()
    citation = extractor._parse_single_citation(
        "Author et al. (2023). Title. arXiv:2301.12345", "1"
    )
    assert citation.arxiv_id == "2301.12345"
    assert citation.year == 2023


def test_extract_from_pdf_missing_file():
    """Test extraction from non-existent PDF raises."""
    extractor = CitationExtractor()
    with pytest.raises((ValueError, FileNotFoundError, OSError)):
        extractor.extract_from_pdf("tests/fixtures/nonexistent.pdf")


# --- Edge case tests ---


def test_extract_unicode_author_kaiser_sutskever():
    """Unicode author name Łukasz in 'Neural GPUs learn algorithms'."""
    extractor = CitationExtractor()
    text = (
        "Łukasz Kaiser and Ilya Sutskever. Neural GPUs learn algorithms. "
        "In International Conference on Learning Representations (ICLR), 2016."
    )
    citation = extractor._parse_single_citation(text, "1")
    assert citation.title is not None
    assert "Neural GPUs" in (citation.title or "")
    assert "algorithms" in (citation.title or "")
    assert citation.year == 2016


def test_extract_venue_delimiter_structured_attention():
    """Title before 'In International Conference' - Kim et al. Structured attention networks."""
    extractor = CitationExtractor()
    text = (
        "Yoon Kim, Carl Denton, Luong Hoang, and Alexander M. Rush. "
        "Structured attention networks. In International Conference on Learning Representations, 2017."
    )
    citation = extractor._parse_single_citation(text, "1")
    assert citation.title is not None
    assert "Structured attention" in (citation.title or "")
    assert citation.year == 2017


def test_extract_leading_reference_number_stripped():
    """Leading [17] should be stripped before parsing."""
    extractor = CitationExtractor()
    text = (
        "[17] Smith, J. (2020). Example paper. Journal, 2020."
    )
    citation = extractor._parse_single_citation(text, "17")
    assert citation.title is not None


def test_extract_vinyals_grammar_as_foreign_language():
    """Vinyals & Kaiser - ampersand in authors, 'Grammar as a foreign language'."""
    extractor = CitationExtractor()
    text = (
        "Vinyals & Kaiser, Koo, Petrov, Sutskever, and Hinton. "
        "Grammar as a foreign language. In Advances in Neural Information Processing Systems, 2015."
    )
    citation = extractor._parse_single_citation(text, "1")
    assert citation.title is not None
    assert "Grammar" in (citation.title or "")
    assert "foreign language" in (citation.title or "")
    assert citation.year == 2015


def test_extract_marcus_penn_treebank():
    """Marcus et al. - colon in title, Penn Treebank."""
    extractor = CitationExtractor()
    text = (
        "Mitchell P Marcus, Mary Ann Marcinkiewicz, and Beatrice Santorini. "
        "Building a large annotated corpus of english: The penn treebank. "
        "Computational linguistics, 19(2):313–330, 1993."
    )
    citation = extractor._parse_single_citation(text, "1")
    assert citation.title is not None
    assert "Building" in (citation.title or "")
    assert "Penn" in (citation.title or "") or "penn" in (citation.title or "").lower()
    assert citation.year == 1993


def test_extract_srivastava_dropout_year_and_overfitting():
    """Srivastava et al. - year 2014 (not 1929 from page range), overfitting preserved."""
    extractor = CitationExtractor()
    text = (
        "Nitish Srivastava, Geoffrey E Hinton, Alex Krizhevsky, Ilya Sutskever, and Ruslan Salakhutdinov. "
        "Dropout: a simple way to prevent neural networks from overfitting. "
        "Journal of Machine Learning Research, 15(1):1929–1958, 2014."
    )
    citation = extractor._parse_single_citation(text, "1")
    assert citation.title is not None
    assert "overfitting" in (citation.title or "").lower()
    assert citation.year == 2014


def test_extract_parikh_decomposable_attention():
    """Parikh et al. - shortened title 'A decomposable attention model'."""
    extractor = CitationExtractor()
    text = (
        "Ankur Parikh, Oscar Täckström, Dipanjan Das, and Jakob Uszkoreit. "
        "A decomposable attention model. In Empirical Methods in Natural Language Processing, 2016."
    )
    citation = extractor._parse_single_citation(text, "1")
    assert citation.title is not None
    assert "decomposable" in (citation.title or "").lower()
    assert citation.year == 2016

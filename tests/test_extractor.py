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

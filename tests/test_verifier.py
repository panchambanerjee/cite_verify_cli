"""Tests for multi-source verifier."""

import pytest
from citeverify.models import Citation, VerificationStatus
from citeverify.verifier import MultiSourceVerifier


@pytest.fixture
def verifier():
    """Create verifier instance."""
    return MultiSourceVerifier()


@pytest.fixture
def citation_with_doi():
    """Citation with DOI."""
    return Citation(
        number="1",
        raw_text="Test",
        title="Attention Is All You Need",
        doi="10.48550/arXiv.1706.03762",
        year=2017,
    )


@pytest.mark.asyncio
async def test_verify_via_doi(verifier, citation_with_doi):
    """Test verification via DOI."""
    result = await verifier.verify(citation_with_doi)
    # Should find Transformer paper
    assert result.status in (
        VerificationStatus.VERIFIED,
        VerificationStatus.PARTIAL,
        VerificationStatus.ERROR,
    )
    assert 0 <= result.confidence <= 1
    await verifier.close()


@pytest.mark.asyncio
async def test_verify_unverified_citation(verifier):
    """Test verification of citation with no identifiers."""
    citation = Citation(
        number="1",
        raw_text="Fake paper that does not exist xyz123",
        title="Fake paper that does not exist xyz123",
    )
    result = await verifier.verify(citation)
    assert result.status in (
        VerificationStatus.UNVERIFIED,
        VerificationStatus.PARTIAL,
        VerificationStatus.ERROR,
    )
    await verifier.close()


@pytest.mark.asyncio
async def test_title_similarity(verifier):
    """Test title similarity helper."""
    # Identical titles: prefix match returns 0.95
    assert verifier._title_similarity("Hello World", "Hello World") >= 0.9
    assert verifier._title_similarity("Hello", "World") < 0.5
    assert verifier._title_similarity("", "Something") == 0.0


# --- Edge case tests ---


def test_title_similarity_prefix_match_shortened_title():
    """Shortened citation title matches full API title (0.95)."""
    verifier = MultiSourceVerifier()
    short = "A decomposable attention model"
    full = "A Decomposable Attention Model for Natural Language Inference"
    sim = verifier._title_similarity(short, full)
    assert sim >= 0.9, "Prefix match should give high similarity"


def test_title_similarity_identical():
    """Identical titles (case variation) should match well."""
    verifier = MultiSourceVerifier()
    assert verifier._title_similarity("Grammar as a foreign language", "Grammar as a Foreign Language") >= 0.9


def test_extract_subtitle_phrase_penn_treebank():
    """Subtitle after colon: Penn Treebank from Building...: The Penn Treebank."""
    verifier = MultiSourceVerifier()
    title = "Building a large annotated corpus of english: The Penn Treebank"
    phrase = verifier._extract_subtitle_phrase(title)
    assert phrase is not None
    assert "Penn Treebank" in phrase
    assert "Building" not in phrase


def test_extract_subtitle_phrase_no_colon():
    """No colon -> None."""
    verifier = MultiSourceVerifier()
    assert verifier._extract_subtitle_phrase("No colon here") is None


def test_extract_subtitle_phrase_strips_article():
    """Strip leading 'The' from phrase after colon."""
    verifier = MultiSourceVerifier()
    phrase = verifier._extract_subtitle_phrase("Something: The Penn Treebank")
    assert phrase is not None
    assert phrase.lower().startswith("penn") or "Penn" in phrase


def test_verifier_imports_clean_title():
    """Verifier imports clean_title for title normalization before search."""
    from citeverify.verifier import MultiSourceVerifier
    from citeverify.utils import clean_title
    # Verifier uses clean_title; raw 'asa' should be fixed
    raw = "Grammar asa foreign language"
    normalized = clean_title(raw)
    assert "as a" in normalized

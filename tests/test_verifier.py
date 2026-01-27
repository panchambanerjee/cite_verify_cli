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
    assert verifier._title_similarity("Hello World", "Hello World") == 1.0
    assert verifier._title_similarity("Hello", "World") < 0.5
    assert verifier._title_similarity("", "Something") == 0.0

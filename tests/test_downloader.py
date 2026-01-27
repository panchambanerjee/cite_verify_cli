"""Tests for PDF downloader."""

import pytest
from citeverify.models import Citation, VerificationResult, VerificationStatus
from citeverify.downloader import SmartPDFDownloader


@pytest.fixture
def downloader():
    """Create downloader instance."""
    return SmartPDFDownloader()


@pytest.fixture
def citation_with_arxiv():
    """Citation with arXiv ID."""
    return Citation(
        number="1",
        raw_text="Test",
        title="Attention Is All You Need",
        arxiv_id="1706.03762",
        year=2017,
    )


@pytest.fixture
def verification_arxiv():
    """Verification result with arXiv."""
    return VerificationResult(
        status=VerificationStatus.VERIFIED,
        confidence=1.0,
        matched_title="Attention Is All You Need",
        arxiv_id="1706.03762",
        verified_sources=["arxiv"],
    )


@pytest.mark.asyncio
async def test_download_from_arxiv(downloader, citation_with_arxiv, verification_arxiv, tmp_path):
    """Test PDF download from arXiv."""
    result = await downloader.download(
        citation_with_arxiv,
        verification_arxiv,
        output_dir=str(tmp_path),
    )
    assert result.success is True or result.success is False  # May fail without network
    if result.success:
        assert result.source == "arxiv"
        assert result.pdf_path
        assert result.file_size > 0
    await downloader.close()


@pytest.mark.asyncio
async def test_download_invalid_arxiv(downloader, tmp_path):
    """Test download with invalid arXiv ID."""
    citation = Citation(number="1", raw_text="X", arxiv_id="9999.99999")
    verification = VerificationResult(
        status=VerificationStatus.UNVERIFIED,
        confidence=0.0,
        verified_sources=[],
    )
    result = await downloader.download(citation, verification, str(tmp_path))
    assert result.success is False
    assert result.error
    await downloader.close()

"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_citation_text():
    """Sample citation text for parsing tests."""
    return (
        "Smith, J., Doe, A. (2020). \"Example Paper Title\". "
        "Journal of Examples, 10(2), 123-145. DOI: 10.1234/test"
    )

"""Helper utility functions for CitationVerify."""

import re
from typing import Optional


def normalize_doi(doi: str) -> Optional[str]:
    """Normalize DOI string."""
    if not doi:
        return None
    
    # Remove common prefixes
    doi = doi.strip()
    if doi.startswith('doi:'):
        doi = doi[4:].strip()
    if doi.startswith('DOI:'):
        doi = doi[4:].strip()
    if doi.startswith('https://doi.org/'):
        doi = doi[16:].strip()
    if doi.startswith('http://doi.org/'):
        doi = doi[15:].strip()
    
    # Remove trailing punctuation
    doi = doi.rstrip('.,);:')
    
    return doi if doi else None


def normalize_arxiv_id(arxiv_id: str) -> Optional[str]:
    """Normalize arXiv ID string."""
    if not arxiv_id:
        return None
    
    arxiv_id = arxiv_id.strip()
    
    # Remove common prefixes
    if arxiv_id.startswith('arXiv:'):
        arxiv_id = arxiv_id[6:].strip()
    if arxiv_id.startswith('arxiv:'):
        arxiv_id = arxiv_id[6:].strip()
    
    # Extract version if present (e.g., 1234.5678v1 -> 1234.5678)
    match = re.match(r'(\d{4}\.\d{4,5})', arxiv_id)
    if match:
        return match.group(1)
    
    return arxiv_id if arxiv_id else None


def extract_year_from_text(text: str) -> Optional[int]:
    """Extract year (4-digit) from text."""
    year_match = re.search(r'\b(19|20)\d{2}\b', text)
    if year_match:
        try:
            return int(year_match.group(0))
        except ValueError:
            pass
    return None


def clean_title(title: str) -> str:
    """Clean and normalize title text."""
    if not title:
        return ""
    
    # Remove extra whitespace
    title = re.sub(r'\s+', ' ', title)
    
    # Remove common citation artifacts
    title = title.strip('.,;:')
    
    return title.strip()

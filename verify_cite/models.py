"""Pydantic data models for CitationVerify."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum


class VerificationStatus(str, Enum):
    """Status of citation verification."""
    VERIFIED = "verified"
    PARTIAL = "partial"
    UNVERIFIED = "unverified"
    ERROR = "error"


class Citation(BaseModel):
    """Extracted citation from paper."""
    number: str
    raw_text: str
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    url: Optional[str] = None
    journal: Optional[str] = None
    manual: bool = False  # User-added citation


class VerificationResult(BaseModel):
    """Result from verifying a citation."""
    status: VerificationStatus
    confidence: float = Field(ge=0.0, le=1.0)
    matched_title: Optional[str] = None
    matched_authors: Optional[List[str]] = None
    matched_year: Optional[int] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    verified_sources: List[str] = Field(default_factory=list)
    discrepancies: List[str] = Field(default_factory=list)
    metadata: Dict = Field(default_factory=dict)


class QualityScore(BaseModel):
    """Quality score breakdown."""
    total: int = Field(ge=0, le=100)
    verification: int = Field(ge=0, le=25)
    peer_review: int = Field(ge=0, le=20)
    recency: int = Field(ge=0, le=15)
    citations: int = Field(ge=0, le=15)
    accessibility: int = Field(ge=0, le=15)
    venue: int = Field(ge=0, le=10)
    explanation: str = ""


class PDFDownloadResult(BaseModel):
    """Result from downloading a PDF."""
    success: bool
    pdf_path: Optional[str] = None
    source: Optional[str] = None
    file_size: int = 0
    error: Optional[str] = None


class VerifiedCitation(Citation):
    """Citation with verification and quality info."""
    verification: Optional[VerificationResult] = None
    quality_score: Optional[QualityScore] = None
    pdf_download: Optional[PDFDownloadResult] = None

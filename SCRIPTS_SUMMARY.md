# CitationVerify - Scripts and Modules Summary

Complete documentation of all scripts, modules, and their dependencies in the CitationVerify package.

---

## Package Structure

```
citeverify/
├── __init__.py          # Package initialization
├── cli.py               # Main CLI entry point
├── extractor.py         # Citation extraction from PDFs/arXiv
├── verifier.py          # Multi-source citation verification
├── scorer.py            # Quality scoring system
├── downloader.py        # PDF download functionality
├── formatter.py         # Output formatting (table, JSON, markdown)
├── models.py            # Pydantic data models
└── utils.py             # Utility functions
```

---

## Core Modules

### 1. `__init__.py`
**Purpose:** Package initialization and version definition

**Dependencies:**
- None (standard library only)

**Exports:**
- `__version__ = "0.1.0"`

**Lines of Code:** ~3

---

### 2. `cli.py` - Main CLI Interface
**Purpose:** Command-line interface entry point using Click framework

**Dependencies:**
- **External:**
  - `click` - CLI framework
  - `rich` - Terminal formatting (Console, Progress, SpinnerColumn, BarColumn, TextColumn)
  - `python-dotenv` - Environment variable loading
- **Internal:**
  - `.extractor.CitationExtractor`
  - `.verifier.MultiSourceVerifier`
  - `.downloader.SmartPDFDownloader`
  - `.scorer.CitationQualityScorer`
  - `.formatter` (display_summary, display_table, display_json, display_markdown)
  - `.models.Citation, VerifiedCitation`
- **Standard Library:**
  - `asyncio` - Async execution
  - `re` - Regular expressions
  - `time` - Timing
  - `pathlib.Path` - Path handling
  - `typing.List` - Type hints

**Key Functions:**
- `main()` - Click command entry point
- `run_pipeline()` - Async processing pipeline

**CLI Arguments:**
- `input_path` - PDF file or arXiv ID/URL
- `--verbose, -v` - Detailed progress
- `--output, -o` - Output directory
- `--format, -f` - Output format (table/json/markdown)
- `--no-verify` - Skip verification
- `--no-download` - Skip PDF downloads
- `--quality-min` - Minimum quality score filter

**Lines of Code:** ~235

---

### 3. `extractor.py` - Citation Extraction
**Purpose:** Extract citations from PDF files and arXiv papers

**Dependencies:**
- **External:**
  - `pdfplumber` - PDF text extraction
  - `arxiv` - arXiv API client (for arXiv extraction)
- **Internal:**
  - `.models.Citation`
  - `.utils` (normalize_doi, normalize_arxiv_id, extract_year_from_text, clean_title)
- **Standard Library:**
  - `re` - Regular expressions for parsing
  - `tempfile` - Temporary file handling
  - `os` - File operations
  - `typing.List, Tuple` - Type hints

**Key Classes:**
- `CitationExtractor` - Main extraction class

**Key Methods:**
- `extract_from_pdf(pdf_path)` - Extract from PDF file
- `extract_from_arxiv(arxiv_id)` - Extract from arXiv paper
- `_extract_text()` - Extract text from PDF
- `_extract_title()` - Extract paper title
- `_find_references_section()` - Locate references section
- `_parse_citations()` - Parse individual citations
- `_parse_single_citation()` - Parse one citation string

**Lines of Code:** ~260

---

### 4. `verifier.py` - Multi-Source Verification
**Purpose:** Verify citations across multiple academic databases

**Dependencies:**
- **External:**
  - `aiohttp` - Async HTTP client for API calls
  - `arxiv` - arXiv API client
- **Internal:**
  - `.models.Citation, VerificationResult, VerificationStatus`
  - `.utils` (normalize_doi, normalize_arxiv_id)
- **Standard Library:**
  - `asyncio` - Async operations and semaphores
  - `difflib.SequenceMatcher` - Title similarity matching
  - `typing.Optional` - Type hints

**Key Classes:**
- `MultiSourceVerifier` - Main verification class

**Key Methods:**
- `verify(citation)` - Main verification method (3-tier priority)
- `_verify_via_crossref_doi()` - DOI lookup via CrossRef
- `_verify_via_arxiv()` - arXiv ID lookup
- `_search_crossref()` - Title search in CrossRef
- `_search_semantic_scholar()` - Title search in Semantic Scholar
- `_title_similarity()` - Calculate title similarity (0-1)
- `_find_discrepancies()` - Detect year mismatches
- `close()` - Close HTTP session

**API Endpoints Used:**
- `https://api.crossref.org/works/{doi}` - DOI lookup
- `https://api.crossref.org/works?query={title}` - Title search
- `https://api.semanticscholar.org/graph/v1/paper/search` - Semantic Scholar search
- arXiv API (via `arxiv` library)

**Rate Limiting:**
- CrossRef: 5 requests/second (semaphore)
- arXiv: 3 requests/second (semaphore)

**Lines of Code:** ~378

---

### 5. `scorer.py` - Quality Scoring
**Purpose:** Calculate quality scores across 6 dimensions

**Dependencies:**
- **Internal:**
  - `.models.Citation, VerificationResult, QualityScore, VerificationStatus`
- **Standard Library:**
  - `datetime` - Year calculations

**Key Classes:**
- `CitationQualityScorer` - Main scoring class

**Key Methods:**
- `score(citation, verification)` - Main scoring method
- `_score_verification()` - Verification quality (25 pts)
- `_score_peer_review()` - Peer review status (20 pts)
- `_score_recency()` - Paper age (15 pts)
- `_score_citations()` - Citation count/impact (15 pts)
- `_score_accessibility()` - Open access availability (15 pts)
- `_score_venue()` - Publication venue quality (10 pts)
- `_generate_explanation()` - Human-readable explanation

**Scoring Breakdown:**
- Total: 100 points
- Verification: 0-25 points
- Peer Review: 5-20 points
- Recency: 3-15 points
- Citations: 0-15 points
- Accessibility: 5-15 points
- Venue: 5-10 points

**Lines of Code:** ~225

---

### 6. `downloader.py` - PDF Download
**Purpose:** Download PDFs with intelligent fallback strategies

**Dependencies:**
- **External:**
  - `aiohttp` - Async HTTP client
  - `python-dotenv` - Environment variables
  - `arxiv` - arXiv API client
  - `PyPDF2` - PDF validation
- **Internal:**
  - `.models.Citation, VerificationResult, PDFDownloadResult`
  - `.utils` (normalize_doi, normalize_arxiv_id)
- **Standard Library:**
  - `asyncio` - Async operations
  - `os` - File operations
  - `pathlib.Path` - Path handling
  - `typing.Optional` - Type hints

**Key Classes:**
- `SmartPDFDownloader` - Main downloader class

**Key Methods:**
- `download(citation, verification, output_dir)` - Main download method
- `_download_from_arxiv()` - Download from arXiv
- `_download_from_unpaywall()` - Download via Unpaywall API
- `_download_from_url()` - Generic URL download
- `_is_valid_pdf()` - Validate downloaded PDF
- `close()` - Close HTTP session

**Download Priority:**
1. arXiv (if arXiv ID exists)
2. Unpaywall (if DOI exists)
3. Semantic Scholar (if open access PDF available)

**API Endpoints Used:**
- `https://api.unpaywall.org/v2/{doi}` - Unpaywall API
- arXiv PDF URLs
- Semantic Scholar open access PDFs

**Environment Variables:**
- `UNPAYWALL_EMAIL` - Required for Unpaywall API

**Lines of Code:** ~200

---

### 7. `formatter.py` - Output Formatting
**Purpose:** Format and display results in multiple formats

**Dependencies:**
- **External:**
  - `rich` - Terminal formatting (Console, Table, Progress components)
- **Internal:**
  - `.models.VerifiedCitation, VerificationStatus`
- **Standard Library:**
  - `json` - JSON serialization
  - `typing.List` - Type hints

**Key Functions:**
- `display_summary(citations)` - Summary statistics table
- `display_table(citations)` - Detailed citation table
- `display_json(citations)` - JSON output
- `display_markdown(citations, paper_title)` - Markdown output
- `get_stars(score)` - Convert score to star rating

**Output Formats:**
- **Table:** Rich terminal tables with colors and formatting
- **JSON:** Structured JSON for programmatic use
- **Markdown:** Markdown tables for documentation

**Lines of Code:** ~150

---

### 8. `models.py` - Data Models
**Purpose:** Pydantic data models for type safety and validation

**Dependencies:**
- **External:**
  - `pydantic` - Data validation and serialization
- **Standard Library:**
  - `typing` (List, Optional, Dict)
  - `enum.Enum` - Status enums

**Key Classes:**
- `VerificationStatus` (Enum) - Verification status values
- `Citation` - Extracted citation data
- `VerificationResult` - Verification results
- `QualityScore` - Quality score breakdown
- `PDFDownloadResult` - PDF download results
- `VerifiedCitation` - Complete citation with verification

**Model Fields:**
- All models use Pydantic Field validation
- Type hints for all fields
- Default values and factories
- Validation constraints (ge, le for scores)

**Lines of Code:** ~80

---

### 9. `utils.py` - Utility Functions
**Purpose:** Helper functions for data normalization and parsing

**Dependencies:**
- **Standard Library:**
  - `re` - Regular expressions
  - `typing.Optional` - Type hints

**Key Functions:**
- `normalize_doi(doi)` - Normalize DOI strings
- `normalize_arxiv_id(arxiv_id)` - Normalize arXiv IDs
- `extract_year_from_text(text)` - Extract year from text
- `clean_title(title)` - Clean and normalize titles

**Lines of Code:** ~60

---

## Test Modules

### `tests/__init__.py`
**Purpose:** Test package initialization

### `tests/conftest.py`
**Purpose:** Pytest configuration and shared fixtures

**Fixtures:**
- `sample_citation_text` - Sample citation for parsing tests

### `tests/test_extractor.py`
**Purpose:** Tests for citation extraction

**Test Functions:**
- `test_parse_single_citation()` - Test citation parsing
- `test_parse_doi()` - Test DOI extraction
- `test_parse_arxiv_id()` - Test arXiv ID extraction
- `test_extract_from_pdf_missing_file()` - Test error handling

### `tests/test_verifier.py`
**Purpose:** Tests for verification functionality

**Test Functions:**
- `test_verify_via_doi()` - Test DOI verification
- `test_verify_unverified_citation()` - Test unverified citations
- `test_title_similarity()` - Test similarity algorithm

### `tests/test_downloader.py`
**Purpose:** Tests for PDF downloading

**Test Functions:**
- `test_download_from_arxiv()` - Test arXiv downloads
- `test_download_invalid_arxiv()` - Test error handling

---

## External Dependencies Summary

### Core Dependencies (from pyproject.toml)
1. **click>=8.1.0** - CLI framework
2. **rich>=13.0.0** - Terminal formatting
3. **pdfplumber>=0.11.0** - PDF text extraction
4. **arxiv>=2.1.0** - arXiv API client
5. **habanero>=1.2.6** - CrossRef client (optional, using direct HTTP)
6. **aiohttp>=3.9.0** - Async HTTP client
7. **pydantic>=2.6.0** - Data validation
8. **python-dotenv>=1.0.0** - Environment variables
9. **PyPDF2>=3.0.0** - PDF validation

### Development Dependencies
1. **pytest>=8.0.0** - Testing framework
2. **pytest-asyncio>=0.23.0** - Async test support
3. **black>=24.0.0** - Code formatter
4. **ruff>=0.1.0** - Linter

---

## Module Dependencies Graph

```
cli.py
├── extractor.py
│   ├── models.py
│   └── utils.py
├── verifier.py
│   ├── models.py
│   └── utils.py
├── scorer.py
│   └── models.py
├── downloader.py
│   ├── models.py
│   └── utils.py
├── formatter.py
│   └── models.py
└── models.py (shared by all)
```

---

## Data Flow

```
User Input
    ↓
cli.py (parse arguments)
    ↓
extractor.py (extract citations)
    → models.Citation
    ↓
verifier.py (verify citations)
    → models.VerificationResult
    ↓
scorer.py (calculate scores)
    → models.QualityScore
    ↓
downloader.py (optional - download PDFs)
    → models.PDFDownloadResult
    ↓
formatter.py (display results)
    → Terminal/JSON/Markdown output
```

---

## API Integrations

### 1. CrossRef API
- **Base URL:** `https://api.crossref.org`
- **Endpoints:**
  - `/works/{doi}` - DOI lookup
  - `/works?query={title}` - Title search
- **Rate Limit:** 5 req/sec
- **Authentication:** None required

### 2. arXiv API
- **Library:** `arxiv` Python package
- **Rate Limit:** 3 req/sec
- **Authentication:** None required

### 3. Semantic Scholar API
- **Base URL:** `https://api.semanticscholar.org/graph/v1`
- **Endpoint:** `/paper/search`
- **Rate Limit:** No strict limit (reasonable use)
- **Authentication:** None required

### 4. Unpaywall API
- **Base URL:** `https://api.unpaywall.org/v2`
- **Endpoint:** `/{doi}?email={email}`
- **Rate Limit:** Reasonable use
- **Authentication:** Email required (via environment variable)

---

## Total Lines of Code

- **Core Modules:** ~1,600 lines
- **Test Modules:** ~200 lines
- **Total:** ~1,800 lines

---

## Entry Point

**CLI Command:** `citeverify`
**Entry Point:** `citeverify.cli:main`
**Defined in:** `pyproject.toml` → `[project.scripts]`

---

## Environment Variables

- `UNPAYWALL_EMAIL` - Email for Unpaywall API (optional but recommended)

---

## Build System

- **Build Backend:** hatchling
- **Package Format:** Wheel + Source Distribution
- **Python Version:** >=3.9

---

This document provides a complete overview of all scripts, modules, dependencies, and their relationships in the CitationVerify package.

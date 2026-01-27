# CitationVerify

**Verify citations in research papers from the command line.**

CitationVerify extracts citations from research papers (PDF or arXiv), verifies them across multiple academic databases, scores their quality, and optionally downloads the cited PDFs.

## Features

- 📄 **Extract citations** from PDFs or arXiv papers
- ✅ **Verify citations** across multiple sources (CrossRef, arXiv, Semantic Scholar)
- 📊 **Quality scoring** across 6 dimensions (verification, peer review, recency, citations, accessibility, venue)
- 📥 **Download PDFs** with intelligent fallback (arXiv → Unpaywall → Semantic Scholar)
- 🎨 **Beautiful output** with rich terminal formatting (table, JSON, markdown)

## Installation

### Prerequisites

- Python 3.9 or higher
- pip

### Setup

1. **Clone or navigate to the project directory:**
   ```bash
   cd /Users/panchamb/Documents/Projects/micro_saas/cite_verify_cli
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install the package in development mode:**
   ```bash
   pip install -e .
   ```

   Or install with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. **Configure environment variables (optional):**
   ```bash
   cp .env.example .env
   # Edit .env and add your Unpaywall email
   ```

   The `.env` file should contain:
   ```env
   UNPAYWALL_EMAIL=your-email@example.com
   ```

## Usage

### Basic Usage

Verify citations in a PDF:
```bash
citeverify paper.pdf
```

Verify citations from an arXiv paper:
```bash
citeverify https://arxiv.org/abs/1706.03762
# or
citeverify 1706.03762
```

### Options

```bash
citeverify [OPTIONS] INPUT_PATH

Options:
  -v, --verbose          Show detailed progress
  -o, --output PATH      Output directory for PDFs (default: ./citations)
  -f, --format FORMAT    Output format: table, json, markdown (default: table)
  --no-verify           Skip verification step
  --no-download         Skip PDF downloads
  --quality-min INT     Minimum quality score to display (0-100)
  --help                Show help message
```

### Examples

**Download PDFs to a custom directory:**
```bash
citeverify paper.pdf --output ./references
```

**Export results as JSON:**
```bash
citeverify paper.pdf --format json > results.json
```

**Export as markdown:**
```bash
citeverify paper.pdf --format markdown > report.md
```

**Only show high-quality citations (score >= 80):**
```bash
citeverify paper.pdf --quality-min 80
```

**Extract citations only (no verification):**
```bash
citeverify paper.pdf --no-verify
```

**Verify without downloading PDFs:**
```bash
citeverify paper.pdf --no-download
```

## Project Structure

```
citeverify/
├── citeverify/
│   ├── __init__.py
│   ├── cli.py              # Main CLI interface
│   ├── extractor.py        # Citation extraction
│   ├── verifier.py         # Multi-source verification
│   ├── downloader.py       # PDF downloads
│   ├── scorer.py           # Quality scoring
│   ├── formatter.py        # Output formatters
│   ├── models.py           # Pydantic data models
│   └── utils.py            # Helper functions
├── tests/
│   ├── __init__.py
│   ├── test_extractor.py
│   ├── test_verifier.py
│   ├── test_downloader.py
│   └── fixtures/
├── pyproject.toml
├── README.md
├── .env.example
└── .gitignore
```

## Quality Scoring

Citations are scored across 6 dimensions (total: 100 points):

- **Verification** (25 pts): How well the citation was verified
- **Peer Review** (20 pts): Whether the paper is peer-reviewed
- **Recency** (15 pts): How recent the paper is
- **Citations** (15 pts): Citation count/impact
- **Accessibility** (15 pts): Open access availability
- **Venue** (10 pts): Quality of publication venue

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black citeverify/ tests/
ruff check citeverify/ tests/
```

### Building the Package

```bash
pip install build
python -m build
```

## Troubleshooting

**"Could not find references section"**
- The PDF may not have a clearly marked references section
- Try using a different PDF or manually extracting citations

**"PDF not available from any source"**
- The paper may be behind a paywall
- Check if the paper has an arXiv version
- Some papers are not available as open access

**Rate limiting errors**
- The tool respects API rate limits
- If you see rate limit errors, wait a few seconds and try again

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Next Steps

- [ ] Add GROBID integration for better extraction
- [ ] Add interactive review mode
- [ ] Add configuration file support
- [ ] Add caching to avoid re-verification
- [ ] Add batch processing
- [ ] Add export to BibTeX
- [ ] Publish to PyPI

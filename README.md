# verify-cite

**Verify citations in research papers from the command line.**

`verify-cite` extracts citations from research papers (PDF or arXiv), verifies them across multiple academic databases, scores their quality, and optionally downloads the cited PDFs.

Tutorial with experiment results and roadmap: [docs/tutorial.md](docs/tutorial.md)

## Features

- **Extract citations** from PDFs or arXiv papers
- **Verify citations** across CrossRef, arXiv, Semantic Scholar, and OpenAlex
- **Quality scoring** across 6 dimensions (verification, peer review, recency, citations, accessibility, venue)
- **Download PDFs** with intelligent fallback (arXiv → Unpaywall → Semantic Scholar)
- **Rich terminal output** (table, JSON, markdown, BibTeX)
- **Configurable threshold** for title similarity matching
- **SQLite caching** to avoid re-querying APIs
- **BibTeX export** for verified citations

## Installation

Requires Python 3.9+.

```bash
pip install verify-cite
```

Optional: set an email for Unpaywall PDF downloads:

```bash
# copy into your working directory or export in the shell
export UNPAYWALL_EMAIL=your-email@example.com
```

See `.env.example` for a dotenv template.

### Development install

```bash
git clone https://github.com/panchambanerjee/cite_verify_cli.git
cd cite_verify_cli
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Usage

### Basic usage

```bash
verify-cite paper.pdf
verify-cite https://arxiv.org/abs/1706.03762
verify-cite 1706.03762
```

### Options

```bash
verify-cite [OPTIONS] INPUT_PATH

Options:
  -v, --verbose          Show detailed verification logs (why citations fail)
  -o, --output PATH      Output directory for PDFs and exports (default: ./citations)
  -f, --format FORMAT    Output format: table, json, markdown, bibtex (default: table)
  -t, --threshold FLOAT  Title similarity threshold 0.0-1.0 (default: 0.7)
  --no-verify           Skip verification step
  --no-download         Skip PDF downloads
  --no-cache            Disable caching (re-query all APIs)
  --clear-cache         Clear cache before running
  --export-bibtex PATH  Export verified citations to BibTeX file
  --quality-min INT     Minimum quality score to display (0-100)
  --help                Show help message
```

### Examples

```bash
verify-cite paper.pdf --output ./references
verify-cite paper.pdf --format json > results.json
verify-cite paper.pdf --format markdown > report.md
verify-cite paper.pdf --quality-min 80
verify-cite paper.pdf --no-verify
verify-cite paper.pdf --no-download
verify-cite paper.pdf --format bibtex > refs.bib
verify-cite paper.pdf --export-bibtex ./references.bib
verify-cite paper.pdf --threshold 0.6
verify-cite paper.pdf --verbose
verify-cite paper.pdf --no-cache
```

## Project structure

```
verify_cite/
├── __init__.py
├── cli.py              # Main CLI interface
├── extractor.py        # Citation extraction
├── verifier.py         # Multi-source verification with caching
├── downloader.py       # PDF downloads
├── scorer.py           # Quality scoring
├── formatter.py        # Output formatters (table, JSON, markdown, BibTeX)
├── cache.py            # SQLite caching for API results
├── models.py           # Pydantic data models
└── utils.py            # Helper functions
```

Python import: `import verify_cite`. Console command: `verify-cite`.

## Edge cases handled

**Extraction (from PDF text):**
- Concatenated phrases – Spaces dropped at line breaks: "Grammar asa foreign language" → "Grammar as a foreign language"
- Year in page ranges – Skips 1929 in "15(1):1929–1958" and correctly extracts 2014
- Unicode author names – Recognizes names like Łukasz, Óscar, etc.
- Venue delimiters – Handles "Title. In International Conference..." and missing spaces
- Venue-like rejection – Avoids treating venue text as the paper title
- Leading reference numbers – Strips "[17]" from citation text before parsing
- Compound words – Preserves "overfitting"
- Hyphenated line breaks – Joins "im- age" → "image"

**Verification:**
- Title normalization – Applies `clean_title` before search
- Shortened titles – Prefix match for abbreviated citation titles
- Subtitle fallback – Retries with part after colon
- Title + venue fallback – Retries with title + venue words when venue is known
- VERIFIED threshold – Similarity ≥ 0.75 marks as VERIFIED (not just PARTIAL)

## Quality scoring

Citations are scored across 6 dimensions (total: 100 points):

- **Verification** (25 pts): How well the citation was verified
- **Peer Review** (20 pts): Whether the paper is peer-reviewed
- **Recency** (15 pts): How recent the paper is
- **Citations** (15 pts): Citation count/impact
- **Accessibility** (15 pts): Open access availability
- **Venue** (10 pts): Quality of publication venue

## Development

```bash
pytest
black verify_cite/ tests/
ruff check verify_cite/ tests/
pip install build twine
python -m build
twine check dist/*
```

## Troubleshooting

**"Could not find references section"**
- The PDF may not have a clearly marked references section
- Try a different PDF or extract citations manually

**"PDF not available from any source"**
- The paper may be behind a paywall
- Check whether an arXiv version exists

**Rate limiting**
- The tool respects API rate limits; wait briefly and retry

## License

MIT

## Contributing

Contributions are welcome. Please open a pull request.

## Roadmap

- [x] Caching to avoid re-verification
- [x] Export to BibTeX
- [x] Verbose logging for debugging
- [x] Configurable similarity threshold
- [x] OpenAlex as an additional verification source
- [ ] GROBID integration for better extraction
- [ ] Interactive review mode
- [ ] Configuration file support
- [ ] Batch processing
- [ ] Publish to PyPI (`twine upload dist/*` once a token is available)

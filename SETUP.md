# Setup Instructions for verify-cite

This guide walks you through setting up the verify-cite CLI from scratch.

## Step-by-step setup

### 1. Navigate to the project directory

```bash
cd /path/to/cite_verify_cli
```

### 2. Create a virtual environment

**macOS/Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt after activation.

### 3. Upgrade pip (recommended)

```bash
pip install --upgrade pip
```

### 4. Install the package

```bash
pip install -e .
```

Or with development dependencies:

```bash
pip install -e ".[dev]"
```

### 5. Verify installation

```bash
verify-cite --help
```

### 6. Configure environment variables (optional)

```bash
cp .env.example .env
```

Edit `.env`:

```env
UNPAYWALL_EMAIL=your-email@example.com
```

Unpaywall requires an email for API access. It is used only for PDF download lookups by DOI.

### 7. Run tests

```bash
pytest tests/ -v
```

## Quick start

```bash
verify-cite 1706.03762 --no-download
```

This will:

1. Download the arXiv paper PDF temporarily
2. Extract citations
3. Verify them across multiple databases
4. Score their quality
5. Display results in a table

## Troubleshooting

### "Command not found: verify-cite"

1. Make sure the virtual environment is activated
2. Reinstall: `pip install -e .`
3. Confirm the venv `bin` directory is on your `PATH`

### Import errors

1. Stay inside the activated venv
2. Reinstall: `pip install -e .`
3. Check dependencies: `pip list`

## Development workflow

Editable installs pick up code changes immediately. Restart the CLI command after edits.

```bash
pytest
pytest -v
pytest tests/test_extractor.py
black verify_cite/ tests/
ruff check verify_cite/ tests/
ruff check --fix verify_cite/ tests/
```

## Deactivate

```bash
deactivate
```

## Next steps

- Read [README.md](README.md) for usage examples
- Read [docs/tutorial.md](docs/tutorial.md) for experiments and roadmap
- Try verifying citations from your own PDFs

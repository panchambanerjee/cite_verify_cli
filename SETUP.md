# Setup Instructions for CitationVerify

This guide will walk you through setting up the CitationVerify CLI tool from scratch.

## Step-by-Step Setup

### 1. Navigate to Project Directory

```bash
cd /Users/panchamb/Documents/Projects/micro_saas/cite_verify_cli
```

### 2. Create Virtual Environment

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt after activation.

### 3. Upgrade pip (Recommended)

```bash
pip install --upgrade pip
```

### 4. Install the Package

**Install in development mode:**
```bash
pip install -e .
```

This installs the package in "editable" mode, so changes to the code are immediately available.

**Or install with development dependencies:**
```bash
pip install -e ".[dev]"
```

This includes testing and linting tools (pytest, black, ruff).

### 5. Verify Installation

Check that the CLI command is available:
```bash
citeverify --help
```

You should see the help message for CitationVerify.

### 6. Configure Environment Variables (Optional but Recommended)

Create a `.env` file from the example:
```bash
cp .env.example .env
```

Edit `.env` and add your email for Unpaywall API:
```env
UNPAYWALL_EMAIL=your-email@example.com
```

**Note:** Unpaywall requires an email address for API access. This helps them track usage and contact you if needed. Your email is not shared publicly.

### 7. Test the Installation

Run a simple test to verify everything works:
```bash
pytest tests/ -v
```

## Quick Start Example

Once installed, try verifying citations from an arXiv paper:

```bash
citeverify 1706.03762
```

This will:
1. Download the arXiv paper
2. Extract citations
3. Verify them across multiple databases
4. Score their quality
5. Display results in a beautiful table

## Troubleshooting

### "Command not found: citeverify"

If the command is not found after installation:
1. Make sure the virtual environment is activated
2. Try reinstalling: `pip install -e .`
3. Check that `~/.local/bin` or the venv's bin directory is in your PATH

### Import Errors

If you see import errors:
1. Make sure you're in the virtual environment
2. Reinstall: `pip install -e .`
3. Check that all dependencies are installed: `pip list`

### Missing Dependencies

If you get errors about missing packages:
```bash
pip install -e ".[dev]"
```

This installs all required dependencies.

## Development Workflow

### Making Changes

Since the package is installed in editable mode (`-e`), any changes you make to the code are immediately available. Just restart the CLI command.

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_extractor.py
```

### Code Formatting

```bash
# Format code with black
black citeverify/ tests/

# Check code style with ruff
ruff check citeverify/ tests/

# Auto-fix issues
ruff check --fix citeverify/ tests/
```

## Deactivating Virtual Environment

When you're done working, deactivate the virtual environment:

```bash
deactivate
```

## Next Steps

- Read the [README.md](README.md) for usage examples
- Try verifying citations from your own PDFs
- Explore the different output formats (table, JSON, markdown)
- Check out the quality scoring system

## Need Help?

- Check the README.md for detailed usage instructions
- Review the test files for examples of how components work
- Check the code comments for implementation details

# Quick Installation Guide

## Prerequisites
- Python 3.9+
- pip

## Installation Steps

1. **Navigate to project directory:**
   ```bash
   cd /Users/panchamb/Documents/Projects/micro_saas/cite_verify_cli
   ```

2. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # macOS/Linux
   # OR
   venv\Scripts\activate  # Windows
   ```

3. **Install package:**
   ```bash
   pip install -e .
   ```

4. **Verify installation:**
   ```bash
   citeverify --help
   ```

5. **Optional - Configure environment:**
   ```bash
   # Create .env file manually with:
   # UNPAYWALL_EMAIL=your-email@example.com
   ```

## Test Installation

```bash
# Run tests
pytest

# Try with an arXiv paper
citeverify 1706.03762 --no-download
```

## Troubleshooting

- **Command not found**: Make sure venv is activated
- **Import errors**: Run `pip install -e .` again
- **Missing dependencies**: Run `pip install -e ".[dev]"`

For detailed setup instructions, see [SETUP.md](SETUP.md).

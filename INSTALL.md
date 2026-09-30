# Quick Installation Guide

## Prerequisites

- Python 3.9+
- pip

## Installation

### From PyPI

```bash
pip install verify-cite
verify-cite --help
```

### From source (development)

1. Navigate to the project directory:

   ```bash
   cd /path/to/cite_verify_cli
   ```

2. Create and activate a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # macOS/Linux
   # OR
   venv\Scripts\activate  # Windows
   ```

3. Install the package:

   ```bash
   pip install -e .
   ```

4. Verify installation:

   ```bash
   verify-cite --help
   ```

5. Optional — configure Unpaywall:

   ```bash
   cp .env.example .env
   # set UNPAYWALL_EMAIL=your-email@example.com
   ```

## Test installation

```bash
pytest
verify-cite 1706.03762 --no-download
```

## Troubleshooting

- **Command not found**: Make sure the virtual environment is activated, or that `pip install verify-cite` completed successfully.
- **Import errors**: Re-run `pip install -e .` or `pip install verify-cite`.
- **Missing dependencies**: Run `pip install -e ".[dev]"`.

For detailed setup instructions, see [SETUP.md](SETUP.md). For a longer walkthrough, see [docs/tutorial.md](docs/tutorial.md).

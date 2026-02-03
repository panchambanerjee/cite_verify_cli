"""Main CLI interface for CitationVerify."""

import asyncio
import re
from dotenv import load_dotenv

load_dotenv()
import time
from pathlib import Path
from typing import List

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .extractor import CitationExtractor
from .verifier import MultiSourceVerifier
from .downloader import SmartPDFDownloader
from .scorer import CitationQualityScorer
from .formatter import (
    display_summary,
    display_table,
    display_json,
    display_markdown,
    display_bibtex,
    save_bibtex,
)
from .models import Citation, VerifiedCitation

console = Console()


@click.command()
@click.argument("input_path")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed verification logs")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="./citations",
    help="Output directory for PDFs and exports",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "json", "markdown", "bibtex"]),
    default="table",
    help="Output format",
)
@click.option("--no-verify", is_flag=True, help="Skip verification")
@click.option("--no-download", is_flag=True, help="Skip PDF downloads")
@click.option(
    "--quality-min",
    type=int,
    default=0,
    help="Minimum quality score to display",
)
@click.option(
    "--threshold",
    "-t",
    type=float,
    default=0.7,
    help="Title similarity threshold (0.0-1.0, default: 0.7)",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable caching (re-query all APIs)",
)
@click.option(
    "--clear-cache",
    is_flag=True,
    help="Clear cache before running",
)
@click.option(
    "--export-bibtex",
    type=click.Path(),
    help="Export verified citations to BibTeX file",
)
def main(
    input_path,
    verbose,
    output,
    format,
    no_verify,
    no_download,
    quality_min,
    threshold,
    no_cache,
    clear_cache,
    export_bibtex,
):
    """
    Verify citations in research papers.

    INPUT_PATH can be:
    - Path to PDF file
    - arXiv URL (https://arxiv.org/abs/...)
    - arXiv ID (2301.12345)

    Examples:
      citeverify paper.pdf
      citeverify https://arxiv.org/abs/2301.12345
      citeverify 2301.12345 --output ./refs
      citeverify paper.pdf --threshold 0.6 --verbose
      citeverify paper.pdf --format bibtex > refs.bib
    """
    from . import __version__
    from .cache import VerificationCache

    console.print(f"[bold blue]CitationVerify v{__version__}[/bold blue]")
    console.print("━" * 60)

    # Handle cache clearing
    if clear_cache:
        cache = VerificationCache()
        count = cache.clear()
        console.print(f"  Cleared {count} cache entries")

    # Validate threshold
    if not 0.0 <= threshold <= 1.0:
        console.print("[bold red]Error:[/bold red] Threshold must be between 0.0 and 1.0")
        raise click.Abort()

    if verbose:
        console.print(f"  Similarity threshold: {threshold}")
        console.print(f"  Caching: {'disabled' if no_cache else 'enabled'}")

    try:
        result = asyncio.run(
            run_pipeline(
                input_path=input_path,
                verify=not no_verify,
                download=not no_download,
                output_dir=output,
                verbose=verbose,
                quality_min=quality_min,
                threshold=threshold,
                use_cache=not no_cache,
            )
        )

        # Display results in requested format
        if format == "table":
            display_summary(result["citations"])
            display_table(result["citations"])
        elif format == "json":
            display_json(result["citations"])
        elif format == "markdown":
            display_markdown(result["citations"], result["paper_title"])
        elif format == "bibtex":
            display_bibtex(result["citations"], result["paper_title"])

        # Export BibTeX if requested
        if export_bibtex:
            count = save_bibtex(result["citations"], export_bibtex)
            console.print(f"  Exported {count} citations to {export_bibtex}")

        # Show cache stats in verbose mode
        if verbose and not no_cache:
            from .cache import VerificationCache
            cache = VerificationCache()
            stats = cache.stats()
            console.print(f"\n  Cache: {stats['valid_entries']} entries")

        console.print(f"\n✨ Done in {result['duration']}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        raise click.Abort()


async def run_pipeline(
    input_path: str,
    verify: bool,
    download: bool,
    output_dir: str,
    verbose: bool,
    quality_min: int,
    threshold: float = 0.7,
    use_cache: bool = True,
) -> dict:
    """Main processing pipeline."""
    start_time = time.time()

    # Determine input type
    if input_path.startswith("http") and "arxiv.org" in input_path:
        match = re.search(r"(\d{4}\.\d{4,5})", input_path)
        if not match:
            raise ValueError("Invalid arXiv URL")
        input_path = match.group(1)
        input_type = "arxiv"
    elif input_path.endswith(".pdf"):
        input_type = "pdf"
    else:
        input_type = "arxiv"

    # Verbose logging callback
    verbose_logs = []
    def log_callback(msg: str):
        if verbose:
            console.print(f"  [dim]{msg}[/dim]")
        verbose_logs.append(msg)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        extract_task = progress.add_task("Extracting citations...", total=100)
        extractor = CitationExtractor()

        if input_type == "pdf":
            citations, paper_title = extractor.extract_from_pdf(input_path)
        else:
            citations, paper_title = extractor.extract_from_arxiv(input_path)

        progress.update(extract_task, completed=100)
        console.print(f"  Extracted {len(citations)} citations")

        verified_citations: List[VerifiedCitation] = [
            VerifiedCitation(**c.model_dump()) for c in citations
        ]

        if verify:
            verify_task = progress.add_task(
                "Verifying citations...",
                total=len(verified_citations),
            )
            
            # Create verifier with threshold, caching, and verbose logging
            verifier = MultiSourceVerifier(
                threshold=threshold,
                use_cache=use_cache,
                verbose=verbose,
                log_callback=log_callback,
            )

            for citation in verified_citations:
                result = await verifier.verify(citation)
                citation.verification = result
                progress.update(verify_task, advance=1)

            await verifier.close()

            verified_count = sum(
                1
                for c in verified_citations
                if c.verification
                and c.verification.status.value == "verified"
            )
            partial_count = sum(
                1
                for c in verified_citations
                if c.verification
                and c.verification.status.value == "partial"
            )
            
            console.print(
                f"  Verified {verified_count}/{len(verified_citations)} citations"
                + (f" ({partial_count} partial)" if partial_count else "")
            )

        if verify:
            scorer = CitationQualityScorer()
            for citation in verified_citations:
                if citation.verification:
                    citation.quality_score = scorer.score(
                        citation, citation.verification
                    )

        if download:
            download_task = progress.add_task(
                "Downloading PDFs...",
                total=len(verified_citations),
            )
            downloader = SmartPDFDownloader()

            for citation in verified_citations:
                if citation.verification:
                    result = await downloader.download(
                        citation,
                        citation.verification,
                        output_dir,
                    )
                    citation.pdf_download = result
                progress.update(download_task, advance=1)

            await downloader.close()

            available = sum(
                1
                for c in verified_citations
                if c.pdf_download and c.pdf_download.success
            )
            console.print(
                f"  Downloaded {available}/{len(verified_citations)} PDFs"
            )

    if quality_min > 0:
        verified_citations = [
            c
            for c in verified_citations
            if c.quality_score and c.quality_score.total >= quality_min
        ]

    duration = f"{time.time() - start_time:.1f}s"

    return {
        "paper_title": paper_title,
        "citations": verified_citations,
        "duration": duration,
        "verbose_logs": verbose_logs,
    }


if __name__ == "__main__":
    main()

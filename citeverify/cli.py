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
)
from .models import Citation, VerifiedCitation

console = Console()


@click.command()
@click.argument("input_path")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed progress")
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="./citations",
    help="Output directory",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "json", "markdown"]),
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
def main(
    input_path,
    verbose,
    output,
    format,
    no_verify,
    no_download,
    quality_min,
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
    """
    from . import __version__

    console.print(f"[bold blue]CitationVerify v{__version__}[/bold blue]")
    console.print("━" * 60)

    try:
        result = asyncio.run(
            run_pipeline(
                input_path=input_path,
                verify=not no_verify,
                download=not no_download,
                output_dir=output,
                verbose=verbose,
                quality_min=quality_min,
            )
        )

        if format == "table":
            display_summary(result["citations"])
            display_table(result["citations"])
        elif format == "json":
            display_json(result["citations"])
        elif format == "markdown":
            display_markdown(result["citations"], result["paper_title"])

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
        console.print(f"  ✓ Extracted {len(citations)} citations")

        verified_citations: List[VerifiedCitation] = [
            VerifiedCitation(**c.model_dump()) for c in citations
        ]

        if verify:
            verify_task = progress.add_task(
                "Verifying citations...",
                total=len(verified_citations),
            )
            verifier = MultiSourceVerifier()

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
            console.print(
                f"  ✓ Verified {verified_count}/{len(verified_citations)} citations"
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
                f"  ✓ Downloaded {available}/{len(verified_citations)} PDFs"
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
    }


if __name__ == "__main__":
    main()

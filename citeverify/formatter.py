"""Output formatters for CitationVerify."""

import json
from typing import List
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from .models import VerifiedCitation, VerificationStatus

console = Console()


def display_summary(citations: List[VerifiedCitation]) -> None:
    """Display summary statistics."""
    total = len(citations)
    if total == 0:
        console.print("\n[bold]SUMMARY[/bold]")
        console.print("━" * 60)
        console.print("No citations to display.")
        return

    verified = sum(
        1
        for c in citations
        if c.verification
        and c.verification.status == VerificationStatus.VERIFIED
    )
    partial = sum(
        1
        for c in citations
        if c.verification
        and c.verification.status == VerificationStatus.PARTIAL
    )
    unverified = sum(
        1
        for c in citations
        if c.verification
        and c.verification.status == VerificationStatus.UNVERIFIED
    )

    avg_quality = (
        sum(c.quality_score.total for c in citations if c.quality_score)
        / total
        if total > 0
        else 0
    )
    pdfs_available = sum(
        1 for c in citations if c.pdf_download and c.pdf_download.success
    )

    console.print("\n[bold]SUMMARY[/bold]")
    console.print("━" * 60)
    console.print(f"Total Citations:        {total}")
    console.print(f"✓ Verified:            {verified} ({verified * 100 // total}%)")
    console.print(f"≈ Partial Match:        {partial} ({partial * 100 // total}%)")
    console.print(f"✗ Unverified:           {unverified} ({unverified * 100 // total}%)")
    console.print(
        f"\nOverall Quality:        {int(avg_quality)}/100 {get_stars(avg_quality)}"
    )
    console.print(
        f"\nPDFs Available:         {pdfs_available}/{total} "
        f"({pdfs_available * 100 // total}%)"
    )


def display_table(citations: List[VerifiedCitation]) -> None:
    """Display citations as rich table."""
    console.print("\n[bold]CITATION DETAILS[/bold]")
    console.print("━" * 60)

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", width=4)
    table.add_column("Citation", width=35)
    table.add_column("Status", width=10)
    table.add_column("Score", width=6)
    table.add_column("PDF", width=4)

    for citation in citations:
        status_str = "?"
        if citation.verification:
            if citation.verification.status == VerificationStatus.VERIFIED:
                status_str = "✓ [green]Valid[/green]"
            elif citation.verification.status == VerificationStatus.PARTIAL:
                status_str = "≈ [yellow]Partial[/yellow]"
            else:
                status_str = "✗ [red]Unverified[/red]"

        score = citation.quality_score.total if citation.quality_score else 0
        pdf = "✓" if citation.pdf_download and citation.pdf_download.success else "✗"

        title = (
            citation.verification.matched_title
            if citation.verification
            else citation.title
        )
        title = title[:35] if title else citation.raw_text[:35]

        table.add_row(
            citation.number,
            title,
            status_str,
            str(score),
            pdf,
        )

    console.print(table)


def display_json(citations: List[VerifiedCitation]) -> None:
    """Display as JSON."""
    output = {"citations": [c.model_dump() for c in citations]}
    print(json.dumps(output, indent=2, default=str))


def display_markdown(
    citations: List[VerifiedCitation], paper_title: str
) -> None:
    """Display as markdown."""
    md = "# Citation Verification Report\n\n"
    md += f"**Paper:** {paper_title}\n\n"
    md += "## Citations\n\n"
    md += "| # | Citation | Status | Score | PDF |\n"
    md += "|---|----------|--------|-------|-----|\n"

    for citation in citations:
        status = (
            "✓"
            if citation.verification
            and citation.verification.status == VerificationStatus.VERIFIED
            else "?"
        )
        score = citation.quality_score.total if citation.quality_score else 0
        pdf = "✓" if citation.pdf_download and citation.pdf_download.success else "✗"
        title = (
            citation.verification.matched_title
            if citation.verification
            else citation.title
            or citation.raw_text[:40]
        )
        md += f"| {citation.number} | {title} | {status} | {score} | {pdf} |\n"

    print(md)


def get_stars(score: float) -> str:
    """Convert score to star rating."""
    if score >= 90:
        return "⭐⭐⭐⭐⭐"
    elif score >= 75:
        return "⭐⭐⭐⭐"
    elif score >= 60:
        return "⭐⭐⭐"
    elif score >= 40:
        return "⭐⭐"
    else:
        return "⭐"

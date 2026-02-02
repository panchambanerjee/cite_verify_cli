"""Output formatters for CitationVerify."""

import json
import re
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


def display_bibtex(
    citations: List[VerifiedCitation], paper_title: str = None
) -> None:
    """
    Display verified citations as BibTeX.
    
    Only exports citations that were verified (have DOI, arXiv ID, or matched metadata).
    """
    bibtex_entries = []
    
    for citation in citations:
        entry = _citation_to_bibtex(citation)
        if entry:
            bibtex_entries.append(entry)
    
    if paper_title:
        print(f"% BibTeX export for: {paper_title}")
        print(f"% Generated by CitationVerify")
        print(f"% Verified citations: {len(bibtex_entries)}/{len(citations)}")
        print()
    
    print("\n".join(bibtex_entries))


def _citation_to_bibtex(citation: VerifiedCitation) -> str:
    """
    Convert a single citation to BibTeX format.
    
    Returns empty string if citation cannot be converted.
    """
    # Only export verified citations
    if not citation.verification:
        return ""
    
    v = citation.verification
    
    # Skip unverified
    if v.status == VerificationStatus.UNVERIFIED:
        return ""
    
    # Generate citation key
    key = _generate_bibtex_key(citation)
    
    # Determine entry type
    entry_type = _determine_entry_type(v)
    
    # Build fields
    fields = []
    
    # Title
    title = v.matched_title or citation.title
    if title:
        fields.append(f"  title = {{{title}}}")
    
    # Authors
    authors = v.matched_authors or citation.authors
    if authors:
        author_str = " and ".join(authors)
        fields.append(f"  author = {{{author_str}}}")
    
    # Year
    year = v.matched_year or citation.year
    if year:
        fields.append(f"  year = {{{year}}}")
    
    # DOI
    doi = v.doi or citation.doi
    if doi:
        fields.append(f"  doi = {{{doi}}}")
    
    # arXiv
    arxiv_id = v.arxiv_id or citation.arxiv_id
    if arxiv_id:
        fields.append(f"  eprint = {{{arxiv_id}}}")
        fields.append(f"  archiveprefix = {{arXiv}}")
    
    # URL
    if citation.url:
        fields.append(f"  url = {{{citation.url}}}")
    
    # Journal/venue from metadata
    metadata = v.metadata or {}
    if "container-title" in metadata:
        container = metadata["container-title"]
        if isinstance(container, list) and container:
            fields.append(f"  journal = {{{container[0]}}}")
        elif isinstance(container, str):
            fields.append(f"  journal = {{{container}}}")
    
    # Publisher
    if "publisher" in metadata:
        fields.append(f"  publisher = {{{metadata['publisher']}}}")
    
    if not fields:
        return ""
    
    entry = f"@{entry_type}{{{key},\n"
    entry += ",\n".join(fields)
    entry += "\n}"
    
    return entry


def _generate_bibtex_key(citation: VerifiedCitation) -> str:
    """Generate a BibTeX citation key."""
    v = citation.verification
    
    # Try to use author last name + year
    key_parts = []
    
    authors = (v.matched_authors if v else None) or citation.authors
    if authors and authors[0]:
        # Extract last name (last word of first author)
        first_author = authors[0].strip()
        last_name = first_author.split()[-1] if first_author else "unknown"
        # Clean for BibTeX key
        last_name = re.sub(r"[^a-zA-Z]", "", last_name)
        key_parts.append(last_name.lower())
    else:
        key_parts.append("citation")
    
    year = (v.matched_year if v else None) or citation.year
    if year:
        key_parts.append(str(year))
    
    # Add citation number to ensure uniqueness
    key_parts.append(citation.number)
    
    return "".join(key_parts)


def _determine_entry_type(v) -> str:
    """Determine BibTeX entry type from verification metadata."""
    metadata = v.metadata or {}
    pub_type = metadata.get("type", "")
    
    if pub_type == "journal-article":
        return "article"
    elif pub_type in ["proceedings-article", "paper-conference"]:
        return "inproceedings"
    elif pub_type == "book-chapter":
        return "incollection"
    elif pub_type == "book":
        return "book"
    elif pub_type == "posted-content" or v.arxiv_id:
        return "misc"  # Preprints
    elif pub_type == "thesis":
        return "phdthesis"
    else:
        return "misc"


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


def save_bibtex(citations: List[VerifiedCitation], output_path: str) -> int:
    """
    Save verified citations to a BibTeX file.
    
    Args:
        citations: List of verified citations
        output_path: Path to output .bib file
        
    Returns:
        Number of citations exported
    """
    bibtex_entries = []
    
    for citation in citations:
        entry = _citation_to_bibtex(citation)
        if entry:
            bibtex_entries.append(entry)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"% BibTeX export by CitationVerify\n")
        f.write(f"% Verified citations: {len(bibtex_entries)}/{len(citations)}\n\n")
        f.write("\n\n".join(bibtex_entries))
    
    return len(bibtex_entries)

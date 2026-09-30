#!/usr/bin/env python3
"""Benchmark verify-cite on a fixed set of arXiv papers (no downloads, no cache)."""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
import urllib.request
from pathlib import Path

from verify_cite.extractor import CitationExtractor
from verify_cite.models import VerifiedCitation
from verify_cite.scorer import CitationQualityScorer
from verify_cite.verifier import MultiSourceVerifier

PAPERS = [
    {"arxiv_id": "1706.03762", "label": "Attention Is All You Need"},
    {"arxiv_id": "1810.04805", "label": "BERT"},
    {"arxiv_id": "1406.2661", "label": "Generative Adversarial Nets"},
]

RESULTS_DIR = Path(__file__).resolve().parent / "results"
BETWEEN_PAPERS_SLEEP = 20


def download_arxiv_pdf(arxiv_id: str, dest: Path, retries: int = 5) -> None:
    """Fetch PDF via export.arxiv.org to avoid hammering the Atom API."""
    url = f"https://export.arxiv.org/pdf/{arxiv_id}.pdf"
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "verify-cite-benchmark/0.1 (research)"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                dest.write_bytes(resp.read())
            return
        except Exception as exc:  # noqa: BLE001 — retry on rate limits / transient errors
            last_err = exc
            wait = 15 * (attempt + 1)
            print(f"  PDF download failed ({exc}); retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"Could not download {url}: {last_err}")


def empty_result(arxiv_id: str, label: str, paper_title: str, error: str, duration: float) -> dict:
    return {
        "arxiv_id": arxiv_id,
        "label": label,
        "paper_title": paper_title,
        "extraction_error": error,
        "duration_seconds": round(duration, 2),
        "citations_extracted": 0,
        "with_title": 0,
        "with_doi": 0,
        "with_arxiv_id": 0,
        "status_counts": {
            "verified": 0,
            "partial": 0,
            "unverified": 0,
            "error": 0,
            "missing": 0,
        },
        "mean_quality_score": None,
        "citations": [],
    }


async def run_one(arxiv_id: str, label: str) -> dict:
    start = time.time()
    extractor = CitationExtractor()

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / f"{arxiv_id}.pdf"
        download_arxiv_pdf(arxiv_id, pdf_path)
        try:
            citations, paper_title = extractor.extract_from_pdf(str(pdf_path))
        except ValueError as exc:
            return empty_result(arxiv_id, label, "Unknown Title", str(exc), time.time() - start)

    verified: list[VerifiedCitation] = [
        VerifiedCitation(**c.model_dump()) for c in citations
    ]

            verifier = MultiSourceVerifier(threshold=0.7, use_cache=False, verbose=False)
            scorer = CitationQualityScorer()

            try:
                sem = asyncio.Semaphore(5)

                async def _one(citation: VerifiedCitation) -> None:
                    async with sem:
                        result = await verifier.verify(citation)
                        citation.verification = result
                        if result:
                            citation.quality_score = scorer.score(citation, result)

                await asyncio.gather(*(_one(c) for c in verified))
            finally:
                await verifier.close()

    status_counts = {
        "verified": 0,
        "partial": 0,
        "unverified": 0,
        "error": 0,
        "missing": 0,
    }
    with_title = 0
    with_doi = 0
    with_arxiv = 0
    quality_totals: list[int] = []
    citation_rows: list[dict] = []

    for c in verified:
        if c.title:
            with_title += 1
        if c.doi:
            with_doi += 1
        if c.arxiv_id:
            with_arxiv += 1

        status = "missing"
        if c.verification:
            status = c.verification.status.value
        status_counts[status] = status_counts.get(status, 0) + 1

        if c.quality_score:
            quality_totals.append(c.quality_score.total)

        citation_rows.append(
            {
                "number": c.number,
                "title": c.title,
                "authors": c.authors,
                "year": c.year,
                "doi": c.doi,
                "arxiv_id": c.arxiv_id,
                "journal": c.journal,
                "raw_text": (c.raw_text or "")[:500],
                "status": status,
                "confidence": c.verification.confidence if c.verification else None,
                "matched_title": c.verification.matched_title if c.verification else None,
                "verified_sources": (
                    c.verification.verified_sources if c.verification else []
                ),
                "discrepancies": (
                    c.verification.discrepancies if c.verification else []
                ),
                "quality_total": c.quality_score.total if c.quality_score else None,
            }
        )

    duration = time.time() - start
    mean_quality = sum(quality_totals) / len(quality_totals) if quality_totals else None

    return {
        "arxiv_id": arxiv_id,
        "label": label,
        "paper_title": paper_title,
        "duration_seconds": round(duration, 2),
        "citations_extracted": len(verified),
        "with_title": with_title,
        "with_doi": with_doi,
        "with_arxiv_id": with_arxiv,
        "status_counts": status_counts,
        "mean_quality_score": round(mean_quality, 2) if mean_quality is not None else None,
        "citations": citation_rows,
    }


def summary_row(result: dict) -> dict:
    return {
        "arxiv_id": result["arxiv_id"],
        "label": result["label"],
        "paper_title": result["paper_title"],
        "extraction_error": result.get("extraction_error"),
        "duration_seconds": result["duration_seconds"],
        "citations_extracted": result["citations_extracted"],
        "with_title": result["with_title"],
        "with_doi": result["with_doi"],
        "with_arxiv_id": result["with_arxiv_id"],
        "status_counts": result["status_counts"],
        "mean_quality_score": result["mean_quality_score"],
    }


async def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary = []

    for i, paper in enumerate(PAPERS):
        out_path = RESULTS_DIR / f"{paper['arxiv_id'].replace('.', '_')}.json"
        if out_path.exists():
            print(f"Reusing existing {out_path.name}")
            result = json.loads(out_path.read_text(encoding="utf-8"))
        else:
            if i > 0:
                print(f"Sleeping {BETWEEN_PAPERS_SLEEP}s between papers...")
                await asyncio.sleep(BETWEEN_PAPERS_SLEEP)
            print(f"Running {paper['arxiv_id']} ({paper['label']})...")
            result = await run_one(paper["arxiv_id"], paper["label"])
            out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
            err = result.get("extraction_error")
            if err:
                print(f"  EXTRACTION FAILED: {err}")
            print(
                f"  extracted={result['citations_extracted']} "
                f"verified={result['status_counts']['verified']} "
                f"partial={result['status_counts']['partial']} "
                f"unverified={result['status_counts']['unverified']} "
                f"error={result['status_counts']['error']} "
                f"mean_quality={result['mean_quality_score']} "
                f"time={result['duration_seconds']}s -> {out_path.name}"
            )

        summary.append(summary_row(result))

    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())

"""Smart PDF downloading with fallback strategies."""

import asyncio
import os
import aiohttp
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from .models import Citation, VerificationResult, PDFDownloadResult
from .utils import normalize_doi, normalize_arxiv_id

# Load environment variables
load_dotenv()


class SmartPDFDownloader:
    """Download PDFs with intelligent fallback."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.unpaywall_email = os.getenv("UNPAYWALL_EMAIL", "user@example.com")

    async def download(
        self,
        citation: Citation,
        verification: VerificationResult,
        output_dir: str = "./citations",
    ) -> PDFDownloadResult:
        """
        Try multiple sources to download PDF.

        Priority:
        1. arXiv
        2. Unpaywall
        3. Semantic Scholar
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        arxiv_id = verification.arxiv_id or citation.arxiv_id
        if arxiv_id:
            result = await self._download_from_arxiv(
                arxiv_id, output_dir, citation.number
            )
            if result.success:
                return result

        doi = verification.doi or citation.doi
        if doi:
            result = await self._download_from_unpaywall(
                doi, output_dir, citation.number
            )
            if result.success:
                return result

        metadata = verification.metadata
        if "openAccessPdf" in metadata and metadata["openAccessPdf"]:
            pdf_url = metadata["openAccessPdf"].get("url")
            if pdf_url:
                result = await self._download_from_url(
                    pdf_url, output_dir, citation.number, "semantic_scholar"
                )
                if result.success:
                    return result

        return PDFDownloadResult(
            success=False,
            error="PDF not available from any source",
        )

    async def _download_from_arxiv(
        self, arxiv_id: str, output_dir: str, citation_number: str
    ) -> PDFDownloadResult:
        """Download from arXiv."""
        try:
            import arxiv

            arxiv_id = normalize_arxiv_id(arxiv_id)
            if not arxiv_id:
                return PDFDownloadResult(success=False, error="Invalid arXiv ID")

            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(search.results())

            filename = f"[{citation_number}]_{arxiv_id}.pdf"
            filepath = os.path.join(output_dir, filename)
            paper.download_pdf(dirpath=output_dir, filename=filename)
            file_size = os.path.getsize(filepath)

            return PDFDownloadResult(
                success=True,
                pdf_path=filepath,
                source="arxiv",
                file_size=file_size,
            )
        except StopIteration:
            return PDFDownloadResult(
                success=False, error="arXiv paper not found"
            )
        except Exception as e:
            return PDFDownloadResult(
                success=False, error=f"arXiv download failed: {str(e)}"
            )

    async def _download_from_unpaywall(
        self, doi: str, output_dir: str, citation_number: str
    ) -> PDFDownloadResult:
        """Download from Unpaywall."""
        doi = normalize_doi(doi)
        if not doi:
            return PDFDownloadResult(success=False, error="Invalid DOI")

        url = f"https://api.unpaywall.org/v2/{doi}"
        params = {"email": self.unpaywall_email}

        try:
            async with self.session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return PDFDownloadResult(
                        success=False, error="Not found in Unpaywall"
                    )
                data = await resp.json()
                if not data.get("is_oa"):
                    return PDFDownloadResult(
                        success=False, error="Not open access"
                    )
                best_oa = data.get("best_oa_location")
                if not best_oa or not best_oa.get("url_for_pdf"):
                    return PDFDownloadResult(
                        success=False, error="No PDF URL available"
                    )
                pdf_url = best_oa["url_for_pdf"]
                return await self._download_from_url(
                    pdf_url, output_dir, citation_number, "unpaywall"
                )
        except asyncio.TimeoutError:
            return PDFDownloadResult(
                success=False, error="Unpaywall timeout"
            )
        except Exception as e:
            return PDFDownloadResult(
                success=False, error=f"Unpaywall error: {str(e)}"
            )

    async def _download_from_url(
        self, url: str, output_dir: str, citation_number: str, source: str
    ) -> PDFDownloadResult:
        """Download PDF from URL."""
        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    return PDFDownloadResult(
                        success=False, error=f"HTTP {resp.status}"
                    )
                content = await resp.read()
                filename = f"[{citation_number}]_{source}.pdf"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "wb") as f:
                    f.write(content)
                if not self._is_valid_pdf(filepath):
                    os.remove(filepath)
                    return PDFDownloadResult(
                        success=False,
                        error="Downloaded file is not a valid PDF",
                    )
                return PDFDownloadResult(
                    success=True,
                    pdf_path=filepath,
                    source=source,
                    file_size=len(content),
                )
        except asyncio.TimeoutError:
            return PDFDownloadResult(
                success=False, error="Download timeout"
            )
        except Exception as e:
            return PDFDownloadResult(
                success=False, error=f"Download error: {str(e)}"
            )

    def _is_valid_pdf(self, filepath: str) -> bool:
        """Check if file is a valid PDF."""
        try:
            import PyPDF2
            with open(filepath, "rb") as f:
                PyPDF2.PdfReader(f)
            return True
        except Exception:
            return False

    async def close(self):
        """Close session."""
        if self.session:
            await self.session.close()

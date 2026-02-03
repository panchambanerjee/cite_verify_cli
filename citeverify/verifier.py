"""Multi-source citation verification with caching and verbose logging."""

import asyncio
import aiohttp
from typing import Optional, List, Callable
from difflib import SequenceMatcher
from .models import Citation, VerificationResult, VerificationStatus
from .utils import normalize_doi, normalize_arxiv_id
from .cache import VerificationCache


class MultiSourceVerifier:
    """Verify citations across multiple sources with caching."""

    def __init__(
        self,
        threshold: float = 0.7,
        use_cache: bool = True,
        verbose: bool = False,
        log_callback: Callable[[str], None] = None,
    ):
        """
        Initialize verifier.

        Args:
            threshold: Minimum similarity threshold for title matching (0.0-1.0)
            use_cache: Whether to use caching for API results
            verbose: Whether to log detailed verification attempts
            log_callback: Function to call for logging (receives log message)
        """
        self.session: Optional[aiohttp.ClientSession] = None
        self.threshold = threshold
        self.use_cache = use_cache
        self.verbose = verbose
        self.log_callback = log_callback
        self.rate_limits = {
            "crossref": asyncio.Semaphore(5),  # 5 req/sec
            "arxiv": asyncio.Semaphore(3),  # 3 req/sec
        }

        if use_cache:
            self.cache = VerificationCache()
        else:
            self.cache = None

    def _log(self, message: str):
        """Log message if verbose mode is enabled."""
        if self.verbose and self.log_callback:
            self.log_callback(message)

    async def verify(self, citation: Citation) -> VerificationResult:
        """
        Verify citation using multiple sources.

        Priority:
        1. DOI → CrossRef (authoritative)
        2. arXiv ID → arXiv API (direct)
        3. Fuzzy search across all sources
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        self._log(f"[{citation.number}] Starting verification...")

        # Priority 1: DOI lookup
        if citation.doi:
            self._log(f"[{citation.number}] Trying DOI: {citation.doi}")

            # Check cache first
            if self.cache:
                cached = self.cache.get("doi", citation.doi)
                if cached:
                    self._log(f"[{citation.number}] ✓ Found in cache (DOI)")
                    return cached

            result = await self._verify_via_crossref_doi(citation.doi)

            if result.status == VerificationStatus.VERIFIED:
                self._log(f"[{citation.number}] ✓ Verified via CrossRef DOI")
                if self.cache:
                    self.cache.set("doi", citation.doi, result)
                return result
            else:
                self._log(
                    f"[{citation.number}] ✗ DOI lookup failed: {result.discrepancies}"
                )

        # Priority 2: arXiv ID lookup
        if citation.arxiv_id:
            self._log(f"[{citation.number}] Trying arXiv ID: {citation.arxiv_id}")

            # Check cache first
            if self.cache:
                cached = self.cache.get("arxiv", citation.arxiv_id)
                if cached:
                    self._log(f"[{citation.number}] ✓ Found in cache (arXiv)")
                    return cached

            result = await self._verify_via_arxiv(citation.arxiv_id)

            if result.status == VerificationStatus.VERIFIED:
                self._log(f"[{citation.number}] ✓ Verified via arXiv")
                if self.cache:
                    self.cache.set("arxiv", citation.arxiv_id, result)
                return result
            else:
                self._log(
                    f"[{citation.number}] ✗ arXiv lookup failed: {result.discrepancies}"
                )

        # Priority 3: Fuzzy search
        if citation.title:
            self._log(
                f"[{citation.number}] Trying title search: {citation.title[:50]}..."
            )

            # Check cache first
            if self.cache:
                cached = self.cache.get("title", citation.title)
                if cached:
                    self._log(f"[{citation.number}] ✓ Found in cache (title)")
                    return cached

            results = await asyncio.gather(
                self._search_crossref(citation),
                self._search_semantic_scholar(citation),
                self._search_arxiv(citation),
                return_exceptions=True,
            )

            valid_results = [
                r for r in results if not isinstance(r, Exception) and r
            ]

            if valid_results:
                # Prefer arXiv when above threshold (title match on arXiv is authoritative)
                arxiv_results = [r for r in valid_results if "arxiv" in (r.verified_sources or [])]
                if arxiv_results:
                    best = max(arxiv_results, key=lambda r: r.confidence)
                else:
                    best = max(valid_results, key=lambda r: r.confidence)
                source = best.verified_sources[0] if best.verified_sources else "unknown"
                self._log(
                    f"[{citation.number}] ✓ Found via {source} "
                    f"(similarity: {best.confidence:.2f})"
                )
                if self.cache:
                    self.cache.set("title", citation.title, best)
                return best
            else:
                self._log(
                    f"[{citation.number}] ✗ Title search failed "
                    f"(threshold: {self.threshold})"
                )
        else:
            self._log(f"[{citation.number}] ✗ No title, DOI, or arXiv ID to search")

        # Not found anywhere
        reasons = []
        if not citation.doi:
            reasons.append("No DOI")
        if not citation.arxiv_id:
            reasons.append("No arXiv ID")
        if not citation.title:
            reasons.append("No title extracted")
        else:
            reasons.append(f"Title similarity below threshold ({self.threshold})")

        self._log(f"[{citation.number}] ✗ Not verified: {', '.join(reasons)}")

        return VerificationResult(
            status=VerificationStatus.UNVERIFIED,
            confidence=0.0,
            discrepancies=reasons,
        )

    async def _verify_via_crossref_doi(self, doi: str) -> VerificationResult:
        """Verify using CrossRef DOI lookup."""
        doi = normalize_doi(doi)
        if not doi:
            return VerificationResult(
                status=VerificationStatus.ERROR,
                confidence=0.0,
                discrepancies=["Invalid DOI format"],
            )

        async with self.rate_limits["crossref"]:
            url = f"https://api.crossref.org/works/{doi}"

            try:
                async with self.session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 404:
                        return VerificationResult(
                            status=VerificationStatus.UNVERIFIED,
                            confidence=0.0,
                            discrepancies=["DOI not found in CrossRef"],
                        )

                    if resp.status != 200:
                        return VerificationResult(
                            status=VerificationStatus.ERROR,
                            confidence=0.0,
                            discrepancies=[f"CrossRef API error: {resp.status}"],
                        )

                    data = await resp.json()
                    message = data["message"]

                    # Extract title
                    matched_title = None
                    if message.get("title"):
                        matched_title = (
                            message["title"][0]
                            if isinstance(message["title"], list)
                            else message["title"]
                        )

                    # Extract authors
                    matched_authors = []
                    if message.get("author"):
                        matched_authors = [
                            f"{a.get('given', '')} {a.get('family', '')}".strip()
                            for a in message["author"]
                        ]

                    # Extract year
                    matched_year = None
                    if message.get("published-print"):
                        date_parts = message["published-print"].get("date-parts", [])
                        if date_parts and date_parts[0]:
                            matched_year = date_parts[0][0]
                    elif message.get("published-online"):
                        date_parts = message["published-online"].get("date-parts", [])
                        if date_parts and date_parts[0]:
                            matched_year = date_parts[0][0]
                    elif message.get("created"):
                        date_parts = message["created"].get("date-parts", [])
                        if date_parts and date_parts[0]:
                            matched_year = date_parts[0][0]

                    return VerificationResult(
                        status=VerificationStatus.VERIFIED,
                        confidence=1.0,
                        matched_title=matched_title,
                        matched_authors=matched_authors,
                        matched_year=matched_year,
                        doi=message.get("DOI"),
                        verified_sources=["crossref"],
                        metadata=message,
                    )

            except asyncio.TimeoutError:
                return VerificationResult(
                    status=VerificationStatus.ERROR,
                    confidence=0.0,
                    discrepancies=["CrossRef timeout"],
                )
            except Exception as e:
                return VerificationResult(
                    status=VerificationStatus.ERROR,
                    confidence=0.0,
                    discrepancies=[f"CrossRef error: {str(e)}"],
                )

    async def _verify_via_arxiv(self, arxiv_id: str) -> VerificationResult:
        """Verify using arXiv API."""
        arxiv_id = normalize_arxiv_id(arxiv_id)
        if not arxiv_id:
            return VerificationResult(
                status=VerificationStatus.ERROR,
                confidence=0.0,
                discrepancies=["Invalid arXiv ID format"],
            )

        async with self.rate_limits["arxiv"]:
            try:
                import arxiv

                search = arxiv.Search(id_list=[arxiv_id])
                paper = next(search.results())

                return VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    confidence=1.0,
                    matched_title=paper.title,
                    matched_authors=[a.name for a in paper.authors],
                    matched_year=paper.published.year if paper.published else None,
                    doi=paper.doi,
                    arxiv_id=arxiv_id,
                    verified_sources=["arxiv"],
                    metadata={
                        "abstract": paper.summary,
                        "pdf_url": paper.pdf_url,
                    },
                )

            except StopIteration:
                return VerificationResult(
                    status=VerificationStatus.UNVERIFIED,
                    confidence=0.0,
                    discrepancies=["arXiv ID not found"],
                )
            except Exception as e:
                return VerificationResult(
                    status=VerificationStatus.ERROR,
                    confidence=0.0,
                    discrepancies=[f"arXiv error: {str(e)}"],
                )

    async def _search_crossref(
        self, citation: Citation
    ) -> Optional[VerificationResult]:
        """Search CrossRef by title."""
        if not citation.title:
            return None

        async with self.rate_limits["crossref"]:
            url = "https://api.crossref.org/works"
            params = {"query": citation.title, "rows": 5}

            try:
                async with self.session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    items = data["message"].get("items", [])

                    if not items:
                        return None

                    # Find best title match
                    best_match = max(
                        items,
                        key=lambda item: self._title_similarity(
                            citation.title,
                            (
                                item["title"][0]
                                if item.get("title")
                                and isinstance(item["title"], list)
                                else (item.get("title") or "")
                            ),
                        ),
                    )

                    matched_title = (
                        best_match["title"][0]
                        if best_match.get("title")
                        and isinstance(best_match["title"], list)
                        else (best_match.get("title") or "")
                    )
                    similarity = self._title_similarity(citation.title, matched_title)

                    if similarity < self.threshold:
                        return None

                    status = (
                        VerificationStatus.VERIFIED
                        if similarity > 0.8
                        else VerificationStatus.PARTIAL
                    )

                    # Extract authors
                    matched_authors = []
                    if best_match.get("author"):
                        matched_authors = [
                            f"{a.get('given', '')} {a.get('family', '')}".strip()
                            for a in best_match["author"]
                        ]

                    # Extract year
                    matched_year = None
                    if best_match.get("published-print"):
                        date_parts = best_match["published-print"].get(
                            "date-parts", []
                        )
                        if date_parts and date_parts[0]:
                            matched_year = date_parts[0][0]
                    elif best_match.get("published-online"):
                        date_parts = best_match["published-online"].get(
                            "date-parts", []
                        )
                        if date_parts and date_parts[0]:
                            matched_year = date_parts[0][0]

                    return VerificationResult(
                        status=status,
                        confidence=similarity,
                        matched_title=matched_title,
                        matched_authors=matched_authors,
                        matched_year=matched_year,
                        doi=best_match.get("DOI"),
                        verified_sources=["crossref"],
                        discrepancies=self._find_discrepancies(citation, best_match),
                        metadata=best_match,
                    )

            except Exception:
                return None

    async def _search_semantic_scholar(
        self, citation: Citation
    ) -> Optional[VerificationResult]:
        """Search Semantic Scholar by title."""
        if not citation.title:
            return None

        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": citation.title,
            "limit": 5,
            "fields": "title,authors,year,externalIds,citationCount",
        }

        try:
            async with self.session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                papers = data.get("data", [])

                if not papers:
                    return None

                # Find best match
                best_match = max(
                    papers,
                    key=lambda p: self._title_similarity(
                        citation.title, p.get("title", "")
                    ),
                )

                matched_title = best_match.get("title", "")
                similarity = self._title_similarity(citation.title, matched_title)

                if similarity < self.threshold:
                    return None

                status = (
                    VerificationStatus.VERIFIED
                    if similarity > 0.8
                    else VerificationStatus.PARTIAL
                )

                # Extract arXiv ID if present
                arxiv_id = None
                external_ids = best_match.get("externalIds", {})
                if external_ids and "ArXiv" in external_ids:
                    arxiv_id = normalize_arxiv_id(external_ids["ArXiv"])

                return VerificationResult(
                    status=status,
                    confidence=similarity,
                    matched_title=matched_title,
                    matched_authors=[
                        a.get("name", "") for a in best_match.get("authors", [])
                    ],
                    matched_year=best_match.get("year"),
                    doi=external_ids.get("DOI") if external_ids else None,
                    arxiv_id=arxiv_id,
                    verified_sources=["semantic_scholar"],
                    metadata=best_match,
                )

        except Exception:
            return None

    async def _search_arxiv(self, citation: Citation) -> Optional[VerificationResult]:
        """Search arXiv by title."""
        if not citation.title:
            return None

        async with self.rate_limits["arxiv"]:
            try:
                import arxiv

                # Search arXiv by title (fetch more to find papers that rank lower in relevance)
                search = arxiv.Search(
                    query=citation.title,
                    max_results=15,
                    sort_by=arxiv.SortCriterion.Relevance,
                )

                best_match = None
                best_similarity = 0.0

                for paper in search.results():
                    similarity = self._title_similarity(citation.title, paper.title)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = paper

                if not best_match or best_similarity < self.threshold:
                    return None

                # arXiv match by title is authoritative: treat as VERIFIED when above threshold
                status = VerificationStatus.VERIFIED

                # Extract arXiv ID from entry_id (e.g., "http://arxiv.org/abs/1234.56789v1")
                arxiv_id = None
                if best_match.entry_id:
                    import re
                    match = re.search(r'(\d{4}\.\d{4,5})', best_match.entry_id)
                    if match:
                        arxiv_id = match.group(1)

                return VerificationResult(
                    status=status,
                    confidence=best_similarity,
                    matched_title=best_match.title,
                    matched_authors=[a.name for a in best_match.authors],
                    matched_year=best_match.published.year if best_match.published else None,
                    doi=best_match.doi,
                    arxiv_id=arxiv_id,
                    verified_sources=["arxiv"],
                    metadata={
                        "abstract": best_match.summary,
                        "pdf_url": best_match.pdf_url,
                    },
                )

            except Exception:
                return None

    def _title_similarity(self, title1: str, title2: str) -> float:
        """Calculate title similarity (0-1)."""
        import re

        if not title1 or not title2:
            return 0.0

        # Normalize
        t1 = re.sub(r"[^\w\s]", "", title1.lower())
        t2 = re.sub(r"[^\w\s]", "", title2.lower())

        return SequenceMatcher(None, t1, t2).ratio()

    def _find_discrepancies(self, original: Citation, matched: dict) -> list:
        """Find discrepancies between original and matched."""
        discrepancies = []

        # Check year
        if original.year and matched.get("published-print"):
            date_parts = matched["published-print"].get("date-parts", [])
            if date_parts and date_parts[0]:
                matched_year = date_parts[0][0]
                if abs(original.year - matched_year) > 1:
                    discrepancies.append(
                        f"Year mismatch: {original.year} vs {matched_year}"
                    )
        elif original.year and matched.get("published-online"):
            date_parts = matched["published-online"].get("date-parts", [])
            if date_parts and date_parts[0]:
                matched_year = date_parts[0][0]
                if abs(original.year - matched_year) > 1:
                    discrepancies.append(
                        f"Year mismatch: {original.year} vs {matched_year}"
                    )

        return discrepancies

    def get_cache_stats(self) -> Optional[dict]:
        """Get cache statistics."""
        if self.cache:
            return self.cache.stats()
        return None

    async def close(self):
        """Close session."""
        if self.session:
            await self.session.close()

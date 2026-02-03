"""Citation extraction from PDFs and arXiv papers."""

import re
import pdfplumber
import tempfile
import os
from typing import List, Tuple
from .models import Citation
from .utils import normalize_doi, normalize_arxiv_id, extract_year_from_text, clean_title


class CitationExtractor:
    """
    Extract citations from PDFs using pdfplumber + regex.
    TODO: Add GROBID support for better accuracy.
    """
    
    def extract_from_pdf(self, pdf_path: str) -> Tuple[List[Citation], str]:
        """
        Extract citations from PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (citations, paper_title)
        """
        # Extract full text
        text = self._extract_text(pdf_path)
        
        # Try to extract title (first non-empty line)
        title = self._extract_title(text)
        
        # Find references section
        ref_section = self._find_references_section(text)
        
        if not ref_section:
            raise ValueError(
                "Could not find references section. "
                "Try using --interactive mode to manually select citations."
            )
        
        # Parse individual citations
        citations = self._parse_citations(ref_section)
        
        return citations, title
    
    def _extract_text(self, pdf_path: str) -> str:
        """Extract all text from PDF."""
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
        
        return text
    
    def _extract_title(self, text: str) -> str:
        """Extract paper title (first substantial line)."""
        lines = text.split('\n')
        for line in lines[:20]:  # Check first 20 lines
            line = line.strip()
            # Skip all-caps headers, very short lines, and common headers
            if (len(line) > 20 and 
                not line.isupper() and 
                not line.lower().startswith(('abstract', 'introduction', 'keywords'))):
                return clean_title(line)
        return "Unknown Title"
    
    def _find_references_section(self, text: str) -> str:
        """Find the references/bibliography section."""
        # Common section headers
        patterns = [
            r'\n\s*(References|REFERENCES)\s*\n',
            r'\n\s*(Bibliography|BIBLIOGRAPHY)\s*\n',
            r'\n\s*(Works Cited|WORKS CITED)\s*\n',
            r'\n\s*(Literature|LITERATURE)\s*\n',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start = match.end()
                
                # Find where references end (common end markers)
                end_patterns = [
                    r'\n\s*(Appendix|APPENDIX)',
                    r'\n\s*(Acknowledgments|ACKNOWLEDGMENTS)',
                    r'\n\s*(Supplementary|SUPPLEMENTARY)',
                ]
                
                end = len(text)
                for end_pattern in end_patterns:
                    end_match = re.search(end_pattern, text[start:], re.IGNORECASE)
                    if end_match:
                        end = start + end_match.start()
                        break
                
                return text[start:end].strip()
        
        return ""
    
    def _parse_citations(self, ref_section: str) -> List[Citation]:
        """Parse individual citations from references section."""
        citations = []
        
        # Try numbered citations first: [1], [2], etc.
        # Stop at next "[n]" or at newline followed by "n." / "n)" (alternate numbering)
        numbered_pattern = r'\[(\d+)\]\s*(.+?)(?=\[\d+\]|\n\s*\d+[.)]\s|$)'
        numbered_matches = re.findall(numbered_pattern, ref_section, re.DOTALL)
        
        if numbered_matches:
            for num, text in numbered_matches:
                citation = self._parse_single_citation(text.strip(), num)
                citations.append(citation)
        else:
            # Try splitting by double newlines or numbered patterns
            # Pattern for numbered citations like "1. " or "1) "
            alt_pattern = r'^\s*(\d+)[.)]\s*(.+?)(?=^\s*\d+[.)]|$)'
            alt_matches = re.findall(alt_pattern, ref_section, re.MULTILINE | re.DOTALL)
            
            if alt_matches:
                for num, text in alt_matches:
                    citation = self._parse_single_citation(text.strip(), num)
                    citations.append(citation)
            else:
                # Fallback: split by double newlines
                parts = re.split(r'\n\s*\n', ref_section)
                for i, part in enumerate(parts, 1):
                    if part.strip():
                        citation = self._parse_single_citation(part.strip(), str(i))
                        citations.append(citation)
        
        return citations
    
    def _parse_single_citation(self, text: str, number: str) -> Citation:
        """Extract metadata from a single citation string."""
        # Strip leading "[n] " if present (defensive: some split paths may include it)
        text = re.sub(r'^\s*\[\d+\]\s*', '', text.strip()).strip()
        if not text:
            return Citation(number=number, raw_text=text, title=None, authors=None, year=None, doi=None, arxiv_id=None, url=None, journal=None)

        # Extract DOI
        doi_match = re.search(r'10\.\d{4,}/[^\s\)]+', text)
        doi = None
        if doi_match:
            doi = normalize_doi(doi_match.group(0))
        
        # Extract arXiv ID - multiple patterns
        arxiv_id = self._extract_arxiv_id(text)
        
        # Extract year (4-digit number)
        year = extract_year_from_text(text)
        
        # Extract URL
        url_match = re.search(r'https?://[^\s\)]+', text)
        url = url_match.group(0).rstrip('.,)') if url_match else None
        
        # Extract title using improved method
        title = self._extract_title_from_citation(text, year)
        
        # Extract authors (text before first period, typically)
        authors = self._extract_authors(text)
        
        # Extract journal (often after title, before year or DOI)
        journal = None
        journal_patterns = [
            r'In\s+([^,]+?)(?:,|\.|$)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Journal|Proceedings|Conference)',
            r'(?:CoRR|arXiv)',  # Common preprint indicators
        ]
        for pattern in journal_patterns:
            journal_match = re.search(pattern, text, re.IGNORECASE)
            if journal_match:
                journal = journal_match.group(0).strip('.,')
                break
        
        return Citation(
            number=number,
            raw_text=text,
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            arxiv_id=arxiv_id,
            url=url,
            journal=journal
        )
    
    def _extract_arxiv_id(self, text: str) -> str:
        """
        Extract arXiv ID from citation text.
        
        Handles multiple formats:
        - arXiv:1234.56789
        - arxiv.org/abs/1234.56789
        - abs/1234.56789
        - CoRR, abs/1234.56789
        """
        # Pattern 1: arXiv:XXXX.XXXXX or arXiv preprint arXiv:XXXX.XXXXX
        match = re.search(r'arXiv[:\s]+(\d{4}\.\d{4,5})(?:v\d+)?', text, re.IGNORECASE)
        if match:
            return normalize_arxiv_id(match.group(1))
        
        # Pattern 1b: "arXiv preprint 1602.02410" (no colon)
        match = re.search(r'arXiv\s+preprint\s+(\d{4}\.\d{4,5})', text, re.IGNORECASE)
        if match:
            return normalize_arxiv_id(match.group(1))
        
        # Pattern 2: arxiv.org/abs/XXXX.XXXXX
        match = re.search(r'arxiv\.org/abs/(\d{4}\.\d{4,5})', text, re.IGNORECASE)
        if match:
            return normalize_arxiv_id(match.group(1))
        
        # Pattern 3: abs/XXXX.XXXXX (common in CoRR citations)
        match = re.search(r'abs/(\d{4}\.\d{4,5})', text, re.IGNORECASE)
        if match:
            return normalize_arxiv_id(match.group(1))
        
        # Pattern 4: Old arXiv format (e.g., cs.CL/0001001)
        match = re.search(r'arXiv[:\s]+([a-z-]+(?:\.[A-Z]{2})?/\d{7})', text, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_title_from_citation(self, text: str, year: int = None) -> str:
        """
        Extract title from citation text using multiple strategies.
        
        Common citation formats:
        1. Author1, Author2. Title of paper. Journal, year.
        2. Author1 et al. "Title of paper". Journal, year.
        3. Author1 and Author2. Title. In Proceedings of..., year.
        """
        # Strategy 1: Title in quotes
        title_match = re.search(r'["""]([^"""]+)["""]', text)
        if title_match:
            title = title_match.group(1).strip()
            if len(title) > 10:
                return clean_title(title)
        
        # Strategy 2: Title between author block and journal/year
        # Look for pattern: "Authors. Title. Journal/venue"
        # Require author word length >= 2 so we don't match "M." (middle initial) and capture "Rush. Title"
        author_end_match = re.search(
            r'(?:et\s+al\.|[A-Za-z\u00C0-\u024F][a-z\u00C0-\u024F]+)\.\s+([A-Z][^.]*(?:\.[^.]*)*?)(?:\.\s*(?:In\s|CoRR|arXiv|Proceedings|Journal|Trans\.|IEEE|ACM|\d{4}))',
            text,
            re.IGNORECASE
        )
        if author_end_match:
            title = author_end_match.group(1).strip()
            # Clean up - remove trailing period
            title = title.rstrip('.')
            if len(title) > 10:
                return clean_title(title)

        # Strategy 2d: "Authors. Title. In Venue..." or "Authors. Title In Venue..." (venue delimiter)
        # PDFs often drop spaces at line breaks: "networks.\nIn International" -> "networks.InInternational"
        text_normalized = re.sub(r'\s+', ' ', text)
        # Restore missing spaces: ".InInternational" -> ". In International" (period+In and In+Capital)
        text_normalized = re.sub(r'\.In([A-Z])', r'. In \1', text_normalized)
        text_normalized = re.sub(r'\bIn([A-Z])', r'In \1', text_normalized)
        # Try venue-style "In International/Empirical/Conference/..." (catches "In Empirical Methods", "InInternational", etc.)
        venue_start = re.search(
            r'In\s*(?:International|Proceedings|Conference|ICLR|Advances|Annual|Symposium|Empirical)\s',
            text_normalized,
            re.IGNORECASE,
        )
        if venue_start:
            before_venue = text_normalized[: venue_start.start()].strip()
            # PDF may merge title with "In": e.g. "algorithmsIn" -> drop trailing "In"
            if re.search(r'[a-zA-Z]In$', before_venue):
                before_venue = before_venue[:-2].rstrip()
            if ". " in before_venue:
                # Use last segment (title); first period may be after "M." in "Alexander M. Rush"
                title = before_venue.split(". ")[-1].strip().rstrip(".")
            else:
                title = self._strip_leading_authors_from_title(before_venue)
            if title:
                title = self._strip_journal_volume_from_title(title)
                if len(title) > 10 and not self._looks_like_venue(title):
                    return clean_title(title)
        for sep in (". In ", " In "):
            if sep in text_normalized:
                before_venue = text_normalized.split(sep, 1)[0].strip()
                if ". " in before_venue:
                    title = before_venue.split(". ")[-1].strip().rstrip(".")
                else:
                    title = self._strip_leading_authors_from_title(before_venue)
                if title:
                    title = self._strip_journal_volume_from_title(title)
                    if len(title) > 10 and not self._looks_like_venue(title):
                        return clean_title(title)
                break
        
        # Strategy 2c: "Authors. Title? In Venue..." or "Authors Title? In Venue..." (no period)
        if "? In " in text or "? In" in text:
            sep = "? In " if "? In " in text else "? In"
            before_venue = text.split(sep)[0].strip().rstrip("?")
            if ". " in before_venue:
                title = before_venue.split(". ")[-1].strip().rstrip("?")
            else:
                # No period: "Authors Title?" - strip leading author block (e.g. "Name and Name ")
                title = self._strip_leading_authors_from_title(before_venue)
            if title:
                title = self._strip_journal_volume_from_title(title)
                if len(title) > 10 and not self._looks_like_venue(title):
                    return clean_title(title)
        
        # Strategy 2b: "Authors. Title, year." or "Authors. Title? In Venue, year."
        if year:
            title_comma_year = re.search(
                r'\.\s+(.+),\s*(?:19|20)\d{2}\s*\.?\s*$',
                text,
                re.DOTALL,
            )
            if title_comma_year:
                title = title_comma_year.group(1).strip().rstrip('.,')
                if ". In " in title or "? In " in title:
                    title = re.split(r'[.?]\s+In\s+', title, maxsplit=1, flags=re.IGNORECASE)[0].strip().rstrip('.?')
                title = self._strip_journal_volume_from_title(title)
                if len(title) > 10 and not self._looks_like_venue(title):
                    return clean_title(title)
        
        # Strategy 3: Find sentence-like text between periods
        # Split by periods and find the best segment that looks like a title
        sentences = re.split(r'\.\s+', text)
        
        # Skip first segment (likely authors) and last segment (likely venue/year)
        if len(sentences) > 2:
            candidates = []
            for sent in sentences[1:-1]:
                sent = sent.strip()
                # Skip venue/volume segments (e.g. "Neural computation, 9(8):1735–1780, 1997")
                if re.search(r',\s*\d+\(\d+\):\s*\d+', sent):
                    continue
                if (sent and
                    sent[0].isupper() and
                    10 < len(sent) < 200 and
                    not re.match(r'^(In\s|Proceedings|Journal|Trans\.|IEEE|ACM|CoRR|arXiv)', sent, re.IGNORECASE)):
                    candidates.append((len(sent), sent))
            
            if candidates:
                candidates.sort(reverse=True)
                title = self._strip_journal_volume_from_title(candidates[0][1])
                if len(title) > 10 and not self._looks_like_venue(title):
                    return clean_title(title)
        
        # Strategy 4: Fallback - text before year; take last segment after a period that looks like a title
        if year:
            year_pos = text.find(str(year))
            if year_pos > 0:
                before_year = text[:year_pos]
                # Segments after periods (skip first = authors)
                segments = re.split(r'\.\s+', before_year)
                # Try from last segment backward (venue often last, title before it)
                for seg in reversed(segments[1:]):
                    seg = seg.strip().rstrip('.,')
                    if ". In " in seg or "? In " in seg:
                        seg = re.split(r'[.?]\s+In\s+', seg, maxsplit=1, flags=re.IGNORECASE)[0].strip().rstrip('.?')
                    seg = self._strip_journal_volume_from_title(seg)
                    if len(seg) > 10 and not self._looks_like_venue(seg):
                        return clean_title(seg)
        
        return None
    
    def _looks_like_venue(self, title: str) -> bool:
        """True if the string is clearly a venue name, not a paper title."""
        if not title or len(title) < 15:
            return False
        t = title.strip().lower()
        # Common venue phrase starts (not paper titles)
        if re.match(r"^(in\s+)?(international|proceedings|conference|advances|annual|symposium|journal|transactions|workshop)\s", t):
            return True
        # Venue abbreviations in parens as the main content
        if re.search(r"^[^()]*\s*\((?:iclr|neurips|nips|icml|acl|emnlp|cvpr|eccv|iccv)\)\s*\.?$", t):
            return True
        return False

    def _strip_journal_volume_from_title(self, title: str) -> str:
        """Remove trailing '. Journal, vol(issue):pages' and leading 'In ' (venue fragment)."""
        if not title:
            return title
        title = title.strip()
        # Strip leading "In " (venue fragment that sometimes gets into title)
        if title.lower().startswith("in "):
            title = title[3:].strip()
        # Match ". Journal name, 9(8):1735–1780" or similar at end
        m = re.search(r'^(.+?)\.\s+[A-Za-z][^.]*,\s*\d+\(\d+\):\s*\d+', title)
        if m:
            return m.group(1).strip().rstrip('.')
        return title

    def _strip_leading_authors_from_title(self, text: str) -> str:
        """
        When format is "Author1 and Author2 Title" (no period), try to strip leading author block.
        Heuristic: after last " and ", if the remainder starts with two capitalized words (name),
        take the rest as title.
        """
        if not text or " and " not in text:
            return text
        parts = text.split(" and ", 1)
        if len(parts) != 2:
            return text
        remainder = parts[1].strip()
        words = remainder.split()
        if len(words) >= 3 and words[0][0].isupper() and words[1][0].isupper():
            return " ".join(words[2:]).strip()
        return remainder
    
    def _extract_authors(self, text: str) -> list:
        """
        Extract author names from citation text.
        
        Authors are typically at the start, ending with a period.
        """
        # Find text before first period followed by capital letter (title start)
        author_match = re.match(
            r'^([^.]+(?:\.\s*[A-Z]\.)*[^.]*?)\.(?=\s*[A-Z])',
            text
        )
        
        if author_match:
            author_text = author_match.group(1)
        else:
            # Fallback: take text up to first period
            period_pos = text.find('.')
            if period_pos > 0:
                author_text = text[:period_pos]
            else:
                return None
        
        # Split authors by 'and' or commas
        # Handle "Firstname Lastname, Firstname Lastname, and Firstname Lastname"
        author_text = re.sub(r',\s+and\s+', ', ', author_text, flags=re.IGNORECASE)
        author_parts = re.split(r'\s+and\s+|,\s+(?=[A-Z])', author_text)
        
        authors = []
        for part in author_parts:
            part = part.strip().rstrip('.,')
            if part and len(part) > 2:
                # Skip "et al."
                if part.lower() not in ['et al', 'et al.', 'others']:
                    authors.append(part)
        
        return authors[:10] if authors else None  # Max 10 authors
    
    def extract_from_arxiv(self, arxiv_id: str) -> Tuple[List[Citation], str]:
        """
        Extract citations from arXiv paper.
        Download PDF and extract.
        
        Args:
            arxiv_id: arXiv ID (e.g., '2301.12345')
            
        Returns:
            Tuple of (citations, paper_title)
        """
        import arxiv
        
        # Normalize arXiv ID
        arxiv_id = normalize_arxiv_id(arxiv_id)
        if not arxiv_id:
            raise ValueError(f"Invalid arXiv ID: {arxiv_id}")
        
        try:
            # Fetch paper
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(search.results())
            
            # Download PDF to temp location
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp_path = tmp.name
                try:
                    paper.download_pdf(filename=tmp_path)
                    citations, _ = self.extract_from_pdf(tmp_path)
                    # Use actual paper title
                    title = paper.title
                finally:
                    # Clean up temp file
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
            
            return citations, title
        
        except StopIteration:
            raise ValueError(f"arXiv paper not found: {arxiv_id}")
        except Exception as e:
            raise ValueError(f"Failed to extract from arXiv: {str(e)}")

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
        numbered_pattern = r'\[(\d+)\]\s*(.+?)(?=\[\d+\]|$)'
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
        # Pattern 1: arXiv:XXXX.XXXXX (with optional version)
        match = re.search(r'arXiv[:\s]+(\d{4}\.\d{4,5})(?:v\d+)?', text, re.IGNORECASE)
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
        # Authors typically end with a period after last name or "et al."
        
        # Find the first period that's likely after authors
        # (followed by a capital letter, indicating start of title)
        author_end_match = re.search(
            r'(?:et\s+al\.|[A-Z][a-z]+)\.\s+([A-Z][^.]*(?:\.[^.]*)*?)(?:\.\s*(?:In\s|CoRR|arXiv|Proceedings|Journal|Trans\.|IEEE|ACM|\d{4}))',
            text,
            re.IGNORECASE
        )
        if author_end_match:
            title = author_end_match.group(1).strip()
            # Clean up - remove trailing period
            title = title.rstrip('.')
            if len(title) > 10:
                return clean_title(title)
        
        # Strategy 3: Find sentence-like text between periods
        # Split by periods and find the longest segment that looks like a title
        sentences = re.split(r'\.\s+', text)
        
        # Skip first segment (likely authors) and last segment (likely venue/year)
        if len(sentences) > 2:
            # Look for the title among middle segments
            candidates = []
            for i, sent in enumerate(sentences[1:-1], 1):
                sent = sent.strip()
                # Title candidates: start with capital, reasonable length, not a venue
                if (sent and 
                    sent[0].isupper() and 
                    10 < len(sent) < 200 and
                    not re.match(r'^(In\s|Proceedings|Journal|Trans\.|IEEE|ACM|CoRR|arXiv)', sent, re.IGNORECASE)):
                    candidates.append((len(sent), sent))
            
            if candidates:
                # Return the longest candidate
                candidates.sort(reverse=True)
                return clean_title(candidates[0][1])
        
        # Strategy 4: Fallback - text before year minus author-like prefix
        if year:
            year_pos = text.find(str(year))
            if year_pos > 0:
                before_year = text[:year_pos]
                # Try to find title after first period
                period_match = re.search(r'\.\s*(.+?)$', before_year)
                if period_match:
                    title = period_match.group(1).strip().rstrip('.,')
                    if len(title) > 10:
                        return clean_title(title)
        
        return None
    
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

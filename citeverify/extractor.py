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
        
        # Extract arXiv ID
        arxiv_match = re.search(r'arXiv:(\d{4}\.\d{4,5})', text, re.IGNORECASE)
        arxiv_id = None
        if arxiv_match:
            arxiv_id = normalize_arxiv_id(arxiv_match.group(1))
        
        # Extract year (4-digit number)
        year = extract_year_from_text(text)
        
        # Extract URL
        url_match = re.search(r'https?://[^\s\)]+', text)
        url = url_match.group(0).rstrip('.,)') if url_match else None
        
        # Extract title (text in quotes or italics)
        title = None
        # Try double quotes first
        title_match = re.search(r'["""](.+?)["""]', text)
        if title_match:
            title = clean_title(title_match.group(1))
        else:
            # Try single quotes
            title_match = re.search(r"'(.+?)'", text)
            if title_match:
                title = clean_title(title_match.group(1))
            else:
                # Try to find title-like text (often before year)
                if year:
                    # Text between authors and year might be title
                    year_pos = text.find(str(year))
                    if year_pos > 0:
                        # Look for text segment before year
                        before_year = text[:year_pos].strip()
                        # Remove common author patterns
                        before_year = re.sub(r'^[A-Z][a-z]+(?:\s+[A-Z]\.?)+', '', before_year)
                        before_year = before_year.strip('.,;: ')
                        if len(before_year) > 10:
                            title = clean_title(before_year)
        
        # Extract authors (crude: text before year or title)
        authors = None
        if year:
            author_text = text[:text.find(str(year))].strip()
            # Split by 'and' or commas
            author_parts = re.split(r'\s+and\s+|,\s+(?=[A-Z])', author_text)
            authors = [a.strip().rstrip('.,') for a in author_parts if a.strip()][:5]  # Max 5
        
        # Extract journal (often after title, before year or DOI)
        journal = None
        journal_patterns = [
            r'In\s+([^,]+?)(?:,|\.|$)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Journal|Proceedings|Conference)',
        ]
        for pattern in journal_patterns:
            journal_match = re.search(pattern, text, re.IGNORECASE)
            if journal_match:
                journal = journal_match.group(1).strip('.,')
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

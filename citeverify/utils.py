"""Helper utility functions for CitationVerify."""

import re
from typing import Optional


def normalize_doi(doi: str) -> Optional[str]:
    """Normalize DOI string."""
    if not doi:
        return None
    
    # Remove common prefixes
    doi = doi.strip()
    if doi.startswith('doi:'):
        doi = doi[4:].strip()
    if doi.startswith('DOI:'):
        doi = doi[4:].strip()
    if doi.startswith('https://doi.org/'):
        doi = doi[16:].strip()
    if doi.startswith('http://doi.org/'):
        doi = doi[15:].strip()
    
    # Remove trailing punctuation
    doi = doi.rstrip('.,);:')
    
    return doi if doi else None


def normalize_arxiv_id(arxiv_id: str) -> Optional[str]:
    """Normalize arXiv ID string."""
    if not arxiv_id:
        return None
    
    arxiv_id = arxiv_id.strip()
    
    # Remove common prefixes
    if arxiv_id.startswith('arXiv:'):
        arxiv_id = arxiv_id[6:].strip()
    if arxiv_id.startswith('arxiv:'):
        arxiv_id = arxiv_id[6:].strip()
    
    # Extract version if present (e.g., 1234.5678v1 -> 1234.5678)
    match = re.match(r'(\d{4}\.\d{4,5})', arxiv_id)
    if match:
        return match.group(1)
    
    return arxiv_id if arxiv_id else None


def extract_year_from_text(text: str) -> Optional[int]:
    """Extract publication year (4-digit) from text. Prefer year at end, skip page ranges like 1929–1958."""
    matches = list(re.finditer(r'\b(19|20)\d{2}\b', text))
    if not matches:
        return None
    # Prefer last year (publication year often at end); skip if in page range pattern like "15(1):1929–1958"
    for m in reversed(matches):
        year_str = m.group(0)
        year = int(year_str)
        start, end = m.start(), m.end()
        before = text[max(0, start - 3) : start]
        after = text[end : end + 5] if end + 5 <= len(text) else ""
        # Skip if looks like page number: preceded by : and followed by – or - and digits
        if re.search(r'[:(]\s*$', before) and re.match(r'^[\s–\-]\s*\d', after):
            continue
        return year
    return int(matches[-1].group(0))


# Common short phrase concatenations (space dropped in PDF extraction)
_CONCATENATED_PHRASES = [
    ('asa', 'as a'),
    ('inthe', 'in the'),
    ('ofthe', 'of the'),
    ('tothe', 'to the'),
    ('forthe', 'for the'),
    ('withthe', 'with the'),
    ('aswell', 'as well'),
    ('suchas', 'such as'),
]


def clean_title(title: str) -> str:
    """Clean and normalize title text."""
    if not title:
        return ""
    
    # Fix hyphenated line breaks (e.g., "im- age" -> "image")
    title = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', title)
    
    # Remove extra whitespace
    title = re.sub(r'\s+', ' ', title)
    
    # Fix common short phrase concatenations (space dropped in PDFs)
    # e.g. "Grammar asa foreign language" -> "Grammar as a foreign language"
    for bad, good in _CONCATENATED_PHRASES:
        title = re.sub(r'\b' + re.escape(bad) + r'\b', good, title, flags=re.IGNORECASE)
    
    # Fix concatenated words from PDF extraction
    # This handles cases like "networkgrammars" -> "network grammars"
    title = fix_concatenated_words(title)
    
    # Remove common citation artifacts
    title = title.strip('.,;:')
    
    return title.strip()


def fix_concatenated_words(text: str) -> str:
    """
    Fix words that were concatenated due to PDF extraction issues.
    
    Uses a simple heuristic: look for long lowercase words and try to split them
    at common word boundaries.
    """
    if not text:
        return text
    
    words = text.split()
    fixed_words = []
    
    # Common English words that might appear at word boundaries
    common_suffixes = [
        'ing', 'tion', 'sion', 'ment', 'ness', 'able', 'ible', 'ful', 'less',
        'ous', 'ive', 'ary', 'ory', 'ical', 'ally', 'ward', 'wise', 'like'
    ]
    common_prefixes = [
        'un', 're', 'pre', 'dis', 'mis', 'non', 'over', 'under', 'sub', 'super',
        'anti', 'auto', 'semi', 'multi', 'trans', 'inter', 'intra'
    ]
    
    # Common short words that often get concatenated
    common_words = {
        'the', 'and', 'for', 'with', 'from', 'that', 'this', 'which', 'into',
        'over', 'under', 'about', 'after', 'before', 'between', 'through',
        'neural', 'network', 'networks', 'learning', 'learn', 'learns', 'deep',
        'machine', 'machines', 'model', 'models', 'attention', 'transformer',
        'language', 'natural', 'processing', 'sequence', 'sequences',
        'recurrent', 'convolutional', 'training', 'translation', 'recognition',
        'generation', 'classification', 'grammars', 'grammar', 'parsing',
        'semantic', 'syntactic', 'encoder', 'decoder', 'embedding', 'embeddings',
        'representation', 'representations', 'algorithms', 'algorithm', 'gpus',
        'gpu', 'limits', 'exploring', 'international', 'conference',
        'active', 'memory', 'replace', 'overfitting',
    }

    for word in words:
        # Skip short words
        if len(word) <= 8:
            fixed_words.append(word)
            continue
        # Keep whole if already a valid compound (e.g. overfitting, not "over fitting")
        if word.lower() in common_words:
            fixed_words.append(word)
            continue
        # Process long words: lowercase for split logic, but also handle mixed-case
        word_lower = word.lower()
        
        # Try to find a split point
        split_found = False
        
        for common in sorted(common_words, key=len, reverse=True):
            if len(common) >= 3 and common in word_lower:
                idx = word_lower.find(common)
                before = word[:idx]
                after = word[idx:]
                
                if idx > 2 and len(after) > 3:
                    if before.lower() in common_words or len(before) >= 3:
                        # Recursively fix parts (handles multiple concatenations)
                        fixed_words.extend(fix_concatenated_words(before).split())
                        fixed_words.extend(fix_concatenated_words(after).split())
                        split_found = True
                        break
                elif idx == 0 and len(after) > len(common) + 2:
                    remainder = word[len(common):]
                    if remainder.lower() in common_words or len(remainder) >= 4:
                        fixed_words.extend(fix_concatenated_words(word[:len(common)]).split())
                        fixed_words.extend(fix_concatenated_words(remainder).split())
                        split_found = True
                        break
        
        if not split_found:
            fixed_words.append(word)
    
    return ' '.join(fixed_words)

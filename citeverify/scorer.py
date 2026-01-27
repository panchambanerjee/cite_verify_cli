"""Citation quality scoring across multiple dimensions."""

from datetime import datetime
from .models import Citation, VerificationResult, QualityScore, VerificationStatus


class CitationQualityScorer:
    """Score citation quality across multiple dimensions."""
    
    def score(self, citation: Citation, verification: VerificationResult) -> QualityScore:
        """
        Calculate quality score (0-100).
        
        Breakdown:
        - Verification: 25 points
        - Peer review: 20 points
        - Recency: 15 points
        - Citations: 15 points
        - Accessibility: 15 points
        - Venue: 10 points
        """
        
        verification_score = self._score_verification(verification)
        peer_review_score = self._score_peer_review(verification)
        recency_score = self._score_recency(citation, verification)
        citations_score = self._score_citations(verification)
        accessibility_score = self._score_accessibility(verification)
        venue_score = self._score_venue(verification)
        
        total = (
            verification_score +
            peer_review_score +
            recency_score +
            citations_score +
            accessibility_score +
            venue_score
        )
        
        return QualityScore(
            total=total,
            verification=verification_score,
            peer_review=peer_review_score,
            recency=recency_score,
            citations=citations_score,
            accessibility=accessibility_score,
            venue=venue_score,
            explanation=self._generate_explanation(
                verification_score, peer_review_score, recency_score,
                citations_score, accessibility_score, venue_score
            )
        )
    
    def _score_verification(self, verification: VerificationResult) -> int:
        """25 points for verification quality."""
        
        if verification.status == VerificationStatus.VERIFIED:
            if len(verification.verified_sources) >= 2:
                return 25
            elif verification.confidence > 0.95:
                return 20
            else:
                return 15
        elif verification.status == VerificationStatus.PARTIAL:
            return 10
        else:
            return 0
    
    def _score_peer_review(self, verification: VerificationResult) -> int:
        """20 points for peer review status."""
        metadata = verification.metadata
        
        # Check publication type
        pub_type = metadata.get('type', '')
        
        if pub_type == 'journal-article':
            return 20
        elif pub_type in ['proceedings-article', 'book-chapter']:
            return 15
        elif pub_type == 'posted-content':  # Preprint
            return 10
        elif verification.arxiv_id and not verification.doi:
            return 10  # arXiv preprint
        elif verification.arxiv_id and verification.doi:
            return 20  # Published version exists
        
        # Check if it's from Semantic Scholar (might have more info)
        if 'semantic_scholar' in verification.verified_sources:
            # Assume peer-reviewed if it has a venue
            if metadata.get('venue') or metadata.get('journal'):
                return 15
        
        return 5
    
    def _score_recency(self, citation: Citation, verification: VerificationResult) -> int:
        """15 points for recency."""
        year = verification.matched_year or citation.year
        
        if not year:
            return 8  # Neutral
        
        current_year = datetime.now().year
        age = current_year - year
        
        if age <= 2:
            return 15
        elif age <= 5:
            return 12
        elif age <= 10:
            return 8
        elif age <= 20:
            return 5
        else:
            return 3  # Classic work
    
    def _score_citations(self, verification: VerificationResult) -> int:
        """15 points for citation impact."""
        citation_count = verification.metadata.get('citationCount', 0)
        
        if citation_count >= 1000:
            return 15
        elif citation_count >= 500:
            return 12
        elif citation_count >= 100:
            return 10
        elif citation_count >= 20:
            return 7
        elif citation_count >= 5:
            return 5
        elif citation_count >= 1:
            return 3
        else:
            # Give benefit of doubt to recent papers
            if verification.matched_year and verification.matched_year >= datetime.now().year - 1:
                return 5
            return 0
    
    def _score_accessibility(self, verification: VerificationResult) -> int:
        """15 points for accessibility."""
        # Check for open access indicators
        if verification.arxiv_id:
            return 15  # arXiv is always open
        
        metadata = verification.metadata
        
        # CrossRef license info
        if 'license' in metadata and metadata['license']:
            for license_info in metadata['license']:
                url = license_info.get('URL', '')
                if 'creativecommons.org' in url:
                    return 15
        
        # Semantic Scholar open access info
        if 'openAccessPdf' in metadata and metadata['openAccessPdf']:
            return 15
        
        # Has DOI (might be accessible via institution)
        if verification.doi:
            return 10
        
        return 5  # Probably paywalled
    
    def _score_venue(self, verification: VerificationResult) -> int:
        """10 points for venue quality."""
        metadata = verification.metadata
        
        # Check if it's a known top venue
        # (In production, use venue ranking database)
        container_title = metadata.get('container-title', [])
        if isinstance(container_title, list) and container_title:
            container_title = container_title[0].lower()
        elif isinstance(container_title, str):
            container_title = container_title.lower()
        else:
            container_title = ''
        
        top_venues = [
            'nature', 'science', 'cell', 'lancet',
            'neurips', 'icml', 'iclr', 'cvpr', 'aaai',
            'acl', 'emnlp', 'naacl', 'iccv', 'eccv'
        ]
        
        if any(venue in container_title for venue in top_venues):
            return 10
        
        # Check publisher
        publisher = metadata.get('publisher', '').lower()
        reputable = ['springer', 'elsevier', 'ieee', 'acm', 'oxford', 'cambridge', 'wiley']
        
        if any(pub in publisher for pub in reputable):
            return 8
        
        # Check if it's a journal (vs conference)
        pub_type = metadata.get('type', '')
        if pub_type == 'journal-article':
            return 7
        
        return 5
    
    def _generate_explanation(self, v, p, r, c, a, ve) -> str:
        """Generate human-readable explanation."""
        parts = []
        
        if v >= 20:
            parts.append("✓ Verified")
        elif v < 10:
            parts.append("⚠ Verification issues")
        
        if p >= 15:
            parts.append("✓ Peer-reviewed")
        elif p == 10:
            parts.append("📄 Preprint")
        
        if r <= 5:
            parts.append("📅 Older reference")
        
        if c >= 12:
            parts.append("🌟 Highly cited")
        
        if a >= 15:
            parts.append("🔓 Open access")
        elif a <= 5:
            parts.append("🔒 Paywalled")
        
        return " • ".join(parts) if parts else "Standard citation"

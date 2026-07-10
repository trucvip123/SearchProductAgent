"""Query parsing utilities — extract structured spec constraints from free-text queries."""

import re
from typing import List


_SPEC_QUERY_PATTERNS = [
    re.compile(
        r"\b(?:vga|gpu|card\s*man\s*hinh|card\s*màn\s*hình|cpu|ram|ssd|hdd|storage|interface)\s*[:=\-]\s*([^,;\n]+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bc[oó]\s+(?:vga|gpu|cpu|ram|ssd|hdd|storage|interface)\s*[:=\-]?\s*([^,;\n]+)",
        re.IGNORECASE,
    ),
]


def _extract_query_spec_terms(query: str) -> List[str]:
    """Extract spec constraints from free-text query, e.g. 'vga: matrox g200e 16mb'."""
    text = (query or "").strip()
    if not text:
        return []

    terms: List[str] = []
    for pattern in _SPEC_QUERY_PATTERNS:
        for match in pattern.finditer(text):
            value = re.sub(r"\s+", " ", (match.group(1) or "").strip(" .,:;|"))
            if len(value) >= 2:
                terms.append(value)

    unique_terms: List[str] = []
    seen: set = set()
    for term in terms:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            unique_terms.append(term)
    return unique_terms

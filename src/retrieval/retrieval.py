"""_rrf_merge stays here as a pure algorithm utility.
"""

from typing import List, Dict, Any


def _rrf_merge(
    fts_rows: List,
    vec_rows: List,
    kw_rows: List,
    key_fn,
    max_results: int,
    k: int = 60,
) -> List:
    """Merge FTS + Vector + Keyword results using Reciprocal Rank Fusion.

    Rows are deduplicated per source before scoring so repeated items
    do not get unfair score boosts from the same retrieval branch.
    """

    def _dedupe_rows(rows: List) -> List:
        seen = set()
        unique_rows = []
        for row in rows:
            key = key_fn(row)
            if key in seen:
                continue
            seen.add(key)
            unique_rows.append(row)
        return unique_rows

    fts_rows = _dedupe_rows(fts_rows)
    vec_rows = _dedupe_rows(vec_rows)
    kw_rows = _dedupe_rows(kw_rows)

    scores: Dict[str, float] = {}
    store: Dict[str, Any] = {}

    for rank, row in enumerate(fts_rows, start=1):
        key = key_fn(row)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        store.setdefault(key, row)

    for rank, row in enumerate(vec_rows, start=1):
        key = key_fn(row)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
        store.setdefault(key, row)

    for rank, row in enumerate(kw_rows, start=1):
        key = key_fn(row)
        if key not in scores:
            scores[key] = 1.0 / (k * 2 + rank)
            store[key] = row

    ranked = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [(store[rk], round(scores[rk], 5)) for rk in ranked[:max_results]]

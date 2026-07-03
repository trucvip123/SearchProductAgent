from typing import Optional, List, Dict, Any
from os import getenv

import httpx

from .logging_utils import _log


async def _get_query_embedding(query: str) -> Optional[List[float]]:
    """Call Ollama embeddings API and return a query vector."""
    embed_model = getenv("EMBEDDING_MODEL", "nomic-embed-text")
    base_url = getenv("OPENAI_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    api_key = getenv("OPENAI_API_KEY", "ollama")
    _log("EMBED", f"model={embed_model}, query_len={len(query)}")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{base_url}/embeddings",
                json={"model": embed_model, "input": query},
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            vec = resp.json()["data"][0]["embedding"]
            _log("EMBED", f"OK, dimensions={len(vec)}")
            return vec
    except Exception as exc:
        _log("EMBED", f"Skipped (non-fatal): {exc}")
        return None


def _rrf_merge(
    fts_rows: List,
    vec_rows: List,
    kw_rows: List,
    key_fn,
    max_results: int,
    k: int = 60,
) -> List:
    """Merge FTS + Vector + Keyword results using Reciprocal Rank Fusion."""
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

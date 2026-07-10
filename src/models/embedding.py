"""Embedding model — async query embedding via OpenAI-compatible /embeddings endpoint.

Canonical implementation. tools/normal/retrieval.py re-exports _get_query_embedding
from here for backward compatibility.
"""

from typing import Optional, List

import httpx

from tools.normal.logging_utils import _log
from .config import get_llm_base_url, get_llm_api_key, get_embedding_model


async def _get_query_embedding(query: str) -> Optional[List[float]]:
    """Call the configured embeddings endpoint and return the query vector.

    Returns None (non-fatal) on any error so callers can fall back gracefully.
    """
    embed_model = get_embedding_model()
    base_url = get_llm_base_url()
    api_key = get_llm_api_key()
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

"""Data models, LLM factory, embedding, and model provider configuration."""

from dataclasses import dataclass, fields, asdict
from typing import Optional, List, Dict, Any


@dataclass
class ProductMemory:
    """Structured memory for one product search turn."""

    product_type: Optional[str] = None
    brand: Optional[str] = None
    series: Optional[str] = None
    model: Optional[str] = None
    cpu: Optional[str] = None
    gpu: Optional[str] = None
    ram: Optional[str] = None
    storage: Optional[str] = None
    capacity: Optional[str] = None
    interface: Optional[str] = None
    price_range: Optional[str] = None
    product_link: Optional[str] = None

    def to_search_tokens(self) -> List[str]:
        tokens = []
        for f in fields(self):
            val = getattr(self, f.name)
            if val and isinstance(val, str) and val.strip():
                tokens.append(val.strip())
        return tokens

    def to_log_dict(self) -> Dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class SearchIntent:
    """Normalized intent extracted from query and structured memory."""

    product_type: Optional[str] = None
    brand: Optional[str] = None
    series: Optional[str] = None
    model: Optional[str] = None
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    price_text: Optional[str] = None

    def to_log_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


# LLM / embedding / provider config
from .config import (
    get_llm_base_url,
    get_llm_api_key,
    get_local_model,
    get_embedding_model,
    get_query_normalizer_timeout,
    LOCAL_MODEL,
    EMBEDDING_MODEL,
    LLM_BASE_URL,
    LLM_API_KEY,
)
from .llm import _build_llm
from .embedding import _get_query_embedding

__all__ = [
    # data models
    "ProductMemory",
    "SearchIntent",
    # config
    "get_llm_base_url",
    "get_llm_api_key",
    "get_local_model",
    "get_embedding_model",
    "get_query_normalizer_timeout",
    "LOCAL_MODEL",
    "EMBEDDING_MODEL",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    # LLM factory
    "_build_llm",
    # embedding
    "_get_query_embedding",
]

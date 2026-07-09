import asyncio
import json
import re
import socket
import time
import traceback
from os import getenv
from typing import Optional, Any, List

import asyncpg
from langchain_core.tools import tool
from pydantic import BaseModel, Field, field_validator, model_validator

from .db_pool import get_db_pool
from .error_utils import _error_json, _product_error_message
from .intent_filters import (
    _build_search_intent,
    _build_metadata_filter_clauses,
    _deduplicate_products,
    _expand_query_with_product_type_aliases,
    _filter_products_by_intent,
    _filter_products_with_specific_price,
    _is_price_query,
    _normalize_query_text,
)
from .logging_utils import _log
from .models import ProductMemory
from .query_normalizer import normalize_query_with_llm
from .retrieval import _get_query_embedding, _rrf_merge


def _is_vector_trace_enabled() -> bool:
    return getenv("VECTOR_TRACE_LOGS", "1").strip().lower() not in {"0", "false", "no", "off"}


def _vector_preview(vec: List[float], max_items: int = 8) -> str:
    if not vec:
        return "[]"
    preview = ", ".join(f"{x:.4f}" for x in vec[:max_items])
    suffix = ", ..." if len(vec) > max_items else ""
    return f"[{preview}{suffix}]"


def _normalize_db_host(raw_host: str) -> str:
    """Normalize host value loaded from env (trim spaces/quotes and strip scheme/path)."""
    host = (raw_host or "").strip().strip("\"'")
    if not host:
        return ""

    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0]
    return host.strip()


def _candidate_db_hosts(host: str) -> List[str]:
    """Build candidate hosts, including Neon canonical fallback from '*-pooler.<host>' form."""
    candidates: List[str] = []
    base = _normalize_db_host(host)
    if base:
        candidates.append(base)

    if "-pooler." in base:
        neon_canonical = base.split("-pooler.", 1)[1].strip()
        if neon_canonical and neon_canonical not in candidates:
            candidates.append(neon_canonical)

    return candidates


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
    seen = set()
    for term in terms:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            unique_terms.append(term)
    return unique_terms


class SearchProductsArgs(BaseModel):
    """Schema tham số cho tool search_products."""

    user_query: str = Field(default="", description="Câu người dùng gõ nguyên văn. Nếu để trống, tự động tổng hợp từ các structured fields.")
    max_results: int = Field(default=20, description="Số lượng kết quả tối đa (mặc định 20).")
    product_type: Optional[str] = Field(default=None, description='Loại thiết bị. VD: "ổ cứng ngoài", "máy chủ", "laptop".')
    brand: Optional[str] = Field(default=None, description='Hãng sản xuất. VD: "WD", "Dell", "HPE", "Synology".')
    series: Optional[str] = Field(default=None, description='Dòng sản phẩm. VD: "My Book", "PowerEdge", "ThinkPad".')
    model: Optional[str] = Field(default=None, description='Model cụ thể. VD: "R740xd", "DS223j", "1381".')
    cpu: Optional[str] = Field(default=None, description='CPU. VD: "Gold 6248", "E-2434".')
    ram: Optional[str] = Field(default=None, description='RAM. VD: "128GB", "32GB ECC".')
    storage: Optional[str] = Field(default=None, description='Lưu trữ gắn trong. VD: "2TB SSD".')
    capacity: Optional[str] = Field(default=None, description='Dung lượng ổ cứng ngoài / NAS. VD: "3TB", "8TB".')
    interface: Optional[str] = Field(default=None, description='Giao tiếp. VD: "USB 3.0", "PCIe 4.0".')
    price_range: Optional[str] = Field(default=None, description='Khoảng giá. VD: "dưới 5 triệu", "10-20 triệu".')
    product_link: Optional[str] = Field(default=None, description='Link sản phẩm. VD: "https://example.com/product/123".')

    @field_validator("user_query", mode="before")
    @classmethod
    def _empty_user_query_to_str(cls, v: Any) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return ""
        return str(v)

    @model_validator(mode="after")
    def _fill_user_query(self) -> "SearchProductsArgs":
        if not self.user_query.strip():
            tokens = [
                v for v in [
                    self.product_type,
                    self.brand,
                    self.series,
                    self.model,
                    self.cpu,
                    self.ram,
                    self.storage,
                    self.capacity,
                    self.interface,
                    self.price_range,
                ]
                if v
            ]
            self.user_query = " ".join(tokens) if tokens else "(unknown)"
        return self

    @field_validator("max_results", mode="before")
    @classmethod
    def _coerce_max_results(cls, v: Any) -> int:
        if v is None or (isinstance(v, str) and not v.strip()):
            return 5
        try:
            return int(v)
        except (TypeError, ValueError):
            return 5

    @field_validator("price_range", mode="before")
    @classmethod
    def _normalize_price_range(cls, v: Any) -> Any:
        if v is None:
            return None

        if isinstance(v, dict):
            min_raw = v.get("min", v.get("gte", v.get("gt")))
            max_raw = v.get("max", v.get("lte", v.get("lt")))

            parts = []
            if min_raw is not None:
                parts.append(f"min={min_raw}")
            if max_raw is not None:
                parts.append(f"max={max_raw}")
            return " ".join(parts) if parts else str(v)

        return v

    @field_validator(
        "product_type",
        "brand",
        "series",
        "model",
        "cpu",
        "ram",
        "storage",
        "capacity",
        "interface",
        "price_range",
        "product_link",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v


@tool(args_schema=SearchProductsArgs)
async def search_products(
    user_query: str,
    max_results: int = 20,
    product_type: Optional[str] = None,
    brand: Optional[str] = None,
    series: Optional[str] = None,
    model: Optional[str] = None,
    cpu: Optional[str] = None,
    ram: Optional[str] = None,
    storage: Optional[str] = None,
    capacity: Optional[str] = None,
    interface: Optional[str] = None,
    price_range: Optional[str] = None,
    product_link: Optional[str] = None,
) -> str:
    vector_trace = _is_vector_trace_enabled()

    memory = ProductMemory(
        product_type=product_type,
        brand=brand,
        series=series,
        model=model,
        cpu=cpu,
        ram=ram,
        storage=storage,
        capacity=capacity,
        interface=interface,
        price_range=price_range,
        product_link=product_link,
    )
    memory_tokens = memory.to_search_tokens()

    raw_query = getenv("RUN_USER_QUERY", user_query).strip()
    fallback_query = _normalize_query_text(raw_query)
    base_query = await normalize_query_with_llm(raw_query=raw_query, fallback_query=fallback_query)
    if memory_tokens:
        extra = [t for t in memory_tokens if t.lower() not in base_query.lower()]
        effective_query = " ".join(extra + [base_query]) if extra else base_query
    else:
        effective_query = base_query

    _log("START", f"user_query='{user_query}', max_results={max_results}")
    if raw_query != fallback_query:
        _log("NORMALIZE", f"fallback_query='{fallback_query}' from raw='{raw_query}'")
    if fallback_query != base_query:
        _log("NORMALIZE", f"final_normalized_query='{base_query}' from fallback='{fallback_query}'")
    _log("MEMORY", f"ProductMemory={memory.to_log_dict()}")

    intent = _build_search_intent(memory, base_query, effective_query)
    expanded_effective_query = _expand_query_with_product_type_aliases(effective_query, intent.product_type)
    if expanded_effective_query != effective_query:
        _log(
            "NORMALIZE",
            f"product_type_expanded_query='{expanded_effective_query}' from effective='{effective_query}'",
        )
    effective_query = expanded_effective_query
    _log("GUARD", f"base_query='{base_query}', effective_query='{effective_query}'")
    _log("INTENT", f"SearchIntent={intent.to_log_dict()}")

    fts_seed = " ".join(memory_tokens) if memory_tokens else effective_query
    fts_text = _expand_query_with_product_type_aliases(fts_seed, intent.product_type)
    _log("HYBRID", f"fts_text='{fts_text}'")

    kw_pats: List[str] = [f"%{t}%" for t in memory_tokens]
    for t in re.findall(r"\b[A-Za-z]{1,6}-?\d{3,5}[A-Za-z0-9.-]*\b", effective_query, re.IGNORECASE):
        p = f"%{t.upper()}%"
        if p not in kw_pats:
            kw_pats.append(p)
    kw_pats = kw_pats[:12]

    db_host = _normalize_db_host(getenv("POSTGRES_HOST", "localhost"))
    db_port = int(getenv("POSTGRES_PORT", "5432"))
    db_name = getenv("POSTGRES_DB", "server_products")
    db_user = getenv("POSTGRES_USER", "postgres")
    db_password = getenv("POSTGRES_PASSWORD", "")
    db_ssl_mode = getenv("POSTGRES_SSLMODE", "require").strip().lower()
    db_table = getenv("POSTGRES_TABLE", "products")

    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", db_table):
        _log("ERROR", f"Invalid table name: '{db_table}'")
        return _error_json(f"Tên bảng không hợp lệ: '{db_table}'")

    safe_pw = "***" if db_password else "(empty)"
    _log(
        "CONFIG",
        (
            f"Connecting PostgreSQL host={db_host} port={db_port} db={db_name} "
            f"user={db_user} table={db_table} password={safe_pw} sslmode={db_ssl_mode}"
        ),
    )

    candidate_hosts = _candidate_db_hosts(db_host)
    if not candidate_hosts:
        _log("ERROR", "POSTGRES_HOST is empty after normalization")
        return _error_json("POSTGRES_HOST đang rỗng hoặc không hợp lệ.")

    selected_host: Optional[str] = None
    for candidate in candidate_hosts:
        try:
            addr_infos = socket.getaddrinfo(candidate, db_port, type=socket.SOCK_STREAM)
            resolved_addresses = sorted({info[4][0] for info in addr_infos if info and len(info) >= 5 and info[4]})
            sample = ", ".join(resolved_addresses[:3]) if resolved_addresses else "(no addresses)"
            _log("DNS", f"Resolved host '{candidate}' -> {sample}")
            selected_host = candidate
            break
        except socket.gaierror as e:
            _log("DNS", f"Resolve failed for host '{candidate}': {e}")

    if not selected_host:
        return _error_json(
            f"Không phân giải được tên máy chủ DB '{db_host}'. Kiểm tra POSTGRES_HOST hoặc DNS mạng."
        )

    if selected_host != db_host:
        _log("DNS", f"Using fallback host '{selected_host}' instead of '{db_host}'")
        db_host = selected_host

    try:
        pool_min_size = int(getenv("POSTGRES_POOL_MIN_SIZE", "1"))
        pool_max_size = int(getenv("POSTGRES_POOL_MAX_SIZE", "10"))
        pool = await get_db_pool(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
            min_size=pool_min_size,
            max_size=pool_max_size,
            ssl_mode=db_ssl_mode,
        )
        _log("CONNECT", "Acquiring PostgreSQL connection from pool")

        async with pool.acquire() as conn:
            col_rows = await conn.fetch(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = $1
                ORDER BY ordinal_position
                """,
                db_table,
            )
            columns = {row["column_name"] for row in col_rows}
            if not columns:
                raise ValueError(f"Bảng '{db_table}' không tồn tại hoặc không có cột nào.")

            _log("SCHEMA", f"Detected columns in '{db_table}': {sorted(columns)}")
            has_embedding_col = "embedding" in columns
            _log("HYBRID", f"has_embedding_col={has_embedding_col}")

            products = []

            _log("SCHEMA", "n8n_vectors -> Hybrid Vector + FTS + Keyword")
            metadata_clauses, metadata_params = _build_metadata_filter_clauses(
                intent,
                {
                    "brand": ["text", "metadata::text"],
                    "series": ["text", "metadata::text"],
                    "model": ["text", "metadata::text"],
                },
            )

            # Add free-text spec constraints (e.g. VGA/GPU/CPU/RAM after ':' tokens).
            spec_terms = _extract_query_spec_terms(effective_query)
            for spec_term in spec_terms:
                metadata_params.append(f"%{spec_term}%")
                param_idx = len(metadata_params)
                metadata_clauses.append(f"(text ILIKE ${param_idx} OR metadata::text ILIKE ${param_idx})")

            metadata_where = " AND ".join(metadata_clauses)
            _log("HYBRID", f"metadata_where='{metadata_where}' metadata_params={metadata_params}")
            if spec_terms:
                _log("HYBRID", f"query_spec_terms={spec_terms}")

            vec_rows_n8n: List = []
            if has_embedding_col:
                vec = await _get_query_embedding(effective_query)
                if vec:
                    if vector_trace:
                        _log(
                            "VECTOR_TRACE",
                            (
                                f"effective_query='{effective_query}', "
                                f"dims={len(vec)}, preview={_vector_preview(vec)}"
                            ),
                        )
                    emb_str = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
                    try:
                        t0 = time.perf_counter()
                        params = list(metadata_params)
                        vector_idx = len(params) + 1
                        limit_idx = len(params) + 2
                        where_sql = f" WHERE {metadata_where}" if metadata_where else ""
                        vec_sql = f"""
                            SELECT id, text, metadata
                            FROM {db_table}
                            {where_sql}
                            ORDER BY embedding <=> ${vector_idx}::vector
                            LIMIT ${limit_idx}
                        """
                        if vector_trace:
                            vec_sql_one_line = " ".join(vec_sql.split())
                            _log("VECTOR_TRACE", f"sql={vec_sql_one_line}")
                            _log(
                                "VECTOR_TRACE",
                                (
                                    f"metadata_params={metadata_params}, "
                                    f"vector_param='vector({len(vec)})', "
                                    f"limit={max_results * 4}"
                                ),
                            )
                        params.extend([emb_str, max_results * 4])
                        vec_rows_n8n = await conn.fetch(vec_sql, *params)
                        _log("HYBRID", f"Vector(n8n)={len(vec_rows_n8n)} rows ({1000 * (time.perf_counter() - t0):.0f}ms)")
                        if vec_rows_n8n:
                            vector_products = []
                            for row in vec_rows_n8n:
                                try:
                                    text_value = (row.get("text") if hasattr(row, 'get') else getattr(row, 'text', '')) or ""
                                    row_id = str(row.get("id") if hasattr(row, 'get') else getattr(row, 'id', ''))
                                    m_name = re.search(r"Tên sản phẩm:\s*(.+?)(?:\.|Giá)", text_value)
                                    product_name = m_name.group(1).strip() if m_name else "N/A"
                                    vector_products.append(
                                        {
                                            "id": row_id,
                                            "tên": product_name,
                                        }
                                    )
                                except (AttributeError, KeyError, TypeError) as e:
                                    _log("VECTOR", f"Failed to parse vector row: {type(e).__name__}: {e}")
                                    continue
                            _log("HYBRID", f"Vector(n8n) product_list={json.dumps(vector_products, ensure_ascii=False)}")
                        if vector_trace and vec_rows_n8n:
                            top_ids = [str(r.get("id")) for r in vec_rows_n8n[:5]]
                            _log("VECTOR_TRACE", f"top_ids={top_ids}")
                    except Exception as exc:
                        _log("HYBRID", f"Vector(n8n) failed: {exc}")
                elif vector_trace:
                    _log("VECTOR_TRACE", "embedding unavailable, vector search skipped")

            fts_rows_n8n: List = []
            try:
                t0 = time.perf_counter()
                params = list(metadata_params)
                query_idx = len(params) + 1
                limit_idx = len(params) + 2
                where_parts = [f"to_tsvector('simple', coalesce(text,'')) @@ plainto_tsquery('simple', ${query_idx})"]
                if metadata_where:
                    where_parts.append(metadata_where)
                fts_sql = f"""
                    SELECT id, text, metadata
                    FROM {db_table}
                    WHERE {' AND '.join(where_parts)}
                    ORDER BY ts_rank_cd(to_tsvector('simple', coalesce(text,'')),
                                        plainto_tsquery('simple', ${query_idx})) DESC
                    LIMIT ${limit_idx}
                """
                params.extend([fts_text, max_results * 4])
                fts_rows_n8n = await conn.fetch(fts_sql, *params)
                _log("HYBRID", f"FTS(n8n)={len(fts_rows_n8n)} rows ({1000 * (time.perf_counter() - t0):.0f}ms)")
            except Exception as exc:
                _log("HYBRID", f"FTS(n8n) failed (non-fatal): {exc}")

            kw_rows_n8n: List = []
            if kw_pats:
                try:
                    t0 = time.perf_counter()
                    params = list(metadata_params)
                    kw_idx = len(params) + 1
                    limit_idx = len(params) + 2
                    where_parts = [f"text ILIKE ANY(${kw_idx}::text[])"]
                    if metadata_where:
                        where_parts.append(metadata_where)
                    kw_sql = f"""
                        SELECT id, text, metadata
                        FROM {db_table}
                        WHERE {' AND '.join(where_parts)}
                        LIMIT ${limit_idx}
                    """
                    params.extend([kw_pats, max_results * 2])
                    kw_rows_n8n = await conn.fetch(kw_sql, *params)
                    _log("HYBRID", f"Keyword(n8n)={len(kw_rows_n8n)} rows ({1000 * (time.perf_counter() - t0):.0f}ms)")
                except Exception as exc:
                    _log("HYBRID", f"Keyword(n8n) failed: {exc}")

            _log("HYBRID", f"RRF input: fts_rows={len(fts_rows_n8n)}, vec_rows={len(vec_rows_n8n)}, kw_rows={len(kw_rows_n8n)}")
            
            try:
                merged_n8n = _rrf_merge(
                    fts_rows_n8n,
                    vec_rows_n8n,
                    kw_rows_n8n,
                    lambda r: str((r.get("id") if hasattr(r, 'get') else getattr(r, 'id', '')) or ""),
                    max_results,
                )
            except AttributeError as ae:
                _log("ERROR", f"AttributeError in _rrf_merge: {ae}")
                _log("ERROR", f"fts_rows_n8n type: {type(fts_rows_n8n)}, first: {type(fts_rows_n8n[0]) if fts_rows_n8n else 'empty'}")
                _log("ERROR", f"vec_rows_n8n type: {type(vec_rows_n8n)}, first: {type(vec_rows_n8n[0]) if vec_rows_n8n else 'empty'}")
                _log("ERROR", f"kw_rows_n8n type: {type(kw_rows_n8n)}, first: {type(kw_rows_n8n[0]) if kw_rows_n8n else 'empty'}")
                _log("ERROR", traceback.format_exc())
                # Graceful fallback: use FTS results directly instead of failing
                merged_n8n = [(row, 1.0 / (60 + rank)) for rank, row in enumerate(fts_rows_n8n[:max_results], start=1)]
                if not merged_n8n:
                    merged_n8n = [(row, 1.0 / (60 + rank)) for rank, row in enumerate(vec_rows_n8n[:max_results], start=1)]
                _log("ERROR", f"Fallback to direct rows: {len(merged_n8n)} results")
            
            _log("HYBRID", f"RRF merged(n8n)={len(merged_n8n)}")
            if not merged_n8n:
                _log("RESULT", "No products found in database")
                return json.dumps(
                    {
                        "status": "no_products",
                        "message": f"Không tìm thấy sản phẩm phù hợp với: '{effective_query}'",
                        "query": effective_query,
                        "products": [],
                    },
                    ensure_ascii=False,
                )
                
            for row, score in merged_n8n:
                try:
                    # Defensive: handle both dict-like and asyncpg.Record access
                    text_value = (row.get("text") if hasattr(row, 'get') else getattr(row, 'text', '')) or ""
                    row_id = str(row.get("id") if hasattr(row, 'get') else getattr(row, 'id', ''))
                    name = "N/A"
                    brand_value = "Unknown"
                    price = "N/A"
                    config = "N/A"
                    _log("HYBRID", f"Parsing n8n row id={row_id} score={score} text_len={len(text_value)}")

                    m_name = re.search(r"Tên sản phẩm:\s*(.+?)(?:\.|Giá)", text_value)
                    if m_name:
                        name = m_name.group(1).strip()
                    m_price = re.search(r"Giá bán:\s*([^\n.]+)", text_value)
                    if m_price:
                        price = m_price.group(1).strip()
                    m_config = re.search(r"Thông số kỹ thuật:\s*(.+?)(?:Trang sản phẩm:|$)", text_value, re.DOTALL)
                    if m_config:
                        config = m_config.group(1).strip()

                    product_link_from_text = "N/A"
                    m_link = re.search(r"Trang sản phẩm:\s*(https?://[^\s\)]+|[^\s\)]+)", text_value, re.IGNORECASE)
                    if m_link:
                        product_link_from_text = m_link.group(1).strip()

                    for candidate in ["DELL", "HPE", "ASUS", "SSN", "LENOVO", "SUPERMICRO", "AMD", "INTEL", "WD", "SEAGATE", "SYNOLOGY"]:
                        if candidate in text_value.upper():
                            brand_value = candidate
                            break
                    products.append(
                        {
                            "id": row_id,
                            "tên": name,
                            "giá": price,
                            "hãng": brand_value,
                            "cấu_hình": config,
                            "link_sản_phẩm": product_link_from_text,
                            "_score": score,
                            "_text": text_value,
                        }
                    )
                except (AttributeError, KeyError, TypeError) as e:
                    _log("ERROR", f"Failed to parse row: {type(e).__name__}: {e}")
                    _log("ERROR", f"Row type: {type(row).__name__}, Row: {row}")
                    continue

            _log("RESULT", f"Products parsed={len(products)}")
            if products:
                preview = products[: min(3, len(products))]
                _log("RESULT", f"Preview top products={json.dumps(preview, ensure_ascii=False)}")

            if products:
                original_count = len(products)
                products = _deduplicate_products(products)
                if len(products) < original_count:
                    _log("DEDUP", f"Removed {original_count - len(products)} duplicate products: {original_count} → {len(products)}")

            if products and any([
                intent.brand,
                intent.product_type,
                intent.series,
                intent.model,
                intent.price_min is not None,
                intent.price_max is not None,
            ]):
                original_count = len(products)
                products = _filter_products_by_intent(products, intent)
                _log("FILTER", f"Intent filter applied: filtered {original_count} → {len(products)} products")

            if (_is_price_query(base_query) or _is_price_query(effective_query)) and products:
                original_count = len(products)
                products = _filter_products_with_specific_price(products)
                _log("FILTER", f"Price query detected: filtered {original_count} → {len(products)} products")
                if not products:
                    _log("FILTER", "No products with specific prices found")

            if not products:
                _log("RESULT", "No products found in database")
                return json.dumps(
                    {
                        "status": "no_products",
                        "message": f"Không tìm thấy sản phẩm phù hợp với: '{effective_query}'",
                        "query": effective_query,
                        "products": [],
                    },
                    ensure_ascii=False,
                )

            for product in products:
                product.pop("_text", None)

            _log("DONE", f"Successfully found {len(products)} products from PostgreSQL")
            return json.dumps(
                {
                    "status": "success",
                    "count": len(products),
                    "query": effective_query,
                    "products": products,
                },
                ensure_ascii=False,
                indent=2,
            )

    except asyncpg.TooManyConnectionsError:
        _log("ERROR", "Too many connections")
        _log("ERROR", traceback.format_exc())
        return _error_json("Cơ sở dữ liệu quá tải. Vui lòng thử lại sau.")
    except asyncpg.InvalidPasswordError:
        _log("ERROR", "Invalid password")
        _log("ERROR", traceback.format_exc())
        return _error_json("Lỗi xác thực cơ sở dữ liệu. Kiểm tra mật khẩu.")
    except asyncpg.PostgresError as e:
        _log("ERROR", f"PostgreSQL error: {e}")
        _log("ERROR", traceback.format_exc())
        return _error_json(f"Lỗi cơ sở dữ liệu: {str(e)}")
    except socket.gaierror as e:
        _log("ERROR", f"DNS resolve error for host '{db_host}': {e}")
        _log("ERROR", traceback.format_exc())
        return _error_json(
            f"Không phân giải được hostname DB '{db_host}'. Kiểm tra POSTGRES_HOST/DNS hoặc thử lại sau."
        )
    except (ConnectionError, OSError) as e:
        _log("ERROR", f"Connection error: {e}")
        _log("ERROR", traceback.format_exc())
        return _error_json("Không kết nối được máy chủ cơ sở dữ liệu. Kiểm tra cấu hình/kết nối.")
    except asyncio.TimeoutError:
        _log("ERROR", "Connection timeout")
        _log("ERROR", traceback.format_exc())
        return _error_json("Hết thời gian chờ kết nối cơ sở dữ liệu.")
    except Exception as e:
        _log("ERROR", f"Unexpected error occurred: {type(e).__name__}: {e}")
        _log("ERROR", f"Full traceback:\n{traceback.format_exc()}")
        message = str(e) if isinstance(e, ValueError) else _product_error_message(e)
        return _error_json(message)

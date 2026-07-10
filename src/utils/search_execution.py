"""Shared search execution helpers used by src.tools.search_tool."""

import json
import re
import time
import traceback
from os import getenv
from typing import Any, List, Optional

import asyncpg

from src.models import ProductMemory
from src.utils import (
    _log,
    _build_search_intent,
    _build_metadata_filter_clauses,
    _deduplicate_products,
    _expand_query_with_product_type_aliases,
    _filter_products_by_intent,
    _filter_products_with_specific_price,
    _get_query_embedding,
    _is_price_query,
    _normalize_query_text,
    _rrf_merge,
    _vector_preview,
    _extract_query_spec_terms,
    normalize_query_with_llm,
)
from .db_search_runtime import _load_db_config, _resolve_db_connection_settings, _fetch_table_columns


def _no_products_response(query: str) -> str:
    return json.dumps(
        {
            "status": "no_products",
            "message": f"Không tìm thấy sản phẩm phù hợp với: '{query}'",
            "query": query,
            "products": [],
        },
        ensure_ascii=False,
    )


async def _prepare_search_context(user_query: str, memory: ProductMemory, max_results: int) -> dict:
    memory_tokens = memory.to_search_tokens()

    raw_query = getenv("RUN_USER_QUERY", user_query).strip()
    fallback_query = _normalize_query_text(raw_query)
    base_query = await normalize_query_with_llm(raw_query=raw_query, fallback_query=fallback_query)
    if memory_tokens:
        extra = [token for token in memory_tokens if token.lower() not in base_query.lower()]
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

    kw_pats: List[str] = [f"%{token}%" for token in memory_tokens]
    for token in re.findall(r"\b[A-Za-z]{1,6}-?\d{3,5}[A-Za-z0-9.-]*\b", effective_query, re.IGNORECASE):
        pattern = f"%{token.upper()}%"
        if pattern not in kw_pats:
            kw_pats.append(pattern)

    return {
        "base_query": base_query,
        "effective_query": effective_query,
        "intent": intent,
        "fts_text": fts_text,
        "kw_pats": kw_pats[:12],
    }
def _build_metadata_filters(intent: Any, effective_query: str) -> tuple[str, list]:
    metadata_clauses, metadata_params = _build_metadata_filter_clauses(
        intent,
        {
            "brand": ["text", "metadata::text"],
            "series": ["text", "metadata::text"],
            "model": ["text", "metadata::text"],
        },
    )

    spec_terms = _extract_query_spec_terms(effective_query)
    for spec_term in spec_terms:
        metadata_params.append(f"%{spec_term}%")
        param_idx = len(metadata_params)
        metadata_clauses.append(f"(text ILIKE ${param_idx} OR metadata::text ILIKE ${param_idx})")

    metadata_where = " AND ".join(metadata_clauses)
    _log("HYBRID", f"metadata_where='{metadata_where}' metadata_params={metadata_params}")
    if spec_terms:
        _log("HYBRID", f"query_spec_terms={spec_terms}")
    return metadata_where, metadata_params


async def _run_vector_search(
    conn: asyncpg.Connection,
    db_table: str,
    effective_query: str,
    metadata_where: str,
    metadata_params: list,
    max_results: int,
    vector_trace: bool,
) -> List:
    vec_rows_n8n: List = []
    vec = await _get_query_embedding(effective_query)
    if not vec:
        if vector_trace:
            _log("VECTOR_TRACE", "embedding unavailable, vector search skipped")
        return vec_rows_n8n

    if vector_trace:
        _log(
            "VECTOR_TRACE",
            f"effective_query='{effective_query}', dims={len(vec)}, preview={_vector_preview(vec)}",
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
            _log("VECTOR_TRACE", f"sql={' '.join(vec_sql.split())}")
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
                    text_value = (row.get("text") if hasattr(row, "get") else getattr(row, "text", "")) or ""
                    row_id = str(row.get("id") if hasattr(row, "get") else getattr(row, "id", ""))
                    match = re.search(r"Tên sản phẩm:\s*(.+?)(?:\.|Giá)", text_value)
                    product_name = match.group(1).strip() if match else "N/A"
                    vector_products.append({"id": row_id, "tên": product_name})
                except (AttributeError, KeyError, TypeError) as error:
                    _log("VECTOR", f"Failed to parse vector row: {type(error).__name__}: {error}")
            _log("HYBRID", f"Vector(n8n) product_list={json.dumps(vector_products, ensure_ascii=False)}")
        if vector_trace and vec_rows_n8n:
            top_ids = [str(row.get("id")) for row in vec_rows_n8n[:5]]
            _log("VECTOR_TRACE", f"top_ids={top_ids}")
    except Exception as error:
        _log("HYBRID", f"Vector(n8n) failed: {error}")

    return vec_rows_n8n


async def _run_fts_search(
    conn: asyncpg.Connection,
    db_table: str,
    fts_text: str,
    metadata_where: str,
    metadata_params: list,
    max_results: int,
) -> List:
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
        rows = await conn.fetch(fts_sql, *params)
        _log("HYBRID", f"FTS(n8n)={len(rows)} rows ({1000 * (time.perf_counter() - t0):.0f}ms)")
        return rows
    except Exception as error:
        _log("HYBRID", f"FTS(n8n) failed (non-fatal): {error}")
        return []


async def _run_keyword_search(
    conn: asyncpg.Connection,
    db_table: str,
    kw_pats: List[str],
    metadata_where: str,
    metadata_params: list,
    max_results: int,
) -> List:
    if not kw_pats:
        return []

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
        rows = await conn.fetch(kw_sql, *params)
        _log("HYBRID", f"Keyword(n8n)={len(rows)} rows ({1000 * (time.perf_counter() - t0):.0f}ms)")
        return rows
    except Exception as error:
        _log("HYBRID", f"Keyword(n8n) failed: {error}")
        return []


async def _run_hybrid_search(
    conn: asyncpg.Connection,
    db_table: str,
    intent: Any,
    effective_query: str,
    fts_text: str,
    kw_pats: List[str],
    max_results: int,
    vector_trace: bool,
    has_embedding_col: bool,
) -> List:
    _log("SCHEMA", "n8n_vectors -> Hybrid Vector + FTS + Keyword")
    metadata_where, metadata_params = _build_metadata_filters(intent, effective_query)

    vec_rows_n8n: List = []
    if has_embedding_col:
        vec_rows_n8n = await _run_vector_search(
            conn,
            db_table,
            effective_query,
            metadata_where,
            metadata_params,
            max_results,
            vector_trace,
        )

    fts_rows_n8n = await _run_fts_search(conn, db_table, fts_text, metadata_where, metadata_params, max_results)
    kw_rows_n8n = await _run_keyword_search(conn, db_table, kw_pats, metadata_where, metadata_params, max_results)

    _log("HYBRID", f"RRF input: fts_rows={len(fts_rows_n8n)}, vec_rows={len(vec_rows_n8n)}, kw_rows={len(kw_rows_n8n)}")
    try:
        merged_rows = _rrf_merge(
            fts_rows_n8n,
            vec_rows_n8n,
            kw_rows_n8n,
            lambda row: str((row.get("id") if hasattr(row, "get") else getattr(row, "id", "")) or ""),
            max_results,
        )
    except AttributeError as error:
        _log("ERROR", f"AttributeError in _rrf_merge: {error}")
        _log("ERROR", f"fts_rows_n8n type: {type(fts_rows_n8n)}, first: {type(fts_rows_n8n[0]) if fts_rows_n8n else 'empty'}")
        _log("ERROR", f"vec_rows_n8n type: {type(vec_rows_n8n)}, first: {type(vec_rows_n8n[0]) if vec_rows_n8n else 'empty'}")
        _log("ERROR", f"kw_rows_n8n type: {type(kw_rows_n8n)}, first: {type(kw_rows_n8n[0]) if kw_rows_n8n else 'empty'}")
        _log("ERROR", traceback.format_exc())
        merged_rows = [(row, 1.0 / (60 + rank)) for rank, row in enumerate(fts_rows_n8n[:max_results], start=1)]
        if not merged_rows:
            merged_rows = [(row, 1.0 / (60 + rank)) for rank, row in enumerate(vec_rows_n8n[:max_results], start=1)]
        _log("ERROR", f"Fallback to direct rows: {len(merged_rows)} results")

    _log("HYBRID", f"RRF merged(n8n)={len(merged_rows)}")
    return merged_rows


def _parse_products_from_rows(merged_rows: List) -> List[dict]:
    products: List[dict] = []
    for row, score in merged_rows:
        try:
            text_value = (row.get("text") if hasattr(row, "get") else getattr(row, "text", "")) or ""
            row_id = str(row.get("id") if hasattr(row, "get") else getattr(row, "id", ""))
            name = "N/A"
            brand_value = "Unknown"
            price = "N/A"
            config = "N/A"

            name_match = re.search(r"Tên sản phẩm:\s*(.+?)(?:\.|Giá)", text_value)
            if name_match:
                name = name_match.group(1).strip()
            price_match = re.search(r"Giá bán:\s*([^\n.]+)", text_value)
            if price_match:
                price = price_match.group(1).strip()
            config_match = re.search(r"Thông số kỹ thuật:\s*(.+?)(?:Trang sản phẩm:|$)", text_value, re.DOTALL)
            if config_match:
                config = config_match.group(1).strip()

            product_link_from_text = "N/A"
            link_match = re.search(r"Trang sản phẩm:\s*(https?://[^\s\)]+|[^\s\)]+)", text_value, re.IGNORECASE)
            if link_match:
                product_link_from_text = link_match.group(1).strip()

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
        except (AttributeError, KeyError, TypeError) as error:
            _log("ERROR", f"Failed to parse row: {type(error).__name__}: {error}")
            _log("ERROR", f"Row type: {type(row).__name__}, Row: {row}")

    _log("RESULT", f"Products parsed={len(products)}")
    if products:
        preview = products[: min(3, len(products))]
        _log("RESULT", f"Preview top products={json.dumps(preview, ensure_ascii=False)}")
    return products


def _finalize_products(products: List[dict], intent: Any, base_query: str, effective_query: str) -> Optional[str]:
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
        return _no_products_response(effective_query)

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

"""Search product tool - implementation module for src package.

This is the canonical implementation. tools/normal/search_tool.py is now
a backward-compatible shim that re-exports from here.
"""

import asyncio
import socket
import traceback
from os import getenv
from typing import Optional

import asyncpg
from langchain_core.tools import tool

from ..utils import (
    get_db_pool,
    _log,
    _error_json,
    _product_error_message,
    _is_vector_trace_enabled,
)
from ..models import ProductMemory
from .schemas import SearchProductsArgs
from ..utils.search_execution import (
    _prepare_search_context,
    _load_db_config,
    _resolve_db_connection_settings,
    _fetch_table_columns,
    _run_hybrid_search,
    _parse_products_from_rows,
    _finalize_products,
    _no_products_response,
)


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
    context = await _prepare_search_context(user_query, memory, max_results)
    base_query = context["base_query"]
    effective_query = context["effective_query"]
    intent = context["intent"]
    fts_text = context["fts_text"]
    kw_pats = context["kw_pats"]

    try:
        db_config = _resolve_db_connection_settings(_load_db_config())
        pool = await get_db_pool(
            host=db_config["host"],
            port=db_config["port"],
            database=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
            min_size=db_config["pool_min_size"],
            max_size=db_config["pool_max_size"],
            ssl_mode=db_config["ssl_mode"],
            connection_options=db_config["connection_options"],
        )
        _log("CONNECT", "Acquiring PostgreSQL connection from pool")

        async with pool.acquire() as conn:
            db_table = db_config["table"]
            columns = await _fetch_table_columns(conn, db_table)
            has_embedding_col = "embedding" in columns
            _log("HYBRID", f"has_embedding_col={has_embedding_col}")
            merged_n8n = await _run_hybrid_search(
                conn,
                db_table,
                intent,
                effective_query,
                fts_text,
                kw_pats,
                max_results,
                vector_trace,
                has_embedding_col,
            )
            if not merged_n8n:
                _log("RESULT", "No products found in database")
                return _no_products_response(effective_query)

            products = _parse_products_from_rows(merged_n8n)
            return _finalize_products(products, intent, base_query, effective_query)

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
        _log("ERROR", f"DNS resolve error: {e}")
        _log("ERROR", traceback.format_exc())
        return _error_json("Không phân giải được hostname DB. Kiểm tra POSTGRES_HOST/DNS hoặc thử lại sau.")
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

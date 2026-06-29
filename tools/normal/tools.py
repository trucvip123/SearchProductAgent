from agents import function_tool, RunContextWrapper
from typing import Optional, Any, List, Dict
from dataclasses import dataclass, fields, asdict
import json
import httpx
import asyncpg
import asyncio
import re
import time
import traceback
from os import getenv
from datetime import datetime


@dataclass
class ProductMemory:
    """Bộ nhớ có cấu trúc cho một lượt tìm kiếm sản phẩm.

    LLM điền các field này khi gọi tool để đảm bảo từ khoá quan trọng
    không bị mất/méo qua quá trình sinh text.

    Dùng cho mọi nhóm thiết bị:
      - Ổ cứng ngoài: brand="WD", series="My Book", capacity="3TB", product_type="ổ cứng ngoài"
      - Máy chủ:      brand="Dell", series="PowerEdge", model="R740xd", cpu="Gold 6248", ram="128GB"
      - Laptop:       brand="Lenovo", model="ThinkPad X1", ram="16GB", storage="512GB SSD"
    """
    product_type: Optional[str] = None  # loại thiết bị: "máy chủ", "ổ cứng ngoài", "laptop", ...
    brand: Optional[str] = None         # hãng: Dell, HPE, WD, Synology, ...
    series: Optional[str] = None        # dòng sản phẩm: PowerEdge, My Book, ThinkPad, ...
    model: Optional[str] = None         # model cụ thể: R740xd, DS223j, ...
    cpu: Optional[str] = None           # CPU: Gold 6248, E-2434, ...
    ram: Optional[str] = None           # RAM: 128GB, 32GB, ...
    storage: Optional[str] = None       # lưu trữ gắn trong: 2TB SSD, ...
    capacity: Optional[str] = None      # dung lượng (ổ cứng ngoài, NAS): 3TB, 8TB, ...
    interface: Optional[str] = None     # giao tiếp: USB 3.0, PCIe, SAS, ...
    price_range: Optional[str] = None   # khoảng giá: "dưới 5 triệu", "10-20 triệu", ...

    def to_search_tokens(self) -> List[str]:
        """Trả về danh sách token có nghĩa để tạo DB search pattern."""
        tokens = []
        for f in fields(self):
            val = getattr(self, f.name)
            if val and isinstance(val, str) and val.strip():
                tokens.append(val.strip())
        return tokens

    def to_log_dict(self) -> Dict[str, str]:
        """Trả về dict chỉ chứa các field đã được điền."""
        return {k: v for k, v in asdict(self).items() if v}


def _log(step: str, message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [search_products] [{step}] {message}", flush=True)


async def _get_query_embedding(query: str) -> Optional[List[float]]:
    """Gọi Ollama Embeddings API để lấy vector của query.

    Trả None nếu API lỗi — vector search sẽ bị bỏ qua (non-fatal).
    Cấu hình qua env: EMBEDDING_MODEL (default: nomic-embed-text).
    """
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
    """Kết hợp kết quả FTS + Vector + Keyword bằng Reciprocal Rank Fusion.

    Công thức: score = Σ 1/(k + rank_i)
    Keyword chỉ bổ sung kết quả chưa có trong FTS/Vector (half weight).
    """
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
        if key not in scores:  # keyword chỉ bổ sung gaps
            scores[key] = 1.0 / (k * 2 + rank)
            store[key] = row

    ranked = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [(store[rk], round(scores[rk], 5)) for rk in ranked[:max_results]]


async def custom_product_error_handler(ctx: RunContextWrapper[Any], error: Exception) -> str:
    """Hàm xử lý lỗi tùy chỉnh cho tool truy vấn sản phẩm máy chủ từ vector DB."""
    _log("ERROR_HANDLER", f"Caught error: {type(error).__name__}: {error}")
    if isinstance(error, httpx.HTTPStatusError):
        return f"Lỗi HTTP {error.response.status_code} khi cố gắng truy vấn database. Vui lòng thử lại sau."
    elif isinstance(error, httpx.TimeoutException):
        return "Yêu cầu truy vấn bị quá thời gian chờ. Vui lòng thử lại."
    elif isinstance(error, httpx.RequestError):
        return "Lỗi mạng khi cố gắng truy vấn database. Vui lòng kiểm tra kết nối và thử lại."
    else:
        return f"Đã xảy ra lỗi không mong muốn: {type(error).__name__}. Vui lòng thử lại."


@function_tool(failure_error_function=custom_product_error_handler)
async def search_products(
    user_query: str,
    max_results: int = 5,
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
) -> str:
    """Tìm kiếm thông tin thiết bị từ PostgreSQL Vector Database.

    Truy vấn dữ liệu thiết bị (giá, cấu hình, hãng) từ PostgreSQL database.

    Args:
        user_query: Câu người dùng gõ nguyên văn (fallback nếu structured fields trống).
        max_results: Số lượng kết quả tối đa (mặc định 5).

        --- Structured Memory (ưu tiên hơn user_query) ---
        product_type: Loại thiết bị. VD: "ổ cứng ngoài", "máy chủ", "laptop", "thiết bị mạng".
        brand:        Hãng sản xuất. VD: "WD", "Dell", "HPE", "Synology", "Lenovo".
        series:       Dòng sản phẩm. VD: "My Book", "PowerEdge", "ThinkPad", "ProLiant".
        model:        Model cụ thể. VD: "R740xd", "DS223j", "X1 Carbon".
        cpu:          CPU. VD: "Intel XEON E-2434", "Gold 6248", "Core i7-1355U".
        ram:          RAM. VD: "128GB", "32GB ECC".
        storage:      Lưu trữ gắn trong. VD: "2TB SSD", "4x 3.5 inch HDD".
        capacity:     Dung lượng ổ cứng ngoài / NAS. VD: "3TB", "8TB".
        interface:    Giao tiếp. VD: "USB 3.0", "PCIe 4.0", "SAS 12Gbps".
        price_range:  Khoảng giá. VD: "dưới 5 triệu", "10-20 triệu".

    Returns:
        JSON string chứa danh sách sản phẩm phù hợp từ PostgreSQL.
    """
    # ── Build ProductMemory từ structured fields ──────────────────────────
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
    )
    memory_tokens = memory.to_search_tokens()

    # ── Chọn effective_query ──────────────────────────────────────────────
    effective_query = getenv("RUN_USER_QUERY", user_query).strip()
    

    _log("START", f"user_query='{user_query}', max_results={max_results}")
    _log("MEMORY", f"ProductMemory={memory.to_log_dict()}")
    _log("GUARD", f"Effective query='{effective_query}'")

    # ── FTS query text: memory tokens > effective_query ───────────────────
    fts_text = " ".join(memory_tokens) if memory_tokens else effective_query
    _log("HYBRID", f"fts_text='{fts_text}'")

    # ── Keyword patterns từ structured memory + model numbers ────────────
    kw_pats: List[str] = [f"%{t}%" for t in memory_tokens]
    for t in re.findall(r"\b[A-Za-z]{1,6}-?\d{3,5}[A-Za-z0-9.-]*\b", effective_query, re.IGNORECASE):
        p = f"%{t.upper()}%"
        if p not in kw_pats:
            kw_pats.append(p)
    kw_pats = kw_pats[:12]

    # Đọc config từ environment variables
    db_host = getenv("POSTGRES_HOST", "localhost")
    db_port = int(getenv("POSTGRES_PORT", "5432"))
    db_name = getenv("POSTGRES_DB", "server_products")
    db_user = getenv("POSTGRES_USER", "postgres")
    db_password = getenv("POSTGRES_PASSWORD", "")
    db_table = getenv("POSTGRES_TABLE", "products")

    # ── Table name validation (SQL injection guard) ──────────────────────
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', db_table):
        raise ValueError(f"Invalid table name: '{db_table}'")

    safe_pw = "***" if db_password else "(empty)"
    _log(
        "CONFIG",
        f"Connecting PostgreSQL host={db_host} port={db_port} db={db_name} user={db_user} table={db_table} password={safe_pw}",
    )

    try:
        # Kết nối đến PostgreSQL
        conn = await asyncpg.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
            timeout=15
        )
        _log("CONNECT", "Connected to PostgreSQL")

        try:
            # Detect schema của bảng để query đúng định dạng dữ liệu.
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

            # ── Schema: product table chuẩn ──────────────────────────────────
            if {"name", "price", "brand", "config", "description"}.issubset(columns):
                _log("SCHEMA", "product table → Hybrid FTS + Vector + Keyword")

                # Biểu thức tsvector dùng lại ở WHERE và ORDER BY
                _tsv = (
                    f"to_tsvector('simple', "
                    f"coalesce(name,'') || ' ' || coalesce(brand,'') || ' ' || "
                    f"coalesce(config,'') || ' ' || coalesce(description,''))"
                )

                # 1) FTS ──────────────────────────────────────────────────────
                fts_rows: List = []
                try:
                    t0 = time.perf_counter()
                    fts_rows = await conn.fetch(f"""
                        SELECT name, price, brand, config, description
                        FROM {db_table}
                        WHERE {_tsv} @@ plainto_tsquery('simple', $1)
                        ORDER BY ts_rank_cd({_tsv}, plainto_tsquery('simple', $1)) DESC
                        LIMIT $2
                    """, fts_text, max_results * 4)
                    _log("HYBRID", f"FTS={len(fts_rows)} rows ({1000*(time.perf_counter()-t0):.0f}ms)")
                except Exception as exc:
                    _log("HYBRID", f"FTS failed (non-fatal): {exc}")

                # 2) Vector ───────────────────────────────────────────────────
                vec_rows: List = []
                if has_embedding_col:
                    vec = await _get_query_embedding(effective_query)
                    if vec:
                        emb_str = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
                        try:
                            t0 = time.perf_counter()
                            vec_rows = await conn.fetch(f"""
                                SELECT name, price, brand, config, description
                                FROM {db_table}
                                ORDER BY embedding <=> $1::vector
                                LIMIT $2
                            """, emb_str, max_results * 4)
                            _log("HYBRID", f"Vector={len(vec_rows)} rows ({1000*(time.perf_counter()-t0):.0f}ms)")
                        except Exception as exc:
                            _log("HYBRID", f"Vector failed (non-fatal): {exc}")

                # 3) Keyword fallback ─────────────────────────────────────────
                kw_rows: List = []
                if kw_pats:
                    try:
                        t0 = time.perf_counter()
                        kw_rows = await conn.fetch(f"""
                            SELECT name, price, brand, config, description
                            FROM {db_table}
                            WHERE name ILIKE ANY($1::text[])
                               OR config ILIKE ANY($1::text[])
                               OR description ILIKE ANY($1::text[])
                            LIMIT $2
                        """, kw_pats, max_results * 2)
                        _log("HYBRID", f"Keyword={len(kw_rows)} rows ({1000*(time.perf_counter()-t0):.0f}ms)")
                    except Exception as exc:
                        _log("HYBRID", f"Keyword failed: {exc}")

                # RRF merge
                merged = _rrf_merge(fts_rows, vec_rows, kw_rows, lambda r: r["name"] or "", max_results)
                _log("HYBRID", f"RRF merged={len(merged)} (fts={len(fts_rows)}, vec={len(vec_rows)}, kw={len(kw_rows)})")
                for row, score in merged:
                    products.append({
                        "tên": row["name"] or "N/A",
                        "giá": str(row["price"]) if row["price"] else "N/A",
                        "hãng": row["brand"] or "Unknown",
                        "cấu_hình": row["config"] or "N/A",
                        "_score": score,
                    })

            # ── Schema: n8n_vectors (id, text, metadata, embedding) ───────────
            elif {"text", "metadata"}.issubset(columns):
                _log("SCHEMA", "n8n_vectors → Hybrid Vector + FTS + Keyword")

                # 1) Vector (primary cho n8n_vectors) ────────────────────────
                vec_rows_n8n: List = []
                if has_embedding_col:
                    vec = await _get_query_embedding(effective_query)
                    if vec:
                        emb_str = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
                        try:
                            t0 = time.perf_counter()
                            vec_rows_n8n = await conn.fetch(f"""
                                SELECT id, text, metadata
                                FROM {db_table}
                                ORDER BY embedding <=> $1::vector
                                LIMIT $2
                            """, emb_str, max_results * 4)
                            _log("HYBRID", f"Vector(n8n)={len(vec_rows_n8n)} rows ({1000*(time.perf_counter()-t0):.0f}ms)")
                        except Exception as exc:
                            _log("HYBRID", f"Vector(n8n) failed: {exc}")

                # 2) FTS trên cột text ─────────────────────────────────────────
                fts_rows_n8n: List = []
                try:
                    t0 = time.perf_counter()
                    fts_rows_n8n = await conn.fetch(f"""
                        SELECT id, text, metadata
                        FROM {db_table}
                        WHERE to_tsvector('simple', coalesce(text,'')) @@ plainto_tsquery('simple', $1)
                        ORDER BY ts_rank_cd(to_tsvector('simple', coalesce(text,'')),
                                           plainto_tsquery('simple', $1)) DESC
                        LIMIT $2
                    """, fts_text, max_results * 4)
                    _log("HYBRID", f"FTS(n8n)={len(fts_rows_n8n)} rows ({1000*(time.perf_counter()-t0):.0f}ms)")
                except Exception as exc:
                    _log("HYBRID", f"FTS(n8n) failed (non-fatal): {exc}")

                # 3) Keyword fallback ─────────────────────────────────────────
                kw_rows_n8n: List = []
                if kw_pats:
                    try:
                        t0 = time.perf_counter()
                        kw_rows_n8n = await conn.fetch(f"""
                            SELECT id, text, metadata
                            FROM {db_table}
                            WHERE text ILIKE ANY($1::text[])
                            LIMIT $2
                        """, kw_pats, max_results * 2)
                        _log("HYBRID", f"Keyword(n8n)={len(kw_rows_n8n)} rows ({1000*(time.perf_counter()-t0):.0f}ms)")
                    except Exception as exc:
                        _log("HYBRID", f"Keyword(n8n) failed: {exc}")

                # RRF merge
                merged_n8n = _rrf_merge(
                    fts_rows_n8n, vec_rows_n8n, kw_rows_n8n,
                    lambda r: str(r.get("id") or ""),
                    max_results,
                )
                _log("HYBRID", f"RRF merged(n8n)={len(merged_n8n)}")
                for row, score in merged_n8n:
                    text_value = row.get("text") or ""
                    name = "N/A"; brand = "Unknown"; price = "N/A"; config = "N/A"
                    description = text_value[:300]
                    _log("HYBRID", f"Parsing n8n row id={row.get('id')} score={score} text_len={len(text_value)}")

                    # Plain text format: "Tên sản phẩm: ... Giá bán: ... Thông số kỹ thuật: ..."
                    m_name = re.search(r"Tên sản phẩm:\s*(.+?)(?:\.|Giá)", text_value)
                    if m_name:
                        name = m_name.group(1).strip()
                    m_price = re.search(r"Giá bán:\s*([^\n.]+)", text_value)
                    if m_price:
                        price = m_price.group(1).strip()
                    m_config = re.search(r"Thông số kỹ thuật:\s*(.+?)(?:Trang sản phẩm:|$)", text_value, re.DOTALL)
                    if m_config:
                        config = m_config.group(1).strip()

                    for candidate in ["DELL", "HPE", "ASUS", "SSN", "LENOVO", "SUPERMICRO", "AMD", "INTEL", "WD", "SEAGATE", "SYNOLOGY"]:
                        if candidate in text_value.upper():
                            brand = candidate; break
                    products.append({
                        "id": str(row.get("id")),
                        "tên": name, "giá": price, "hãng": brand,
                        "cấu_hình": config, "_score": score,
                    })

            else:
                raise ValueError(
                    f"Schema bảng '{db_table}' chưa được hỗ trợ. Các cột hiện có: {sorted(columns)}"
                )

            _log("RESULT", f"Products parsed={len(products)}")
            if products:
                preview = products[: min(3, len(products))]
                _log("RESULT", f"Preview top products={json.dumps(preview, ensure_ascii=False)}")

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

            _log("DONE", f"Successfully found {len(products)} products from PostgreSQL")
            return json.dumps({
                "status": "success",
                "count": len(products),
                "query": effective_query,
                "products": products
            }, ensure_ascii=False, indent=2)

        finally:
            await conn.close()
            _log("CONNECT", "Closed PostgreSQL connection")

    except asyncpg.PostgresError as e:
        _log("ERROR", f"PostgreSQL error: {e}")
        _log("ERROR", traceback.format_exc())
        raise ValueError(f"Lỗi cơ sở dữ liệu: {str(e)}")
    except asyncpg.TooManyConnectionsError as e:
        _log("ERROR", "Too many connections")
        _log("ERROR", traceback.format_exc())
        raise ValueError("Cơ sở dữ liệu quá tải. Vui lòng thử lại sau.")
    except asyncpg.InvalidPasswordError as e:
        _log("ERROR", "Invalid password")
        _log("ERROR", traceback.format_exc())
        raise ValueError("Lỗi xác thực cơ sở dữ liệu. Kiểm tra mật khẩu.")
    except asyncpg.TargetServerRejectedException as e:
        _log("ERROR", "Server rejected connection")
        _log("ERROR", traceback.format_exc())
        raise ValueError("Máy chủ cơ sở dữ liệu từ chối kết nối. Kiểm tra cấu hình.")
    except asyncio.TimeoutError:
        _log("ERROR", "Connection timeout")
        _log("ERROR", traceback.format_exc())
        raise ValueError("Hết thời gian chờ kết nối cơ sở dữ liệu.")
    except Exception as e:
        _log("ERROR", f"Unexpected error occurred: {e}")
        _log("ERROR", traceback.format_exc())
        raise ValueError(f"Lỗi không xác định: {str(e)}")
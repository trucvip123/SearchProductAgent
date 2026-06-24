from agents import function_tool, RunContextWrapper
from typing import Optional, Any, List, Dict
import json
import httpx
import asyncpg
import asyncio
from os import getenv


async def custom_product_error_handler(ctx: RunContextWrapper[Any], error: Exception) -> str:
    """Hàm xử lý lỗi tùy chỉnh cho tool truy vấn sản phẩm máy chủ từ vector DB."""
    print(f"--- Custom Error Handler: Caught error: {type(error).__name__}: {error} ---")
    if isinstance(error, httpx.HTTPStatusError):
        return f"Lỗi HTTP {error.response.status_code} khi cố gắng truy vấn database. Vui lòng thử lại sau."
    elif isinstance(error, httpx.TimeoutException):
        return "Yêu cầu truy vấn bị quá thời gian chờ. Vui lòng thử lại."
    elif isinstance(error, httpx.RequestError):
        return "Lỗi mạng khi cố gắng truy vấn database. Vui lòng kiểm tra kết nối và thử lại."
    else:
        return f"Đã xảy ra lỗi không mong muốn: {type(error).__name__}. Vui lòng thử lại."


@function_tool(failure_error_function=custom_product_error_handler)
async def search_server_products(
    query: str,
    max_results: int = 5
) -> str:
    """Tìm kiếm thông tin sản phẩm máy chủ từ PostgreSQL Vector Database.

    Truy vấn dữ liệu sản phẩm máy chủ (giá, cấu hình, hãng) từ PostgreSQL database
    bằng cách sử dụng semantic search với query text.

    Args:
        query: Câu hỏi hoặc từ khóa tìm kiếm (VD: "máy chủ Dell dưới 200k", 
               "máy với CPU E5", "HPE 16 core", etc.)
        max_results: Số lượng kết quả tối đa (mặc định 5).

    Returns:
        JSON string chứa danh sách sản phẩm phù hợp từ PostgreSQL
        với thông tin: tên, giá, cấu hình, hãng.
    """
    print(f"--- Tool: Searching products in PostgreSQL Vector DB with query: '{query}' ---")

    # Đọc config từ environment variables
    db_host = getenv("POSTGRES_HOST", "localhost")
    db_port = int(getenv("POSTGRES_PORT", "5432"))
    db_name = getenv("POSTGRES_DB", "server_products")
    db_user = getenv("POSTGRES_USER", "postgres")
    db_password = getenv("POSTGRES_PASSWORD", "")
    db_table = getenv("POSTGRES_TABLE", "products")

    print(f"--- Tool: Connecting to PostgreSQL at {db_host}:{db_port}/{db_name} ---")

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
        print("--- Tool: Connected to PostgreSQL ---")

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

            print(f"--- Tool: Detected columns in '{db_table}': {sorted(columns)} ---")
            print(f"--- Tool: Executing query with keyword: '{query}' ---")
            search_pattern = f"%{query}%"

            products = []

            # Schema dạng product table chuẩn.
            if {"name", "price", "brand", "config", "description"}.issubset(columns):
                query_sql = f"""
                    SELECT
                        name as "tên",
                        price as "giá",
                        brand as "hãng",
                        config as "cấu_hình",
                        description as "mô_tả"
                    FROM {db_table}
                    WHERE
                        name ILIKE $1
                        OR description ILIKE $1
                        OR config ILIKE $1
                    LIMIT $2
                """
                results = await conn.fetch(query_sql, search_pattern, max_results)
                for row in results:
                    products.append(
                        {
                            "tên": row["tên"] or "N/A",
                            "giá": str(row["giá"]) if row["giá"] else "N/A",
                            "hãng": row["hãng"] or "Unknown",
                            "cấu_hình": row["cấu_hình"] or "N/A",
                            "mô_tả": row["mô_tả"] or "",
                        }
                    )

            # Schema dạng n8n_vectors: id, text, metadata, embedding.
            elif {"text", "metadata"}.issubset(columns):
                query_sql = f"""
                    SELECT id, text, metadata
                    FROM {db_table}
                    WHERE text ILIKE $1
                    LIMIT $2
                """
                results = await conn.fetch(query_sql, search_pattern, max_results)
                for row in results:
                    text_value = row.get("text") or ""
                    name = "N/A"
                    brand = "Unknown"
                    price = "N/A"
                    config = "N/A"
                    description = text_value[:300]

                    # Dữ liệu text thường là JSON string; thử parse để bóc product_name/url.
                    try:
                        parsed = json.loads(text_value)
                        if isinstance(parsed, list) and parsed:
                            first_item = parsed[0]
                            if isinstance(first_item, dict):
                                name = first_item.get("product_name") or first_item.get("name") or name
                                description = first_item.get("description") or description
                                maybe_price = first_item.get("price")
                                if maybe_price:
                                    price = str(maybe_price)
                                maybe_config = first_item.get("config") or first_item.get("spec")
                                if maybe_config:
                                    config = str(maybe_config)
                    except (json.JSONDecodeError, TypeError):
                        # fallback: suy đoán brand từ text
                        pass

                    upper_text = text_value.upper()
                    for candidate in ["DELL", "HPE", "ASUS", "SSN", "LENOVO", "SUPERMICRO"]:
                        if candidate in upper_text:
                            brand = candidate
                            break

                    products.append(
                        {
                            "id": str(row.get("id")),
                            "tên": name,
                            "giá": price,
                            "hãng": brand,
                            "cấu_hình": config,
                            "mô_tả": description,
                        }
                    )

            else:
                raise ValueError(
                    f"Schema bảng '{db_table}' chưa được hỗ trợ. Các cột hiện có: {sorted(columns)}"
                )

            print(f"--- Tool: Found {len(products)} products ---")
            if not products:
                print("--- Tool Warning: No products found in database ---")
                return json.dumps(
                    {
                        "status": "no_products",
                        "message": f"Không tìm thấy sản phẩm phù hợp với: '{query}'",
                        "query": query,
                        "products": [],
                    },
                    ensure_ascii=False,
                )

            print(f"--- Tool: Successfully found {len(products)} products from PostgreSQL ---")
            return json.dumps({
                "status": "success",
                "count": len(products),
                "query": query,
                "products": products
            }, ensure_ascii=False, indent=2)

        finally:
            await conn.close()
            print("--- Tool: Closed PostgreSQL connection ---")

    except asyncpg.PostgresError as e:
        print(f"--- Tool Error: PostgreSQL error: {e} ---")
        raise ValueError(f"Lỗi cơ sở dữ liệu: {str(e)}")
    except asyncpg.TooManyConnectionsError as e:
        print(f"--- Tool Error: Too many connections ---")
        raise ValueError("Cơ sở dữ liệu quá tải. Vui lòng thử lại sau.")
    except asyncpg.InvalidPasswordError as e:
        print(f"--- Tool Error: Invalid password ---")
        raise ValueError("Lỗi xác thực cơ sở dữ liệu. Kiểm tra mật khẩu.")
    except asyncpg.TargetServerRejectedException as e:
        print(f"--- Tool Error: Server rejected connection ---")
        raise ValueError("Máy chủ cơ sở dữ liệu từ chối kết nối. Kiểm tra cấu hình.")
    except asyncio.TimeoutError:
        print(f"--- Tool Error: Connection timeout ---")
        raise ValueError("Hết thời gian chờ kết nối cơ sở dữ liệu.")
    except Exception as e:
        print(f"--- Tool Error: An unexpected error occurred: {e} ---")
        raise ValueError(f"Lỗi không xác định: {str(e)}")
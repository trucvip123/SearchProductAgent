"""Debug utility to inspect asyncpg.Record structure."""

import asyncio
import asyncpg
from os import getenv


async def inspect_record_structure():
    """Connect to DB and inspect the actual row types returned."""
    db_host = getenv("POSTGRES_HOST", "localhost")
    db_port = int(getenv("POSTGRES_PORT", "5432"))
    db_name = getenv("POSTGRES_DB", "server_products")
    db_user = getenv("POSTGRES_USER", "postgres")
    db_password = getenv("POSTGRES_PASSWORD", "")
    
    try:
        conn = await asyncpg.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
        )
        
        # Fetch one sample row
        result = await conn.fetch("SELECT id, text FROM products LIMIT 1")
        
        if result:
            row = result[0]
            print(f"Row type: {type(row)}")
            print(f"Row dir: {[x for x in dir(row) if not x.startswith('_')]}")
            print(f"Has 'get' method: {hasattr(row, 'get')}")
            print(f"Supports [] indexing: {hasattr(row, '__getitem__')}")
            
            print(f"\nTesting access methods:")
            print(f"  row['id'] = {row['id']}")
            print(f"  row.get('id') = {row.get('id') if hasattr(row, 'get') else 'N/A'}")
            print(f"  getattr(row, 'id', 'N/A') = {getattr(row, 'id', 'N/A')}")
        
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(inspect_record_structure())

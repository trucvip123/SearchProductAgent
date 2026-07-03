from datetime import datetime


def _log(step: str, message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [search_products] [{step}] {message}", flush=True)
